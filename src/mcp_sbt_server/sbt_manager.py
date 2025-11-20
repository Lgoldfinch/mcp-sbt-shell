import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("mcp_sbt_server.sbt_manager")


class SbtManager:
    def __init__(self, timeout: int = 30, sbt_path: Optional[str] = None, workdir: Optional[str] = None):
        self.timeout = timeout
        self.sbt_path = sbt_path or "sbt"
        self.workdir = workdir
        self.process: Optional[subprocess.Popen] = None
        self.ready = False
        self._lock = threading.Lock()
        self._output_buffer = []
        self._ready_event = threading.Event()
        self._stderr_monitor_thread: Optional[threading.Thread] = None

        # Validate workdir if provided
        if self.workdir:
            workdir_path = Path(self.workdir)
            if not workdir_path.exists():
                raise RuntimeError(f"Working directory does not exist: {self.workdir}")
            if not workdir_path.is_dir():
                raise RuntimeError(f"Working directory path is not a directory: {self.workdir}")

        logger.info(
            f"SBT Manager initialized with timeout={timeout}s, sbt_path={self.sbt_path}, workdir={self.workdir or 'current directory'}"
        )

    def start(self) -> None:
        with self._lock:
            if self.process and self.process.poll() is None:
                logger.info("SBT process is already running")
                return

            # Determine the working directory to use
            cwd = self.workdir if self.workdir else os.getcwd()
            logger.info(f"Starting SBT process with executable: {self.sbt_path} in directory: {cwd}")

            try:
                self.process = subprocess.Popen(
                    [self.sbt_path, "--no-colors", "--supershell=false"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=cwd,
                    bufsize=1,
                    universal_newlines=True,
                )
            except FileNotFoundError as e:
                error_msg = (
                    f"Failed to start SBT process: {e}\n\n"
                    f"SBT executable not found at: {self.sbt_path}\n\n"
                    f"Please ensure:\n"
                    f"1. SBT is installed on your system\n"
                    f"2. The path to the SBT executable is correct\n"
                    f"3. The executable has proper permissions"
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg) from e
            except Exception as e:
                error_msg = f"Failed to start SBT process: {e}"
                logger.error(error_msg)
                raise RuntimeError(error_msg) from e

            self.ready = False
            self._ready_event.clear()
            threading.Thread(target=self._monitor_startup, daemon=True).start()

            # Start stderr monitoring thread
            self._stderr_monitor_thread = threading.Thread(target=self._monitor_stderr, daemon=True)
            self._stderr_monitor_thread.start()

            logger.info("SBT process started, waiting for ready signal")

    def _monitor_startup(self) -> None:
        if not self.process:
            logger.warning("Monitor startup called but no process exists")
            return

        logger.debug("Monitoring SBT startup for ready signal")
        while True:
            line = self.process.stdout.readline()
            if not line:
                logger.warning("SBT process ended during startup monitoring")
                break

            # Log each stdout line during startup
            stripped_line = line.strip()
            if stripped_line:
                logger.debug(f"SBT stdout: {stripped_line}")

            if stripped_line.endswith(">"):
                logger.info("SBT process is ready")
                self.ready = True
                self._ready_event.set()
                break

    def _monitor_stderr(self) -> None:
        """Continuously monitor and log stderr output from the SBT process."""
        if not self.process:
            logger.warning("Monitor stderr called but no process exists")
            return

        logger.debug("Starting stderr monitoring for SBT process")
        while self.process and self.process.poll() is None:
            line = self.process.stderr.readline()
            if not line:
                break

            stripped_line = line.strip()
            if stripped_line:
                # Log stderr at WARNING level since it typically contains error/warning messages
                logger.warning(f"SBT stderr: {stripped_line}")

        logger.debug("Stderr monitoring ended")

    def stop(self) -> None:
        with self._lock:
            if self.process and self.process.poll() is None:
                logger.info("Stopping SBT process")
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                    logger.info("SBT process stopped gracefully")
                except subprocess.TimeoutExpired:
                    logger.warning("SBT process did not stop gracefully, forcing termination")
                    self.process.kill()
                    self.process.wait()
                    logger.info("SBT process force terminated")

            # Wait for stderr monitoring thread to finish
            if self._stderr_monitor_thread and self._stderr_monitor_thread.is_alive():
                logger.debug("Waiting for stderr monitoring thread to finish")
                self._stderr_monitor_thread.join(timeout=2)
                if self._stderr_monitor_thread.is_alive():
                    logger.warning("Stderr monitoring thread did not finish gracefully")

            self.process = None
            self.ready = False
            self._stderr_monitor_thread = None

    def execute_command(self, command: str) -> str:
        logger.debug(f"Waiting for SBT to be ready before executing command: {command}")
        if not self._ready_event.wait(timeout=10):
            logger.error("SBT not ready within timeout period")
            raise RuntimeError("SBT not ready within timeout")

        with self._lock:
            if not self.process or self.process.poll() is not None:
                logger.error("SBT process not running when attempting to execute command")
                raise RuntimeError("SBT process not running")

            try:
                logger.debug(f"Executing SBT command: {command}")
                self.process.stdin.write(command + "\n")
                self.process.stdin.flush()

                output_lines = []
                start_time = time.time()

                while time.time() - start_time < self.timeout:
                    line = self.process.stdout.readline()
                    if not line:
                        if self.process.poll() is not None:
                            logger.error("SBT process died during command execution")
                            raise RuntimeError("SBT process died during command execution")
                        continue

                    stripped_line = line.strip()
                    # Log stdout during command execution
                    if stripped_line:
                        logger.debug(f"SBT stdout: {stripped_line}")

                    output_lines.append(line.rstrip("\n\r"))

                    if stripped_line.endswith(">"):
                        logger.debug(f"SBT command completed: {command}")
                        break

                else:
                    logger.warning(f"SBT command timed out after {self.timeout} seconds: {command}")
                    raise RuntimeError(f"Command timed out after {self.timeout} seconds")

                return self._truncate_output(output_lines)

            except Exception as e:
                logger.error(f"Exception during SBT command execution: {e}")
                if self.process and self.process.poll() is not None:
                    logger.warning("SBT process is no longer running after command execution error")
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
        logger.info("Restarting SBT process")
        self.stop()
        time.sleep(1)
        self.start()
        logger.info("SBT process restart completed")
