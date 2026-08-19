from fastmcp import FastMCP

from .output import clean_output, safe_clean
from .sbt_session import SbtSession
from .token_counter import SavingsTracker, make_counter

mcp = FastMCP("mcp-sbt-shell")
sbt_session = None
_timeout = None
_aggressive = False
_collapse_success = False
_savings = None


async def main_async(
    sbt_executable: str,
    cwd: str,
    port: int,
    timeout: int,
    aggressive: bool,
    collapse_success: bool,
    count_tokens: bool,
):
    global sbt_session, _timeout, _aggressive, _collapse_success, _savings
    sbt_session = SbtSession(executable=sbt_executable, cwd=cwd)
    _timeout = timeout
    _aggressive = aggressive
    _collapse_success = collapse_success
    if count_tokens:
        count_fn, source = make_counter()
        _savings = SavingsTracker(count_fn, source)
    await sbt_session.start()
    try:
        await mcp.run_async(transport="streamable-http", port=port)
    except KeyboardInterrupt:
        pass
    finally:
        if sbt_session is not None and sbt_session.is_running():
            await sbt_session.stop()
        if _savings is not None:
            _savings.log_summary()


@mcp.tool()
async def sbt_execute(command: str, raw: bool) -> str:
    """Execute a command in the sbt shell.

    Output is filtered to reduce tokens: noise (control codes, progress redraws,
    the echoed command) is always stripped, and passing-suite chatter may be
    collapsed depending on the server's configuration. When content is removed a
    marker like "[N lines hidden — re-run with raw=true ...]" is appended.

    Args:
        command: The sbt command to execute
        raw: When true, return the unfiltered sbt output (use this to recover
            detail after a "hidden"/"collapsed" marker)
    """
    if not command:
        return "Error: Command is required"

    if sbt_session is None:
        raise RuntimeError("sbt session was not properly initialized")

    try:
        if not sbt_session.is_running():
            await sbt_session.restart()

        output = await sbt_session.execute(command, _timeout)
        returned = (
            output
            if raw
            else clean_output(
                output,
                command=command,
                aggressive=_aggressive,
                collapse_success_enabled=_collapse_success,
            )
        )
        if _savings is not None:
            _savings.record(command, output, returned)
        return returned
    except Exception as e:
        return safe_clean(f"Error occured, during command execution: {e!s}", command)
