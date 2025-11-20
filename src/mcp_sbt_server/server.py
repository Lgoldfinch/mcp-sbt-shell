import logging
import signal
import sys
from pathlib import Path

from fastmcp import FastMCP

from .sbt_manager import SbtManager

logger = logging.getLogger("mcp_sbt_server")

# Initialize FastMCP server
mcp = FastMCP("mcp-sbt-server")

# Global SBT manager instance
sbt_manager = None


def setup_logging(log_file=None, log_level="INFO"):
    """Configure logging with optional file output and custom level.

    Args:
        log_file: Optional path to log file. If None, logs to stderr only.
        log_level: Logging level as string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Clear any existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Always add stderr handler
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    root_logger.addHandler(stderr_handler)

    # Add file handler if log_file is specified
    if log_file:
        try:
            # Create directory if it doesn't exist
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            # Create file handler with append mode
            file_handler = logging.FileHandler(log_file, mode="a")
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

            logger.info(f"Logging to file: {log_file}")
        except Exception as e:
            logger.error(f"Failed to set up file logging to {log_file}: {e}")
            # Continue with stderr-only logging

    # Set the logging level
    root_logger.setLevel(numeric_level)

    logger.info(f"Logging configured at level: {log_level}")


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


def main_sync(log_file=None, log_level="INFO", sbt_executable=None):
    """Synchronous entry point for the script.

    Args:
        log_file: Optional path to log file for output
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        sbt_executable: Optional path to SBT executable
    """
    global sbt_manager

    # Setup logging first
    setup_logging(log_file=log_file, log_level=log_level)

    # Initialize SBT manager with provided executable
    sbt_manager = SbtManager(sbt_path=sbt_executable)
    logger.info(f"Initialized SBT manager with executable: {sbt_executable or 'sbt'}")

    logger.info("Starting MCP SBT server")
    setup_signal_handlers()

    mcp.run(transport="stdio")
