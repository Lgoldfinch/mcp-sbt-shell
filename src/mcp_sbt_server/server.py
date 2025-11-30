from fastmcp import FastMCP

from .sbt_session import SbtSession

mcp = FastMCP("mcp-sbt-server")
sbt_session = None
_timeout = None


async def main_async(sbt_executable: str, cwd: str, port: int, timeout: int):
    global sbt_session, _timeout
    sbt_session = SbtSession(executable=sbt_executable, cwd=cwd)
    _timeout = timeout
    await sbt_session.start()
    try:
        await mcp.run_async(transport="streamable-http", port=port)
    except KeyboardInterrupt:
        if sbt_session is not None and sbt_session.is_running():
            await sbt_session.stop()


@mcp.tool()
async def sbt_execute(command: str) -> str:
    """Execute a command in the sbt shell.

    Args:
        command: The sbt command to execute
    """
    if not command:
        return "Error: Command is required"

    if sbt_session is None:
        raise RuntimeError("sbt session was not properly initialized")

    try:
        if not sbt_session.is_running():
            await sbt_session.restart()

        output = await sbt_session.execute(command, _timeout)
        return output
    except Exception as e:
        return f"Error occured, during command execution: {e!s}"
