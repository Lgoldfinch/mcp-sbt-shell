"""CLI entry point for mcp-sbt-server."""

import argparse
import os

from .server import main_sync


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="MCP server for sbt shell management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Use default sbt in current directory
  %(prog)s --sbt-executable /usr/local/bin/sbt  # Use custom SBT executable
  %(prog)s --sbt-executable sbt.bat            # Use sbt.bat on Windows
  %(prog)s --workdir /path/to/project          # Run sbt commands in specific directory
  %(prog)s --workdir ./my-scala-project        # Run sbt commands in relative directory
        """,
    )

    parser.add_argument(
        "--sbt-executable",
        type=str,
        default="sbt.bat",
        help="Path to the SBT executable (e.g., sbt, sbt.bat, or full path to executable)",
    )

    parser.add_argument(
        "--workdir",
        type=str,
        default=os.getcwd(),
        help="Working directory where sbt commands will be executed (default: current directory)",
    )

    return parser.parse_args()


def main():
    """Main entry point for the CLI."""
    args = parse_arguments()

    # Start the server with parsed arguments
    main_sync(sbt_executable=args.sbt_executable, workdir=args.workdir)


if __name__ == "__main__":
    main()
