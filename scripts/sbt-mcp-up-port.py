#!/usr/bin/env python3
"""Assign a worktree a stable, globally-unique MCP server port.

Usage: sbt-mcp-up-port.py <worktree>

Prints the chosen port to stdout and writes/updates both the worktree's
.mcp.json and a small central registry (keyed by absolute worktree path). The
registry guarantees two worktrees never get the same port and that a worktree's
port never changes across runs -- otherwise a per-worktree "first free port"
scan can hand the same port to two worktrees at different times, and Claude Code
(which caches the .mcp.json URL at session start) ends up talking to the wrong
worktree's server.

This lives in its own file rather than an inline heredoc because macOS ships
bash 3.2, whose parser mishandles a here-document embedded in $(...) command
substitution.
"""

import json
import os
import re
import socket
import sys

worktree = os.path.abspath(sys.argv[1])
mcp_path = os.path.join(worktree, ".mcp.json")
NAME = "mcp-sbt-shell"
LO, HI = 8092, 8192  # ports [LO, HI)

reg_dir = os.path.join(
    os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"),
    "mcp-sbt-shell",
)
reg_path = os.path.join(reg_dir, "ports.json")


def free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


# Load (and prune) the registry: {worktree_abspath: port}. Drop entries whose
# directory no longer exists so the port pool doesn't leak over time.
registry = {}
if os.path.exists(reg_path):
    try:
        with open(reg_path) as f:
            registry = json.load(f)
    except (OSError, ValueError):
        registry = {}
registry = {k: v for k, v in registry.items() if k == worktree or os.path.isdir(k)}

# Reuse our own reserved port unconditionally so the URL stays stable across
# restarts (a bound port here is just our own previous/other server).
port = registry.get(worktree)
if port is None:
    # Migrate an existing .mcp.json port if it isn't already claimed by another
    # worktree; otherwise pick the lowest unreserved, currently-free port.
    reserved = set(registry.values())
    data0 = {}
    if os.path.exists(mcp_path):
        try:
            with open(mcp_path) as f:
                data0 = json.load(f)
        except (OSError, ValueError):
            data0 = {}
    m = re.search(r":(\d+)/", data0.get("mcpServers", {}).get(NAME, {}).get("url", ""))
    if m and int(m.group(1)) not in reserved:
        port = int(m.group(1))
    else:
        for p in range(LO, HI):
            if p not in reserved and free(p):
                port = p
                break
        else:
            sys.exit(f"no free port in {LO}-{HI - 1}")
    registry[worktree] = port
    os.makedirs(reg_dir, exist_ok=True)
    tmp = reg_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(registry, f, indent=2)
        f.write("\n")
    os.replace(tmp, reg_path)

data = {}
if os.path.exists(mcp_path):
    try:
        with open(mcp_path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        # Corrupt/unreadable .mcp.json: start fresh rather than crash. We own
        # the mcp-sbt-shell key and are about to rewrite the file anyway.
        data = {}
servers = data.setdefault("mcpServers", {})

# 127.0.0.1, not localhost: on macOS localhost prefers IPv6, where Docker et al.
# often squat on the port and intercept the connection.
servers[NAME] = {"type": "http", "url": f"http://127.0.0.1:{port}/mcp"}
with open(mcp_path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")

print(port)
sys.stderr.write(
    f"[sbt-mcp-up] {NAME} -> http://127.0.0.1:{port}/mcp  (wrote {mcp_path})\n"
)
