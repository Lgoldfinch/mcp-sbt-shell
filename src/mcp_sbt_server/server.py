import asyncio
import sys

from fastmcp import FastMCP

from .sbt_session import SbtSession

# Initialize FastMCP server
mcp = FastMCP("mcp-sbt-server")

# Global SBT session instance
sbt_session = None


async def main_async(sbt_executable: str, workdir: str):
    """Async entry point for the script.

    Args:
        sbt_executable: Optional path to SBT executable
        workdir: Optional working directory where sbt commands will be executed
    """
    global sbt_session

    # Initialize SBT session with provided executable and workdir
    sbt_session = SbtSession(executable=sbt_executable, cwd=workdir)

    # Start SBT session - if this fails, server doesn't start
    await sbt_session.start()

    # Run MCP server
    await mcp.run_async(transport="stdio")


@mcp.tool()
async def execute_sbt_command(command: str) -> str:
    """Execute a command in the sbt shell.

    Args:
        command: The sbt command to execute
    """
    if not command:
        return "Error: Command is required"

    try:
        # Check if SBT process is still running
        if not sbt_session._is_process_running():
            # If SBT died, the server should terminate too
            print("SBT process has died, terminating server", file=sys.stderr)
            sys.exit(1)

        output = await sbt_session.execute(command)
        return output
    except Exception as e:
        # If there's an error executing command, check if process died
        if not sbt_session._is_process_running():
            print("SBT process has died during command execution, terminating server", file=sys.stderr)
            sys.exit(1)
        return f"Failed to execute command: {e!s}"


# Keep a synchronous wrapper for compatibility with the entry point
def main_sync(sbt_executable: str, workdir: str):
    """Synchronous wrapper for the async main."""
    try:
        asyncio.run(main_async(sbt_executable=sbt_executable, workdir=workdir))
    except KeyboardInterrupt:
        if sbt_session and sbt_session._is_process_running():
            asyncio.run(sbt_session.stop())
        sys.exit(0)
