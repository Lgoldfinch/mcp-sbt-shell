import os
import subprocess
import threading
import time
from typing import List, Optional


class SbtManager:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.process: Optional[subprocess.Popen] = None
        self.ready = False
        self._lock = threading.Lock()
        self._output_buffer = []
        self._ready_event = threading.Event()

    def start(self) -> None:
        with self._lock:
            if self.process and self.process.poll() is None:
                return

            self.process = subprocess.Popen(
                ["sbt", "--no-colors", "--supershell=false"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=os.getcwd(),
                bufsize=1,
                universal_newlines=True,
            )

            self.ready = False
            self._ready_event.clear()
            threading.Thread(target=self._monitor_startup, daemon=True).start()

    def _monitor_startup(self) -> None:
        if not self.process:
            return

        while True:
            line = self.process.stdout.readline()
            if not line:
                break

            if line.strip().endswith(">"):
                self.ready = True
                self._ready_event.set()
                break

    def stop(self) -> None:
        with self._lock:
            if self.process and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            self.process = None
            self.ready = False

    def execute_command(self, command: str) -> str:
        if not self._ready_event.wait(timeout=10):
            raise RuntimeError("SBT not ready within timeout")

        with self._lock:
            if not self.process or self.process.poll() is not None:
                raise RuntimeError("SBT process not running")

            try:
                self.process.stdin.write(command + "\n")
                self.process.stdin.flush()

                output_lines = []
                start_time = time.time()

                while time.time() - start_time < self.timeout:
                    line = self.process.stdout.readline()
                    if not line:
                        if self.process.poll() is not None:
                            raise RuntimeError("SBT process died during command execution")
                        continue

                    output_lines.append(line.rstrip("\n\r"))

                    if line.strip().endswith(">"):
                        break

                else:
                    raise RuntimeError(f"Command timed out after {self.timeout} seconds")

                return self._truncate_output(output_lines)

            except Exception:
                if self.process and self.process.poll() is not None:
                    self.ready = False
                    self._ready_event.clear()
                raise

    def _truncate_output(self, lines: List[str], max_lines: int = 100) -> str:
        if len(lines) <= max_lines:
            return "\n".join(lines)

        keep_start = max_lines // 2
        keep_end = max_lines - keep_start - 1

        result = lines[:keep_start]
        result.append(f"... [{len(lines) - max_lines} lines truncated] ...")
        result.extend(lines[-keep_end:])

        return "\n".join(result)

    def is_running(self) -> bool:
        with self._lock:
            return self.process is not None and self.process.poll() is None

    def is_ready(self) -> bool:
        return self.ready and self.is_running()

    def restart(self) -> None:
        self.stop()
        time.sleep(1)
        self.start()
