import asyncio
import signal
import sys
from typing import Any, Dict

from mcp.server import FastMCP

from .sbt_manager import SbtManager

# Initialize FastMCP server
mcp = FastMCP("mcp-sbt-server")

# Global SBT manager instance
sbt_manager = SbtManager()

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        sbt_manager.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


@mcp.tool()
def execute_sbt_command(command: str) -> str:
    """Execute a command in the sbt shell.
    
    Args:
        command: The sbt command to execute
    """
    if not command:
        return "Error: Command is required"

    try:
        if not sbt_manager.is_running():
            sbt_manager.start()

        output = sbt_manager.execute_command(command)
        return output
    except Exception as e:
        return f"Failed to execute command: {e!s}"


@mcp.tool()
def get_sbt_status() -> str:
    """Check the status of the sbt process."""
    is_running = sbt_manager.is_running()
    is_ready = sbt_manager.is_ready()

    status_text = "SBT Status:\n"
    status_text += f"Running: {is_running}\n"
    status_text += f"Ready: {is_ready}\n"

    if not is_running:
        status_text += "SBT process is not running"
    elif not is_ready:
        status_text += "SBT process is starting up..."
    else:
        status_text += "SBT process is ready to accept commands"

    return status_text


@mcp.tool()
def restart_sbt() -> str:
    """Restart the sbt shell process."""
    try:
        sbt_manager.restart()
        return "SBT process restarted successfully"
    except Exception as e:
        return f"Failed to restart SBT: {e!s}"


def main_sync():
    """Synchronous entry point for the script."""
    setup_signal_handlers()
    mcp.run()


if __name__ == "__main__":
    main_sync()
