"""Slips behind real time, logged as episodes instead of one by one.

The pacer drops owed real time when the run falls too far behind
(``common.harness.pacer``). Under a sustained overload that happens
again and again, and logging every drop as ``TIME_SLIPPED`` floods the
event log and the console's fault list. ``SlipEpisodes`` turns the
drops into one episode:

- ``TIME_SLIPPED`` when the first drop comes, as before;
- ``TIME_SLIPPING`` at most every ``REPORT_INTERVAL_S`` while drops go
  on, with how many were dropped since the last report;
- ``TIME_SLIP_ENDED`` once the run has kept up for ``QUIET_S`` with no
  drop, or the clock pauses, with the episode's total. An episode of
  one drop ends silently: its ``TIME_SLIPPED`` already said it all.

It is free of Qt and of real time: the harness passes the time in.
"""

from __future__ import annotations

__all__ = [
    "QUIET_S",
    "REPORT_INTERVAL_S",
    "SLIPPED",
    "SLIPPING",
    "SLIP_ENDED",
    "SlipEpisodes",
]

#: Real seconds between reports while a slip goes on.
REPORT_INTERVAL_S = 10.0
#: Real seconds of keeping up, with no drop, that end a slip.
QUIET_S = 5.0

SLIPPED = "TIME_SLIPPED"
SLIPPING = "TIME_SLIPPING"
SLIP_ENDED = "TIME_SLIP_ENDED"

#: One event to log: its name and detail.
Event = tuple[str, str]


class SlipEpisodes:
    """Turn the pacer's drops into one logged episode per slip."""

    def __init__(
        self,
        report_interval_s: float = REPORT_INTERVAL_S,
        quiet_s: float = QUIET_S,
    ) -> None:
        """Track slips, none yet.

        Args:
            report_interval_s: Real seconds between reports while a
                slip goes on.
            quiet_s: Real seconds of keeping up, with no drop, that
                end a slip.
        """
        self._report_interval_s = report_interval_s
        self._quiet_s = quiet_s
        self._active = False
        self._started_s = 0.0
        self._last_drop_s = 0.0
        self._last_report_s = 0.0
        self._total = 0
        self._drops = 0
        self._unreported = 0

    @property
    def is_slipping(self) -> bool:
        """Whether a slip is going on."""
        return self._active

    @property
    def total(self) -> int:
        """Ticks dropped in the slip going on, or 0."""
        return self._total if self._active else 0

    def dropped(
        self, now_s: float, count: int, actual_speed: float | None = None
    ) -> list[Event]:
        """Note ``count`` owed ticks dropped; return what to log.

        Args:
            now_s: Real time, in seconds.
            count: Ticks dropped.
            actual_speed: The speed the run achieves, if known, for
                the report.
        """
        if not self._active:
            self._active = True
            self._started_s = self._last_drop_s = self._last_report_s = now_s
            self._total = count
            self._unreported = 0
            self._drops = 1
            return [(SLIPPED, f"{count} ticks behind real time, not made up")]
        self._drops += 1
        self._total += count
        self._unreported += count
        self._last_drop_s = now_s
        since_s = now_s - self._last_report_s
        if since_s < self._report_interval_s:
            return []
        detail = (
            f"{self._unreported} more ticks dropped in {since_s:.1f} s; "
            f"{self._total} since the slip began"
            + _speed_text(actual_speed)
        )
        self._last_report_s = now_s
        self._unreported = 0
        return [(SLIPPING, detail)]

    def ticked(
        self,
        now_s: float,
        keeping_up: bool,
        actual_speed: float | None = None,
    ) -> list[Event]:
        """Note a finished tick; return what to log.

        A slip ends once the run keeps up and nothing has been dropped
        for ``quiet_s``.

        Args:
            now_s: Real time, in seconds.
            keeping_up: Whether the run is about level with real time.
            actual_speed: The speed the run achieves, if known.
        """
        if (
            self._active
            and keeping_up
            and now_s - self._last_drop_s >= self._quiet_s
        ):
            return self._end(actual_speed)
        return []

    def held(self) -> list[Event]:
        """Note that the clock stopped running; end any slip."""
        if self._active:
            return self._end(None)
        return []

    def _end(self, actual_speed: float | None) -> list[Event]:
        # Close the episode; one drop needs no closing line.
        self._active = False
        if self._drops == 1:
            return []
        detail = (
            f"{self._total} ticks dropped in {self._drops} batches over "
            f"{self._last_drop_s - self._started_s:.1f} s"
            + _speed_text(actual_speed)
        )
        return [(SLIP_ENDED, detail)]


def _speed_text(actual_speed: float | None) -> str:
    # The achieved speed, when there is one to give.
    if actual_speed is None:
        return ""
    return f"; running at {actual_speed:.1f}x"
