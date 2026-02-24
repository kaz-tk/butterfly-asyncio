"""Session management for Butterfly.

SessionManager: central registry of all terminal sessions.
TerminalSession: binds a PTY + logger + connected clients + history buffer.
"""

import asyncio
import logging
import random
import string
from datetime import UTC, datetime

from fastapi import WebSocket

from butterfly.config import settings
from butterfly.pty_manager import PtyProcess
from butterfly.session_logger import SessionLogger

logger = logging.getLogger("butterfly.session")


def _generate_session_id() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


class TerminalSession:
    """A terminal session binding PTY, logger, clients, and history."""

    def __init__(self, session_id: str) -> None:
        self.id = session_id
        self.created = datetime.now(UTC)
        self.clients: list[WebSocket] = []
        self.history = bytearray()
        self._pty: PtyProcess | None = None
        self._logger: SessionLogger | None = None
        self._closing = False

    async def start(self, cols: int = 0, rows: int = 0, cmd: str = "") -> None:
        """Spawn PTY and start session logging."""
        self._pty = PtyProcess(
            on_output=self._on_pty_output,
            on_exit=self._on_pty_exit,
        )
        await self._pty.spawn(cols, rows, cmd=cmd)

        if settings.log_enabled:
            self._logger = SessionLogger(settings.log_dir, self.id)
            self._logger.start()

        logger.info("Session %s started", self.id)

    def _on_pty_output(self, data: bytes) -> None:
        """Handle output from PTY — broadcast to clients, log, buffer."""
        # Append to history buffer
        self.history.extend(data)
        if len(self.history) > settings.history_size:
            self.history = self.history[-settings.history_size :]

        # Log
        if self._logger:
            self._logger.write(data)

        # Broadcast to all connected clients
        for ws in list(self.clients):
            try:
                asyncio.ensure_future(ws.send_bytes(data))
            except Exception:
                self.clients.remove(ws)

    def _on_pty_exit(self) -> None:
        """Handle PTY exit — notify all clients."""
        logger.info("Session %s PTY exited", self.id)
        exit_msg = '{"type":"exit"}'
        for ws in list(self.clients):
            try:
                asyncio.ensure_future(ws.send_text(exit_msg))
            except Exception:
                pass

    async def add_client(self, ws: WebSocket) -> None:
        """Add a WebSocket client, sending history replay."""
        self.clients.append(ws)

        # Send history replay
        if self.history:
            try:
                await ws.send_bytes(bytes(self.history))
            except Exception:
                pass

        logger.debug("Session %s: client added (total=%d)", self.id, len(self.clients))

    def remove_client(self, ws: WebSocket) -> None:
        """Remove a WebSocket client."""
        if ws in self.clients:
            self.clients.remove(ws)
        logger.debug("Session %s: client removed (total=%d)", self.id, len(self.clients))

    def write(self, data: bytes) -> None:
        """Write input to PTY."""
        if self._pty:
            self._pty.write(data)

    def resize(self, cols: int, rows: int) -> None:
        """Resize PTY."""
        if self._pty:
            self._pty.resize(cols, rows)

    @property
    def alive(self) -> bool:
        return self._pty is not None and self._pty.alive

    async def close(self) -> None:
        """Shut down session."""
        if self._closing:
            return
        self._closing = True

        if self._pty:
            await self._pty.close()

        if self._logger:
            self._logger.stop()

        # Close all client connections
        for ws in list(self.clients):
            try:
                await ws.close()
            except Exception:
                pass
        self.clients.clear()

        logger.info("Session %s closed", self.id)


class SessionManager:
    """Central registry of terminal sessions."""

    def __init__(self) -> None:
        self.sessions: dict[str, TerminalSession] = {}

    async def create_session(
        self, cols: int = 0, rows: int = 0, cmd: str = ""
    ) -> TerminalSession:
        """Create and start a new terminal session."""
        session_id = _generate_session_id()
        session = TerminalSession(session_id)
        self.sessions[session_id] = session
        await session.start(cols, rows, cmd=cmd)
        logger.info("Created session %s (total=%d)", session_id, len(self.sessions))
        return session

    def get_session(self, session_id: str) -> TerminalSession | None:
        return self.sessions.get(session_id)

    async def remove_session(self, session_id: str) -> None:
        """Close and remove a session."""
        session = self.sessions.pop(session_id, None)
        if session:
            await session.close()
            logger.info("Removed session %s (total=%d)", session_id, len(self.sessions))

    async def shutdown(self) -> None:
        """Close all sessions (called on app shutdown)."""
        logger.info("Shutting down %d sessions", len(self.sessions))
        for session_id in list(self.sessions):
            await self.remove_session(session_id)
