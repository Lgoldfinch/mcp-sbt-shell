import asyncio
import signal
import sys
from typing import Any, Dict, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    ErrorCode,
    ListToolsRequest,
    McpError,
)

from .sbt_manager import SbtManager


class SbtServer:
    def __init__(self):
        self.server = Server("mcp-sbt-server", version="0.1.0")
        self.sbt_manager = SbtManager()
        self.setup_handlers()
        self.setup_signal_handlers()

    def setup_handlers(self):
        self.server.setRequestHandler(ListToolsRequest, self.list_tools)
        self.server.setRequestHandler(CallToolRequest, self.call_tool)

    def setup_signal_handlers(self):
        def signal_handler(signum, frame):
            self.sbt_manager.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def list_tools(self) -> Dict[str, Any]:
        return {
            "tools": [
                {
                    "name": "execute_sbt_command",
                    "description": "Execute a command in the sbt shell",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"command": {"type": "string", "description": "The sbt command to execute"}},
                        "required": ["command"],
                    },
                },
                {
                    "name": "get_sbt_status",
                    "description": "Check the status of the sbt process",
                    "inputSchema": {"type": "object", "properties": {}, "required": []},
                },
                {
                    "name": "restart_sbt",
                    "description": "Restart the sbt shell process",
                    "inputSchema": {"type": "object", "properties": {}, "required": []},
                },
            ]
        }

    async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            if name == "execute_sbt_command":
                return await self.execute_sbt_command(arguments or {})
            elif name == "get_sbt_status":
                return await self.get_sbt_status(arguments or {})
            elif name == "restart_sbt":
                return await self.restart_sbt(arguments or {})
            else:
                raise McpError(ErrorCode.MethodNotFound, f"Unknown tool: {name}")
        except Exception as e:
            return {"content": [{"type": "text", "text": f"Error: {e!s}"}], "isError": True}

    async def execute_sbt_command(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        command = arguments.get("command")
        if not command:
            raise McpError(ErrorCode.InvalidParams, "Command is required")

        try:
            if not self.sbt_manager.is_running():
                self.sbt_manager.start()

            output = self.sbt_manager.execute_command(command)
            return {"content": [{"type": "text", "text": output}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"Failed to execute command: {e!s}"}], "isError": True}

    async def get_sbt_status(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        is_running = self.sbt_manager.is_running()
        is_ready = self.sbt_manager.is_ready()

        status_text = "SBT Status:\n"
        status_text += f"Running: {is_running}\n"
        status_text += f"Ready: {is_ready}\n"

        if not is_running:
            status_text += "SBT process is not running"
        elif not is_ready:
            status_text += "SBT process is starting up..."
        else:
            status_text += "SBT process is ready to accept commands"

        return {"content": [{"type": "text", "text": status_text}]}

    async def restart_sbt(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        try:
            self.sbt_manager.restart()
            return {"content": [{"type": "text", "text": "SBT process restarted successfully"}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"Failed to restart SBT: {e!s}"}], "isError": True}

    async def run(self):
        async with stdio_server() as streams:
            await self.server.run(streams[0], streams[1], self.server.create_initialization_options())


async def main():
    server = SbtServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
