"""CLI entry point for mcp-sbt-server."""

import argparse
import logging

from .server import main_sync

# Configure logging for CLI
logger = logging.getLogger("mcp_sbt_server.cli")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="MCP server for sbt shell management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Log to stderr only, INFO level
  %(prog)s --log-file server.log              # Log to file, INFO level
  %(prog)s --log-level DEBUG                  # Log to stderr, DEBUG level
  %(prog)s --log-file server.log --log-level DEBUG  # Both file and DEBUG level
  %(prog)s --sbt-executable /usr/local/bin/sbt  # Use custom SBT executable
  %(prog)s --sbt-executable sbt.bat            # Use sbt.bat on Windows
        """,
    )

    parser.add_argument("--log-file", type=str, help="Path to log file for output (logs to stderr if not specified)")

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set logging level (default: INFO)",
    )

    parser.add_argument(
        "--sbt-executable",
        type=str,
        help="Path to the SBT executable (e.g., sbt, sbt.bat, or full path to executable)",
    )

    return parser.parse_args()


def main():
    """Main entry point for the CLI."""
    args = parse_arguments()

    logger.info("Starting MCP SBT server")

    # Start the server with parsed arguments
    main_sync(log_file=args.log_file, log_level=args.log_level, sbt_executable=args.sbt_executable)


if __name__ == "__main__":
    main()
