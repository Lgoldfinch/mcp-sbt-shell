#!/usr/bin/env bash
#
# Start an sbt-shell MCP server for a single worktree and register it in that
# worktree's .mcp.json.
#
# One server = one port = one worktree. Run this once per worktree (each in its
# own terminal); it assigns the worktree a stable, unique port (tracked in
# ~/.cache/mcp-sbt-shell/ports.json), writes/updates <worktree>/.mcp.json to
# point at it, then runs the server in the foreground (Ctrl-C to stop). A given
# worktree always gets the same port and no two worktrees share one.
#
# The worktree can be given as a bare directory OR with --cwd DIR / --cwd=DIR.
# Any other flags are passed straight through to the server (a leading -- is
# optional). --aggressive and --collapse-success are applied by default.
#
# To run it from any worktree as a bare command, symlink it onto your PATH once:
#   ln -s "$(pwd)/scripts/sbt-mcp-up.sh" ~/.local/bin/sbt-mcp-up
# then `sbt-mcp-up` (no path) starts a server for the current directory.
#
# Usage:
#   scripts/sbt-mcp-up.sh                        # server for the current directory
#   scripts/sbt-mcp-up.sh /path/to/wt            # server for another worktree
#   scripts/sbt-mcp-up.sh --cwd /path/to/wt      # same, --cwd form
#   scripts/sbt-mcp-up.sh /path/to/wt --count-tokens   # extra server flags
#   scripts/sbt-mcp-up.sh /path/to/wt -- --timeout 60  # -- also works
#
# Env:
#   SBT_EXECUTABLE   sbt binary to use (default: sbt)
#
set -euo pipefail

# Resolve symlinks so REPO is correct even when this script is invoked through a
# symlink on PATH (e.g. ~/.local/bin/sbt-mcp-up -> .../scripts/sbt-mcp-up.sh).
SOURCE="${BASH_SOURCE[0]}"
while [[ -h "$SOURCE" ]]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ "$SOURCE" != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
REPO="$(dirname "$SCRIPT_DIR")"
SBT="${SBT_EXECUTABLE:-sbt}"

# Pull the worktree out of the args (bare dir or --cwd DIR / --cwd=DIR); pass
# everything else through to the server.
WORKTREE=""
PASS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --) shift; PASS+=("$@"); break ;;
    --cwd) WORKTREE="$2"; shift 2 ;;
    --cwd=*) WORKTREE="${1#--cwd=}"; shift ;;
    *)
      # A path-like arg (contains "/", or starts with "." or "/") is meant to be
      # the worktree; capture it and let the directory check below validate it,
      # rather than silently passing a mistyped path through to the server.
      if [[ -z "$WORKTREE" && ( -d "$1" || "$1" == */* || "$1" == .* || "$1" == /* ) ]]; then
        WORKTREE="$1"; shift
      else
        PASS+=("$1"); shift
      fi
      ;;
  esac
done
[[ -z "$WORKTREE" ]] && WORKTREE="$PWD"
if [[ ! -d "$WORKTREE" ]]; then
  echo "[sbt-mcp-up] error: worktree is not a directory: $WORKTREE" >&2
  exit 1
fi
WORKTREE="$(cd "$WORKTREE" && pwd)"

# Assign this worktree a stable, globally-unique port and write it into the
# worktree's .mcp.json. The allocator lives in a sibling Python file rather than
# an inline heredoc because macOS ships bash 3.2, whose parser mishandles a
# here-document embedded in $(...) command substitution.
PORT="$(python3 "$SCRIPT_DIR/sbt-mcp-up-port.py" "$WORKTREE")"

echo "[sbt-mcp-up] worktree : $WORKTREE" >&2
echo "[sbt-mcp-up] port     : $PORT" >&2
echo "[sbt-mcp-up] starting server (Ctrl-C to stop) ..." >&2
echo "[sbt-mcp-up] in Claude Code for this worktree, run /mcp and enable mcp-sbt-shell" >&2

exec uv run --project "$REPO" mcp-sbt-shell \
  --sbt-executable "$SBT" \
  --cwd "$WORKTREE" \
  --port "$PORT" \
  --aggressive \
  --collapse-success \
  ${PASS[@]+"${PASS[@]}"}
