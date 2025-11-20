import logging
import signal
import sys

from fastmcp import FastMCP

from .sbt_manager import SbtManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("mcp_sbt_server")

# Initialize FastMCP server
mcp = FastMCP("mcp-sbt-server")

# Global SBT manager instance
sbt_manager = SbtManager()


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    logger.info("Setting up signal handlers for graceful shutdown")

    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully")
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
    logger.info(f"Executing SBT command: {command}")

    if not command:
        logger.warning("Empty command received")
        return "Error: Command is required"

    try:
        if not sbt_manager.is_running():
            logger.info("SBT not running, starting it")
            sbt_manager.start()

        output = sbt_manager.execute_command(command)
        logger.info(f"SBT command executed successfully: {command}")
        return output
    except Exception as e:
        logger.error(f"Failed to execute SBT command '{command}': {e}")
        return f"Failed to execute command: {e!s}"


@mcp.tool()
def get_sbt_status() -> str:
    """Check the status of the sbt process."""
    logger.debug("Checking SBT status")
    is_running = sbt_manager.is_running()
    is_ready = sbt_manager.is_ready()

    status_text = "SBT Status:\n"
    status_text += f"Running: {is_running}\n"
    status_text += f"Ready: {is_ready}\n"

    if not is_running:
        status_text += "SBT process is not running"
        logger.info("SBT process is not running")
    elif not is_ready:
        status_text += "SBT process is starting up..."
        logger.info("SBT process is starting up")
    else:
        status_text += "SBT process is ready to accept commands"
        logger.info("SBT process is ready to accept commands")

    return status_text


@mcp.tool()
def restart_sbt() -> str:
    """Restart the sbt shell process."""
    logger.info("Restarting SBT process")
    try:
        sbt_manager.restart()
        logger.info("SBT process restarted successfully")
        logger.info("SBT process restarted successfully")
        return "SBT process restarted successfully"
    except Exception as e:
        logger.error(f"Failed to restart SBT: {e}")
        return f"Failed to restart SBT: {e!s}"


def main_sync(host: str, port: int):
    """Synchronous entry point for the script.

    Args:
        host: Host to bind the server to
        port: Port to bind the server to
    """
    logger.info(f"Starting MCP SBT server with host={host}, port={port}")
    setup_signal_handlers()

    mcp.run(transport="streamable-http", host=host, port=port)
