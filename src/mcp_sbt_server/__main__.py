import argparse
import asyncio
import os

from .server import main_async


def parse_args():
    parser = argparse.ArgumentParser(description="MCP server for sbt shell management")

    parser.add_argument(
        "--sbt-executable",
        type=str,
        default="sbt.bat",
        help="path to the sbt executable",
    )

    parser.add_argument(
        "--cwd",
        type=str,
        default=os.getcwd(),
        help="working directory where sbt commands will be executed",
    )

    return parser.parse_args()


def main():
    """Main entry point for the CLI."""
    args = parse_args()
    asyncio.run(main_async(sbt_executable=args.sbt_executable, cwd=args.cwd))


if __name__ == "__main__":
    main()
