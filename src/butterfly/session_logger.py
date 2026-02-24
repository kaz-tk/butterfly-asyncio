"""Session logger compatible with script(1)/scriptreplay(1).

Produces two files per session:
  - typescript file: raw byte output (script(1) compatible)
  - timing file: "<delay_seconds> <byte_count>\n" (scriptreplay compatible)

Replay with: scriptreplay --timing=<file>.timing <file>

Files are organized by date: YYYY/MM/DD/typescript-<session_id>-<random>
Date changes trigger automatic rotation to a new date directory.
"""

import logging
import os
import random
import string
import time
from datetime import date
from pathlib import Path

logger = logging.getLogger("butterfly.logger")


def _random_id(length: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


class SessionLogger:
    """Logs terminal output in script(1)/scriptreplay(1) compatible format."""

    def __init__(self, base_dir: Path, session_id: str) -> None:
        self.base_dir = base_dir
        self.session_id = session_id
        self._day_random = _random_id()
        self._ts_file: int | None = None  # file descriptor for typescript
        self._tm_file: int | None = None  # file descriptor for timing
        self._last_time: float = 0.0
        self._current_date: date | None = None
        self._closed = False

    def start(self) -> None:
        """Open log files for writing."""
        self._rotate_if_needed()
        logger.info("Session logging started: %s", self.session_id)

    def _rotate_if_needed(self) -> None:
        """Open new files if date changed or files not yet opened."""
        today = date.today()
        if self._current_date == today and self._ts_file is not None:
            return

        # Close existing files
        self._close_files()

        self._current_date = today
        self._day_random = _random_id()

        # Create date-based directory
        date_dir = self.base_dir / today.strftime("%Y/%m/%d")
        date_dir.mkdir(parents=True, exist_ok=True)

        base_name = f"typescript-{self.session_id}-{self._day_random}"
        ts_path = date_dir / base_name
        tm_path = date_dir / f"{base_name}.timing"

        # Open with os.open for unbuffered writes
        self._ts_file = os.open(str(ts_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        self._tm_file = os.open(str(tm_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        self._last_time = time.monotonic()

        # Write script(1) header
        header = f"Script started on {today.isoformat()}\n"
        os.write(self._ts_file, header.encode())

        logger.debug("Log files: %s", ts_path)

    def write(self, data: bytes) -> None:
        """Log output data with timing information."""
        if self._closed:
            return

        self._rotate_if_needed()

        now = time.monotonic()
        delay = now - self._last_time
        self._last_time = now

        # Write raw data to typescript
        if self._ts_file is not None:
            os.write(self._ts_file, data)

        # Write timing: <delay_seconds> <byte_count>
        if self._tm_file is not None:
            timing_line = f"{delay:.6f} {len(data)}\n"
            os.write(self._tm_file, timing_line.encode())

    def _close_files(self) -> None:
        """Close open file descriptors."""
        for fd in (self._ts_file, self._tm_file):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
        self._ts_file = None
        self._tm_file = None

    def stop(self) -> None:
        """Finalize and close log files."""
        if self._closed:
            return
        self._closed = True

        # Write footer
        if self._ts_file is not None:
            footer = f"\nScript done on {date.today().isoformat()}\n"
            try:
                os.write(self._ts_file, footer.encode())
            except OSError:
                pass

        self._close_files()
        logger.info("Session logging stopped: %s", self.session_id)
