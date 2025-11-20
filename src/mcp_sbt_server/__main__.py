"""CLI entry point for mcp-sbt-server."""

import argparse
import logging

from .server import main_sync

# Configure logging for CLI
logger = logging.getLogger("mcp_sbt_server.cli")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="MCP server for sbt shell management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Start server with default settings
  %(prog)s --host 0.0.0.0 --port 8080  # Start server on all interfaces, port 8080
  %(prog)s --port 9000               # Start server on localhost, port 9000
        """.strip(),
    )

    parser.add_argument("--host", default="localhost", help="Host to bind the server to (default: localhost)")

    parser.add_argument("--port", type=int, default=8093, help="Port to bind the server to (default: 8093)")

    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    return parser.parse_args()


def main():
    """Main entry point for the CLI."""
    args = parse_args()

    logger.info(f"Starting MCP SBT server with CLI args: host={args.host}, port={args.port}")

    # Start the server with the provided host and port
    main_sync(args.host, args.port)


if __name__ == "__main__":
    main()
