"""CLI entry point for mcp-sbt-server."""

import logging

from .server import main_sync

# Configure logging for CLI
logger = logging.getLogger("mcp_sbt_server.cli")


def main():
    """Main entry point for the CLI."""
    logger.info("Starting MCP SBT server")

    # Start the server
    main_sync()


if __name__ == "__main__":
    main()
