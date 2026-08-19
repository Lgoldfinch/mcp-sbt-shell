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
  failed.
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

See section Multiple mcp-sbt-shells section for details on the quickest way to get mcp sbt servers up and running.  

### Basic Usage

Once installed with `uv tool install`, start the server with default settings:

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
- `--count-tokens`: testing aid — log per-call and cumulative token savings to
  stderr (off by default). Uses Anthropic's `count_tokens` when
  `ANTHROPIC_API_KEY` is set, otherwise a rough `char/4` proxy.

## Connecting to Claude

This server runs over **HTTP**, so Claude does not spawn it — you start it yourself and point Claude at its URL.

1. In your repo of choice, start the server, using `uv run ...` or `mcp-sbt-shell`, with the required args.  

2. Register it with Claude Code:

   ```bash
   claude mcp add --transport http sbt-shell http://localhost:<port>/mcp
   ```

   Add `--scope project` to write a shared `.mcp.json` in the repo, or
   `--scope user` to make it available across all your projects. Then run `/mcp`
   in a Claude Code session to confirm `sbt-shell` is connected and `sbt_execute`
   is listed.

The server must be running before Claude uses it and must stay running.
Restarting it drops the sbt session; Claude simply reconnects to the URL.

### Multiple mcp-sbt-shells

Each server is bound to one `--cwd` and one port, so run **one server per
project**, each on its own port. `scripts/sbt-mcp-up.sh` automates this: it
assigns the project a **stable, unique port** (recorded in a small registry at
`~/.cache/mcp-sbt-shell/ports.json`), writes `<project>/.mcp.json` to point at
`http://127.0.0.1:<port>/mcp`, then runs the server in the foreground. The port
never changes across runs and no two projects share one, so a project's Claude
session always reaches its own server.

> If you change a project's port (e.g. from an older version that reused ports),
> reconnect in Claude Code — run `/mcp` and reconnect `mcp-sbt-shell`, or restart
> the session. Claude caches the `.mcp.json` URL at session start and won't pick
> up a changed port on its own.

To run it from any project without typing the repo path, symlink it onto your
`PATH` once (the script resolves the symlink to find its repo):

```bash
ln -s "$(pwd)/scripts/sbt-mcp-up.sh" ~/.local/bin/sbt-mcp-up
```

Then, in any project:

```bash
sbt-mcp-up                        # server for the current project
sbt-mcp-up /path/to/project            # another project (bare dir)
sbt-mcp-up --cwd /path/to/project      # another project (--cwd form)
sbt-mcp-up /path/to/project --count-tokens   # extra server flags
```

(Without the symlink, invoke it as `scripts/sbt-mcp-up.sh` from the repo, or by
its full path from anywhere.)

The project can be a bare directory or `--cwd DIR`; any other flags are passed
straight through to the server (a leading `--` is optional). `--aggressive` and
`--collapse-success` are applied by default, so you don't need to repeat them.
For accurate `--count-tokens` counts, export `ANTHROPIC_API_KEY` first.

Run it once per project (each in its own terminal), then `/mcp` in that
project's Claude Code session and enable `mcp-sbt-shell`. It uses `127.0.0.1`
rather than `localhost` so it isn't intercepted on macOS, where `localhost`
prefers IPv6 and other processes (e.g. Docker) may be bound there.

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