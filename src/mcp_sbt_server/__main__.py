"""CLI entry point for mcp-sbt-server."""

import argparse
import sys
from .server import main_sync


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

    parser.add_argument("--port", type=int, default=None, help="Port to bind the server to (default: MCP default port)")

    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    return parser.parse_args()


def main():
    """Main entry point for the CLI."""
    args = parse_args()

    # Note: FastMCP currently doesn't support host/port configuration
    # These arguments are kept for future compatibility and documentation
    if args.host != "localhost" or args.port is not None:
        print("Note: FastMCP currently uses default host/port configuration.")
        print(f"Requested host: {args.host}, port: {args.port}")
        print("Server will start with MCP defaults.")

    # Start the server
    main_sync()


if __name__ == "__main__":
    main()
