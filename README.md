# mcp-sbt-shell

An MCP server for executing commands in a persistent sbt shell session.

## Quick Start

### Installation

```bash
pip install mcp-sbt-shell
```

### Basic Usage

Start the server with default settings:

```bash
mcp_sbt_shell
```

### Custom Options

- `--sbt-executable`: sbt executable path (default: `sbt.bat`)
- `--cwd`: Working directory (default: current directory)  
- `--port`: Server port (default: `8080`)
- `--timeout`: Command timeout in seconds (default: `30`)

## Tools

### `sbt_execute`

Execute commands in a persistent sbt shell session. This tool maintains a long-running sbt process to avoid startup overhead and provides direct access to sbt's build capabilities.

**Parameters:**
- `command` (string) - Required. The sbt command to execute (e.g., "compile", "test", "run")

**Returns:**
- `output` (string) - The complete output from the sbt command execution, including any compilation messages, test results, or error information.

The tool will execute the command in the configured sbt session and return the full output, making it suitable for compiling code, running tests, packaging applications, or any other sbt task supported by your project's build configuration.

## How it works

It sends command to sbt shell, then waits for byte sequence (`\x1b\x5b\x3f\x32\x30\x30\x34\x68\x3e\x2e\x2e\x2e\x2e`) that signals the end of command execution (tested on Windows with `sbt.bat`).

## Prerequisites

- Python 3.11+
- sbt installed and in PATH
- Scala project with `build.sbt` in the working directory