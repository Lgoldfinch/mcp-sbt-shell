"""Tests for scripts/sbt-mcp-up-port.py, the per-worktree port allocator.

The allocator is a standalone script (not an importable module — it runs work at
import time), so we exercise it the way sbt-mcp-up.sh does: as a subprocess,
passing a worktree path and isolating its registry via XDG_CACHE_HOME.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "sbt-mcp-up-port.py"
LO, HI = 8092, 8192  # keep in sync with the allocator


def run(worktree, cache_dir):
    """Run the allocator for `worktree`, isolating its registry in `cache_dir`.

    Returns (port:int, stderr:str). Raises if the script exits non-zero.
    """
    env = {**os.environ, "XDG_CACHE_HOME": str(cache_dir)}
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(worktree)],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return int(proc.stdout.strip()), proc.stderr


def read_mcp(worktree):
    return json.loads((Path(worktree) / ".mcp.json").read_text())


def registry(cache_dir):
    return json.loads((Path(cache_dir) / "mcp-sbt-shell" / "ports.json").read_text())


@pytest.fixture
def cache(tmp_path):
    return tmp_path / "cache"


@pytest.fixture
def wt(tmp_path):
    """A worktree directory factory: wt('a') -> a fresh, existing dir."""

    def make(name):
        d = tmp_path / "wt" / name
        d.mkdir(parents=True)
        return d

    return make


# --- basic allocation ------------------------------------------------------


def test_allocates_port_in_range_and_writes_mcp_json(cache, wt):
    a = wt("a")
    port, _ = run(a, cache)
    assert LO <= port < HI
    server = read_mcp(a)["mcpServers"]["mcp-sbt-shell"]
    assert server == {"type": "http", "url": f"http://127.0.0.1:{port}/mcp"}


def test_url_uses_ipv4_loopback_not_localhost(cache, wt):
    # 127.0.0.1, not localhost: avoids macOS IPv6/Docker interception.
    a = wt("a")
    run(a, cache)
    url = read_mcp(a)["mcpServers"]["mcp-sbt-shell"]["url"]
    assert url.startswith("http://127.0.0.1:")
    assert "localhost" not in url


def test_registry_keyed_by_absolute_worktree_path(cache, wt):
    a = wt("a")
    port, _ = run(a, cache)
    reg = registry(cache)
    assert reg == {str(a): port}


# --- stability & uniqueness (the whole point of the registry) --------------


def test_same_worktree_gets_same_port_across_runs(cache, wt):
    a = wt("a")
    p1, _ = run(a, cache)
    p2, _ = run(a, cache)
    assert p1 == p2


def test_distinct_worktrees_get_distinct_ports(cache, wt):
    pa, _ = run(wt("a"), cache)
    pb, _ = run(wt("b"), cache)
    pc, _ = run(wt("c"), cache)
    assert len({pa, pb, pc}) == 3


# --- migrating an existing .mcp.json port ----------------------------------


def _seed_mcp(worktree, port, extra=None):
    data = {"mcpServers": {"mcp-sbt-shell": {"type": "http", "url": f"http://127.0.0.1:{port}/mcp"}}}
    if extra:
        data.update(extra)
    (Path(worktree) / ".mcp.json").write_text(json.dumps(data))


def test_migrates_existing_mcp_json_port(cache, wt):
    a = wt("a")
    _seed_mcp(a, 8150)
    port, _ = run(a, cache)
    assert port == 8150


def test_does_not_migrate_a_port_another_worktree_already_holds(cache, wt):
    a, b = wt("a"), wt("b")
    _seed_mcp(a, 8150)
    _seed_mcp(b, 8150)  # both stale-point at 8150
    pa, _ = run(a, cache)
    pb, _ = run(b, cache)
    assert pa == 8150
    assert pb != 8150


def test_preserves_unrelated_keys_in_mcp_json(cache, wt):
    a = wt("a")
    _seed_mcp(a, 8150, extra={"other": {"keep": "me"}})
    run(a, cache)
    data = read_mcp(a)
    assert data["other"] == {"keep": "me"}


# --- registry hygiene ------------------------------------------------------


def test_prunes_entries_for_deleted_worktrees(cache, wt):
    reg_dir = Path(cache) / "mcp-sbt-shell"
    reg_dir.mkdir(parents=True)
    (reg_dir / "ports.json").write_text(json.dumps({"/no/such/dir": 8150}))
    a = wt("a")
    port, _ = run(a, cache)
    reg = registry(cache)
    assert "/no/such/dir" not in reg
    assert reg == {str(a): port}


def test_corrupt_registry_is_recovered_not_fatal(cache, wt):
    reg_dir = Path(cache) / "mcp-sbt-shell"
    reg_dir.mkdir(parents=True)
    (reg_dir / "ports.json").write_text("{ not json")
    a = wt("a")
    port, _ = run(a, cache)  # must not raise
    assert LO <= port < HI


def test_corrupt_mcp_json_is_ignored_for_migration(cache, wt):
    a = wt("a")
    (a / ".mcp.json").write_text("{ not json")
    port, _ = run(a, cache)  # falls back to a scanned free port, no crash
    assert LO <= port < HI
    # and the file is rewritten as valid JSON
    assert read_mcp(a)["mcpServers"]["mcp-sbt-shell"]["url"].endswith(f":{port}/mcp")
