import argparse
import asyncio
import os

from .server import main_async


def parse_args():
    parser = argparse.ArgumentParser(description="MCP server for executing commands in sbt shell")

    parser.add_argument(
        "--sbt-executable",
        type=str,
        default="sbt",
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

    parser.add_argument(
        "--aggressive",
        action="store_true",
        help="ScalaTest-aware filter: keep failure detail, drop passing-suite chatter",
    )

    parser.add_argument(
        "--collapse-success",
        action="store_true",
        help="collapse a successful run to a terse one-line summary",
    )

    parser.add_argument(
        "--count-tokens",
        action="store_true",
        help="testing aid: log per-call and cumulative token savings to stderr "
        "(uses Anthropic count_tokens when ANTHROPIC_API_KEY is set, else char/4 proxy)",
    )

    return parser.parse_args()


def main():
    """Main entry point for the CLI."""
    args = parse_args()
    asyncio.run(
        main_async(
            sbt_executable=args.sbt_executable,
            cwd=args.cwd,
            port=args.port,
            timeout=args.timeout,
            aggressive=args.aggressive,
            collapse_success=args.collapse_success,
            count_tokens=args.count_tokens,
        )
    )


if __name__ == "__main__":
    main()
