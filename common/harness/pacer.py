"""Real-time pacing for the harness's ticks.

``TickPacer`` ticks the harness's ``SystemClock`` in real time at the
clock's speed, as ``utils.clock_driver.ClockDriver`` does, with one
difference: a tick is over not when ``tick()`` returns but when every
module has replied (R64), so the pacer never starts a tick while one
is in flight. The harness reports the end of a tick with
``tick_finished``.

Real time goes on earning ticks while one is in flight. They are owed
and run back to back once the replies are in, so a short hold-up is
made up afterwards (section 4.3 of
``documents/system-integration-design.md``). Past
``MAX_CATCH_UP_TICKS`` owed ticks the backlog is dropped, and
simulation time slips instead. A pause keeps at most the next tick
owed, so a run resumes where it stopped instead of in a burst.

Like ``ClockDriver``, the pacer follows the clock's state: control
speed and pause through the clock.
"""

from __future__ import annotations

__all__ = ["TickPacer"]

import math
import time
from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, QTimer, Signal

from utils.clock_driver import MAX_CATCH_UP_TICKS
from utils.system_clock import SystemClock

MILLISECONDS_PER_SECOND = 1000


class TickPacer(QObject):
    """Tick a ``SystemClock`` in real time, one tick at a time."""

    #: Owed ticks were dropped; carries how many.
    backlogDropped = Signal(int)

    def __init__(
        self,
        clock: SystemClock,
        now_s: Callable[[], float] = time.perf_counter,
        parent: QObject | None = None,
    ) -> None:
        """Attach a pacer to ``clock``; ``start`` sets it going.

        Args:
            clock: The clock to tick.
            now_s: Real time in seconds, for tests to replace. The
                default is high-resolution on every platform.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._clock = clock
        self._now_s = now_s
        self._running = False
        self._in_flight = False
        # Real time when the current interval began, or None while no
        # real time is earning ticks.
        self._anchor_s: float | None = None
        self._anchor_interval_s = clock.tick_interval_s
        # Ticks already earned when the anchor was set.
        self._carry_ticks = 0.0
        self._ticks_since_anchor = 0
        self._dropped_ticks = 0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self.poll)
        clock.add_state_listener(self._on_clock_state_changed)

    @property
    def clock(self) -> SystemClock:
        """The clock this pacer ticks."""
        return self._clock

    @property
    def is_running(self) -> bool:
        """Whether the pacer is started."""
        return self._running

    @property
    def is_in_flight(self) -> bool:
        """Whether a tick has started and not yet finished."""
        return self._in_flight

    @property
    def owed_ticks(self) -> float:
        """Ticks earned but not started, with the part of the next."""
        return self._earned_ticks()

    @property
    def dropped_ticks(self) -> int:
        """Owed ticks dropped since the pacer was created."""
        return self._dropped_ticks

    def start(self) -> None:
        """Tick the clock whenever it is not paused."""
        if not self._running:
            self._running = True
            self._retime()

    def stop(self) -> None:
        """Stop ticking, whatever the clock's state."""
        if self._running:
            self._running = False
            self._hold()

    def tick_finished(self) -> None:
        """Report that the tick in flight is over: every reply is in."""
        if self._in_flight:
            self._in_flight = False
            self._schedule()

    def poll(self) -> None:
        """Start the next tick if one is due and none is in flight.

        The pacer's own timer calls this; tests with a fake ``now_s``
        call it by hand.
        """
        if not self._running or self._in_flight or self._anchor_s is None:
            return
        earned = self._earned_ticks()
        if earned < 1:
            # Woke a little early; wait for the rest.
            self._schedule()
            return
        due = math.floor(earned)
        if due > MAX_CATCH_UP_TICKS:
            # Too far behind to catch up: drop all but this tick and
            # count real time from now.
            self._drop(due - 1)
            self._anchor_s = self._now_s()
            self._carry_ticks = 1.0
            self._ticks_since_anchor = 0
        # Mark the tick as in flight and spent before running it: the
        # harness may finish it, or change the clock, from inside.
        self._in_flight = True
        self._ticks_since_anchor += 1
        self._clock.tick()

    def _on_clock_state_changed(self) -> None:
        # Speed or pause changed: retime from now.
        if self._running:
            self._retime()

    def _earned_ticks(self) -> float:
        # Ticks earned since the anchor and not yet started, including
        # the part of the next one.
        earned = self._carry_ticks - self._ticks_since_anchor
        if self._anchor_s is not None:
            elapsed_s = self._now_s() - self._anchor_s
            earned += elapsed_s / self._anchor_interval_s
        return max(0.0, earned)

    def _retime(self) -> None:
        # Re-anchor real time at the current speed, keeping what was
        # earned; a pause keeps at most the next tick.
        if self._clock.is_paused:
            self._hold()
            return
        self._carry_ticks = self._earned_ticks()
        self._ticks_since_anchor = 0
        self._anchor_s = self._now_s()
        self._anchor_interval_s = self._clock.tick_interval_s
        self._schedule()

    def _hold(self) -> None:
        # Stop earning ticks. Whole ticks owed beyond the next one are
        # dropped, so nothing bursts when ticking starts again.
        earned = self._earned_ticks()
        if earned >= 2:
            self._drop(math.floor(earned) - 1)
        self._carry_ticks = min(earned, 1.0)
        self._ticks_since_anchor = 0
        self._anchor_s = None
        self._timer.stop()

    def _schedule(self) -> None:
        # Wake when the next tick falls due, or at once if it has.
        # Rounding up keeps the wake from landing early.
        if not self._running or self._in_flight or self._anchor_s is None:
            self._timer.stop()
            return
        earned = self._earned_ticks()
        if earned >= 1:
            self._timer.start(0)
            return
        wait_s = (1 - earned) * self._anchor_interval_s
        self._timer.start(math.ceil(wait_s * MILLISECONDS_PER_SECOND))

    def _drop(self, count: int) -> None:
        # Count and report owed ticks that will never run.
        self._dropped_ticks += count
        self.backlogDropped.emit(count)
