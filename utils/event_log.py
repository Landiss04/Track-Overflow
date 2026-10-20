"""Event log: one CSV file of significant simulation events.

REQ-NFR-008 asks for a log of significant simulation events for
debugging and review, and REQ-INTF-015 asks for it in CSV. The central
harness writes it, since every message between modules passes through
it (``conventions/files-and-paths.md``).

Each row holds the real time it was written, the simulation time and
tick it belongs to, who it is about, what happened, and any detail.
Event names are capitals, like every enumerated value. A row is
flushed as soon as it is written, so the log survives a crash.
"""

from __future__ import annotations

__all__ = ["COLUMNS", "EventLog", "log_file_name"]

import csv
from datetime import datetime
from pathlib import Path
from types import TracebackType

from utils.system_clock import (
    SECONDS_PER_DAY,
    SECONDS_PER_HOUR,
    SECONDS_PER_MINUTE,
)

COLUMNS = (
    "wall_time",
    "sim_time_s",
    "time_of_day",
    "tick",
    "source",
    "event",
    "detail",
)


def log_file_name(started: datetime) -> str:
    """Return the file name for a log started at ``started``."""
    return f"events-{started:%Y%m%d-%H%M%S}.csv"


class EventLog:
    """Append significant events to one CSV file."""

    def __init__(self, path: Path) -> None:
        """Create the file and its folder, and write the header.

        Args:
            path: Where to write. An existing file is replaced.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        # Kept open for the life of the log; ``close`` or a ``with``
        # block releases it.
        self._file = path.open("w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow(COLUMNS)
        self._file.flush()

    @property
    def path(self) -> Path:
        """Where the log is written."""
        return self._path

    @property
    def closed(self) -> bool:
        """Whether the log no longer accepts rows."""
        return self._file.closed

    def write(
        self,
        *,
        sim_time_s: float,
        tick: int,
        source: str,
        event: str,
        detail: str = "",
    ) -> None:
        """Append one event and flush it to disk.

        Args:
            sim_time_s: Unwrapped simulation time of the event.
            tick: Tick the event belongs to, 0 before the first.
            source: Who the event is about, such as a module name or
                ``harness``.
            event: What happened, in capitals, such as
                ``TICK_REJECTED``.
            detail: Anything that helps a reader, such as a reason.
        """
        if self._file.closed:
            return
        self._writer.writerow(
            (
                datetime.now().isoformat(timespec="milliseconds"),
                f"{sim_time_s:.1f}",
                _time_of_day(sim_time_s),
                tick,
                source,
                event,
                detail,
            )
        )
        self._file.flush()

    def close(self) -> None:
        """Flush and close the file. Later writes are ignored."""
        if not self._file.closed:
            self._file.close()

    def __enter__(self) -> EventLog:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def _time_of_day(sim_time_s: float) -> str:
    # HH:MM:SS of the simulated day, as every window shows it (D017).
    whole_s = int(sim_time_s) % SECONDS_PER_DAY
    hours, remainder_s = divmod(whole_s, SECONDS_PER_HOUR)
    minutes, seconds = divmod(remainder_s, SECONDS_PER_MINUTE)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
