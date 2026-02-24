"""Asyncio PTY process management.

Forks a PTY child process and bridges I/O via asyncio event loop.
Child exit is detected via EIO/EOF on the PTY fd (no SIGCHLD handler needed,
which avoids conflicts with uvloop).
"""

import asyncio
import fcntl
import logging
import os
import pty
import signal
import struct
import termios
from collections.abc import Callable

from butterfly.config import settings

logger = logging.getLogger("butterfly.pty")


class PtyProcess:
    """Manages a single PTY child process with async I/O."""

    def __init__(self, on_output: Callable[[bytes], None], on_exit: Callable[[], None]) -> None:
        self.on_output = on_output
        self.on_exit = on_exit
        self.pid: int = -1
        self.fd: int = -1
        self._loop: asyncio.AbstractEventLoop | None = None
        self._closed = False

    async def spawn(
        self, cols: int = 0, rows: int = 0, cmd: str = ""
    ) -> None:
        """Fork a PTY and start reading.

        Args:
            cols: Terminal columns (0 = use default).
            rows: Terminal rows (0 = use default).
            cmd: Command to run instead of shell (per-session override).
                 Falls back to settings.cmd, then settings.shell.
        """
        cols = cols or settings.default_cols
        rows = rows or settings.default_rows
        self._cmd = cmd

        pid, fd = pty.fork()

        if pid == 0:
            # Child process — exec command or shell
            self._child_exec(cols, rows)
            # Never returns

        # Parent process
        self.pid = pid
        self.fd = fd
        self._loop = asyncio.get_running_loop()

        # Set non-blocking
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        # Set initial window size
        self._set_winsize(cols, rows)

        # Register fd reader — EOF/EIO on this fd signals child exit
        self._loop.add_reader(fd, self._read_ready)

        effective = self._cmd or settings.cmd or settings.shell
        logger.info("Spawned PTY pid=%d fd=%d cmd=%s", self.pid, self.fd, effective)

    def _child_exec(self, cols: int, rows: int) -> None:
        """Configure and exec command in child process (called after fork, pid==0)."""
        # Set window size before exec
        s = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(1, termios.TIOCSWINSZ, s)  # stdout fd

        env = os.environ.copy()
        env["TERM"] = settings.term
        env["COLORTERM"] = "truecolor"
        env["BUTTERFLY"] = "1"

        # Priority: per-session cmd > global cmd > shell
        cmd = self._cmd or settings.cmd
        if cmd:
            args = cmd.split()
            env["SHELL"] = args[0]
            os.execvpe(args[0], args, env)
        else:
            shell = settings.shell
            env["SHELL"] = shell
            os.execvpe(shell, [shell, "-il"], env)

    def _read_ready(self) -> None:
        """Called by event loop when fd is readable."""
        if self._closed:
            return
        try:
            data = os.read(self.fd, 65536)
            if data:
                self.on_output(data)
            else:
                self._handle_eof()
        except OSError:
            self._handle_eof()

    def _handle_eof(self) -> None:
        """Handle EOF/EIO from PTY — child has exited."""
        if not self._closed:
            logger.info("PTY EOF pid=%d", self.pid)
            self._cleanup()

    def write(self, data: bytes) -> None:
        """Write raw bytes to PTY."""
        if self._closed:
            return
        try:
            os.write(self.fd, data)
        except OSError as e:
            logger.warning("PTY write error: %s", e)
            self._handle_eof()

    def resize(self, cols: int, rows: int) -> None:
        """Resize PTY window."""
        if self._closed:
            return
        self._set_winsize(cols, rows)
        logger.debug("Resized PTY pid=%d to %dx%d", self.pid, cols, rows)

    def _set_winsize(self, cols: int, rows: int) -> None:
        """Set PTY window size via ioctl."""
        try:
            s = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, s)
        except OSError:
            pass

    def _cleanup(self) -> None:
        """Clean up PTY resources and reap child."""
        if self._closed:
            return
        self._closed = True

        # Remove fd reader
        if self._loop and self.fd >= 0:
            try:
                self._loop.remove_reader(self.fd)
            except Exception:
                pass

        # Close fd
        if self.fd >= 0:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = -1

        # Kill and reap child
        if self.pid > 0:
            try:
                os.kill(self.pid, signal.SIGHUP)
                os.kill(self.pid, signal.SIGCONT)
            except ProcessLookupError:
                pass
            try:
                os.waitpid(self.pid, os.WNOHANG)
            except ChildProcessError:
                pass
            self.pid = -1

        # Notify session
        self.on_exit()

    async def close(self) -> None:
        """Gracefully close the PTY."""
        self._cleanup()

    @property
    def alive(self) -> bool:
        return not self._closed
