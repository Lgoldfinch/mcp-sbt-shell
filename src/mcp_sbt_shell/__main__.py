import argparse
import asyncio
import os

from .server import main_async


def parse_args():
    parser = argparse.ArgumentParser(description="MCP server for executing commands in sbt shell")

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

    parser.add_argument("-p", "--port", type=int, default="8080", help="port to use")

    parser.add_argument("-T", "--timeout", type=int, default=30, help="sbt_execute timeout")

    return parser.parse_args()


def main():
    """Main entry point for the CLI."""
    args = parse_args()
    asyncio.run(main_async(sbt_executable=args.sbt_executable, cwd=args.cwd, port=args.port, timeout=args.timeout))


if __name__ == "__main__":
    main()
