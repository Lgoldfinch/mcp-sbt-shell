# mcp-sbt-shell

An MCP server for executing commands in a persistent sbt shell session. It's a Python wrapper which aims to reduce SBT 
start up times and token usage.

Forked from https://github.com/mozhaa/mcp-sbt-shell. 

## How it works

It sends commands to sbt shell, then waits for byte sequence (`\x1b\x5b\x3f\x32\x30\x30\x34\x68\x3e\x2e\x2e\x2e\x2e`) 
that signals the end of command execution.

### How it saves tokens

- **Persistent session.** sbt stays running between commands, so you pay the
  slow, noisy JVM/sbt startup once instead of on every invocation — subsequent
  commands skip the boot banners and warm-up entirely.
- **Noise stripping (always on).** ANSI/control codes, carriage-return progress
  redraws, the echoed command, and prompt residue are removed before the output
  is returned. No message content is lost.
- **`--aggressive` filtering.** A ScalaTest-aware filter that drops noise, such as compilation status and test successes, 
  while keeping failure detail (`*** FAILED ***` blocks, assertion
  messages, `[error]`/`[warn]`) inline, so the model still sees *why* a test
  failed. On the failure path it also: drops framework/runtime stack frames
  (keeping the project frame that matters — see `--keep-frame-prefixes`),
  compacts project frames that repeat a source location (ScalaTest lifecycle
  overrides all report the test class's declaration line), deduplicates identical
  traces across failures (`(same trace as "…")`), prepends
  a one-line recompile-status header (`compiled: N sources` / `no recompile
  (cached)`) so you can tell a fresh result from a cached one, and strips the
  low-value `[info]` prefix.
- **`--collapse-success`.** A clean run collapses to a terse one-line summary
  plus any warnings.

Whenever content is dropped or collapsed, a marker is appended so the caller can
re-run with `raw=true` to recover the full log.

## Quick Start

### Installation

Clone this tool's repo, then either run it in the cloned directory or install a
global command:

```bash
git clone <repo-url> mcp-sbt-shell

# run it directly from within the project you're working on: 
uv run --project /path/to/topaz mcp-sbt-shell

# ...or install a global `mcp-sbt-shell` command (re-run after code changes)
uv tool install /path/to/mcp-sbt-shell
```

### Using sbt-mcp-up (Recommended)

The easiest way to run the server is with `sbt-mcp-up`, which automates port assignment and `.mcp.json` setup:

```bash
ln -s "$(pwd)/scripts/sbt-mcp-up.sh" ~/.local/bin/sbt-mcp-up
```

Then, in any Scala project:

```bash
sbt-mcp-up                                # start server for current project
sbt-mcp-up /path/to/project               # start server for another project
sbt-mcp-up --cwd /path/to/project         # same, using --cwd form
sbt-mcp-up --cwd /path/to/project --count-tokens   # with extra flags
```

The script assigns a **stable, unique port** (recorded in `~/.cache/mcp-sbt-shell/ports.json`), writes `.mcp.json` to configure Claude, and runs the server in the foreground with `--aggressive` and `--collapse-success` filters enabled by default. The port never changes across runs and no two projects share one.

### Manual Setup (Alternative)

Once installed with `uv tool install`, start the server directly with:

```bash
mcp-sbt-shell
```

By default it runs `sbt` from your `PATH`. To build a specific project rather than the current
directory, add `--cwd /path/to/your/scala-project`.

### Custom Options

- `--sbt-executable`: sbt executable path (default: `sbt`)
- `--cwd`: Working directory (default: current directory)  
- `--port`: Server port (default: `8080`)
- `--timeout`: Command timeout in seconds (default: `30`)
- `--aggressive`: ScalaTest-aware filtering — keep failure detail (`*** FAILED ***`
  blocks, assertion messages, `[error]`/`[warn]`), drop passing-suite chatter (off
  by default)
- `--collapse-success`: collapse a successful run to a terse one-line summary (off
  by default)
- `--keep-frame-prefixes`: comma-separated class prefixes whose stack frames are
  always kept in `--aggressive` mode, even if they match a framework package
  (e.g. `com.topaz.`). Framework frames (`org.scalatest`/`scala.`/`java.`/`jdk.`/`sbt.`)
  are dropped by default; everything else is kept, so this is only needed to
  force-keep a frame that would otherwise be treated as framework noise. Empty by
  default.
- `--count-tokens`: testing aid — log per-call and cumulative token savings to
  stderr (off by default). Uses Anthropic's `count_tokens` when
  `ANTHROPIC_API_KEY` is set, otherwise a rough `char/4` proxy.

## Connecting to Claude

This server runs over **HTTP**, so Claude does not spawn it — you start it yourself and point Claude at its URL.

1. In your repo of choice, start the server, using `uv run ...` or `mcp-sbt-shell`, with the required args.  

2. Register it with Claude Code:

   ```bash
   claude mcp add --transport http sbt-shell 127.0.0.1://localhost:<port>/mcp
   ```

   Add `--scope project` to write a shared `.mcp.json` in the repo, or
   `--scope user` to make it available across all your projects. Then run `/mcp`
   in a Claude Code session to confirm `sbt-shell` is connected and `sbt_execute`
   is listed.

The server must be running before Claude uses it and must stay running.
Restarting it drops the sbt session; Claude simply reconnects to the URL.

### Running Multiple Servers

If you need to run multiple `sbt-mcp-up` instances (one per project), run each in its own terminal. See the sbt-mcp-up section above for setup details.

If you change a project's port manually, reconnect in Claude Code — run `/mcp` and reconnect `mcp-sbt-shell`, or restart the session, since Claude caches the `.mcp.json` URL at session start.

**Note:** `sbt-mcp-up` uses `127.0.0.1` rather than `localhost` so it isn't intercepted on macOS, where `localhost` prefers IPv6 and other processes (e.g. Docker) may be bound there.

## Development

```bash
uv sync                              # install deps (incl. pytest, anthropic)
uv run pytest                        # run the output-filter test suite
uv run ruff check                    # lint
uv run python -m tests.eval_tokens   # token-savings report per filter mode
```

The eval harness counts real tokens when `ANTHROPIC_API_KEY` is set in the
environment, otherwise it falls back to a rough `char/4` proxy (labelled in its
output):

```bash
ANTHROPIC_API_KEY=sk-ant-... uv run python -m tests.eval_tokens
```

## Prerequisites

- Python 3.11+
- sbt installed and in PATH
- Scala project with `build.sbt` in the working directory