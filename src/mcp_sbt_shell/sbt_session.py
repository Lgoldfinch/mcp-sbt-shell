import asyncio


class SbtSession:
    def __init__(self, executable: str, cwd: str) -> None:
        self.executable = executable
        self.cwd = cwd
        self.process: asyncio.subprocess.Process | None = None
        self.prompt = b"\x1b\x5b\x3f\x32\x30\x30\x34\x68\x3e\x2e\x2e\x2e\x2e"

    async def start(self) -> None:
        self.process = await asyncio.create_subprocess_exec(
            self.executable,
            "--no-colors",
            "--supershell=false",
            cwd=self.cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            bufsize=0,
        )
        await self._wait_for_prompt(timeout=60)

    def is_running(self) -> bool:
        return self.process is not None and self.process.returncode is None

    async def _wait_for_prompt(self, timeout: int) -> str:
        buffer = b""
        prompt_len = len(self.prompt)
        loop = asyncio.get_event_loop()
        end_time = loop.time() + timeout

        while self.is_running():
            try:
                remaining_time = end_time - loop.time()
                if remaining_time <= 0:
                    raise asyncio.TimeoutError()

                data = await asyncio.wait_for(self.process.stdout.read(4096), timeout=remaining_time)
                if not data:
                    break
                buffer += data

                if buffer[-prompt_len:] == self.prompt:
                    return buffer[:-prompt_len].decode("utf-8", errors="replace")

            except (asyncio.TimeoutError, TimeoutError):
                break

        await asyncio.sleep(1)
        output = buffer.decode("utf-8", errors="replace")
        if not self.is_running():
            raise RuntimeError(
                f"process terminated with return code: {self.process.returncode}.\n\nsbt output:\n" + output
            )
        raise TimeoutError(f"no prompt detected within {timeout} seconds.\n\nsbt output:\n" + output)

    async def _send_command(self, command: str) -> None:
        if not self.is_running():
            raise RuntimeError("sbt process is not running")
        try:
            encoded_command = command.encode("ascii")
        except Exception as e:
            raise ValueError("command must contain only ascii characters") from e

        self.process.stdin.write(encoded_command + b"\n")
        await self.process.stdin.drain()

    async def execute(self, command: str, timeout: int) -> str:
        await self._send_command(command)
        return await self._wait_for_prompt(timeout)

    async def stop(self) -> None:
        if not self.is_running():
            return

        await self._send_command("exit")
        try:
            await asyncio.wait_for(self.process.wait(), timeout=2)
        except asyncio.TimeoutError:
            pass

        if self.is_running():
            self.process.terminate()
            await self.process.wait()

    async def restart(self) -> None:
        await self.stop()
        await self.start()
