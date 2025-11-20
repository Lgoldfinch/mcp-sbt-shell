# MCP SBT Server

An MCP (Model Context Protocol) server that provides access to an sbt shell for executing Scala build commands.

## Features

- Persistent sbt shell process for efficient command execution
- Automatic sbt process management (start, restart, cleanup)
- 30-second command timeout with clear error handling
- Output truncation to 100 lines with middle cuts for large outputs
- Clean sbt output with `--no-colors --supershell=false` flags
- Three MCP tools:
  - `execute_sbt_command`: Execute sbt commands
  - `get_sbt_status`: Check sbt process status
  - `restart_sbt`: Restart the sbt shell

## Installation

### Using uv (recommended)

```bash
# Clone or navigate to the project directory
cd mcp-sbt-server

# Install dependencies
uv sync

# Install development dependencies
uv sync --dev
```

### Using pip

```bash
# Install dependencies
pip install mcp

# Install development dependencies  
pip install ruff
```

## Usage

### Running the Server

```bash
# Using uv
uv run python -m mcp_sbt_server

# Using python directly
python -m src.mcp_sbt_server.server
```

### MCP Configuration

Add the server to your MCP settings configuration file:

```json
{
  "mcpServers": {
    "sbt": {
      "command": "uv",
      "args": ["run", "python", "-m", "mcp_sbt_server"],
      "cwd": "/path/to/your/scala/project"
    }
  }
}
```

Or if using python directly:

```json
{
  "mcpServers": {
    "sbt": {
      "command": "python",
      "args": ["-m", "mcp_sbt_server"],
      "cwd": "/path/to/your/scala/project"
    }
  }
}
```

## Available Tools

### execute_sbt_command

Execute a command in the sbt shell.

Parameters:
- `command` (string, required): The sbt command to execute

Example:
```json
{
  "name": "execute_sbt_command",
  "arguments": {
    "command": "compile"
  }
}
```

### get_sbt_status

Check the status of the sbt process.

Parameters: None

Returns information about whether sbt is running and ready to accept commands.

### restart_sbt

Restart the sbt shell process.

Parameters: None

Useful if the sbt process becomes unresponsive or crashes.

## Development

### Code Quality

The project uses ruff for linting and formatting:

```bash
# Check for linting issues
uv run ruff check .

# Format code
uv run ruff format .
```

### Project Structure

```
mcp-sbt-server/
├── pyproject.toml          # Project configuration and dependencies
├── .gitignore             # Git ignore file
├── README.md              # This file
└── src/
    └── mcp_sbt_server/
        ├── __init__.py    # Package initialization
        ├── server.py      # MCP server implementation
        └── sbt_manager.py # SBT process management
```

## Configuration

The server can be configured through environment variables:

- Working directory: Set by the `cwd` field in MCP configuration
- Command timeout: Fixed at 30 seconds
- SBT flags: Fixed to `--no-colors --supershell=false`

## Troubleshooting

### SBT not found
Ensure sbt is installed and available in the system PATH, or provide the full path to sbt in your environment.

### Permission issues
Make sure the server has permission to execute sbt and access the project directory.

### Process hanging
If sbt becomes unresponsive, use the `restart_sbt` tool to restart the process.

## License

This project is provided as-is for use with MCP-enabled tools.
