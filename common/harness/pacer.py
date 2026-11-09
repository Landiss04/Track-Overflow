"""Real-time pacing for the harness's ticks.

``TickPacer`` ticks the harness's ``SystemClock`` in real time at the
clock's speed, as ``utils.clock_driver.ClockDriver`` does, with one
difference: a tick is over not when ``tick()`` returns but when every
module has replied (R64), so the pacer never starts a tick while one
is in flight. The harness reports the end of a tick with
``tick_finished``.

Real time goes on earning ticks while one is in flight. They are owed
and run afterwards, so a short hold-up is made up (section 4.3 of
``documents/system-integration-design.md``). A slip drops owed real
time, never a tick: every module still steps every tick, with the
same ``dt``, and only simulation time falls behind real time (D017).

How the pacer sheds load when the modules cannot keep up:

- **Catch-up limit.** At most ``MAX_LAG_S`` of real time is owed.
  Past it the backlog is dropped, all but the next tick, and real time
  counts from now. The limit is in real time, so a run tolerates the
  same lag at 1x and 10x: 5 ticks at 1x, 50 at 10x.
- **Rest after each tick.** The modules' windows draw on the threads
  that answer ``STEP``, so a run that never stops ticking starves them,
  and they slow every later reply. After each tick the pacer rests in
  proportion to the tick's round trip, so the harness keeps the
  modules busy for at most ``MAX_BUSY_FRACTION`` of real time. A run
  that keeps up never waits for the rest: the next tick is not due
  yet. Under overload it holds the run at that fraction of what the
  modules can do, instead of at all of it. The rest is at most
  ``MAX_REST_S``: one long stall is not followed by a long idle.
- **Speed changes** keep what is owed, up to the limit at the new
  speed.
- **A pause** keeps at most the next tick owed, so a run resumes where
  it stopped instead of in a burst.

The pacer also measures the speed the run actually achieves,
``actual_speed``, and how far it is behind, ``lag_s``.

Like ``ClockDriver``, the pacer follows the clock's state: control
speed and pause through the clock.
"""

from __future__ import annotations

__all__ = [
    "MAX_BUSY_FRACTION",
    "MAX_LAG_S",
    "MAX_REST_S",
    "MIN_SPEED_SPAN_S",
    "SPEED_WINDOW_S",
    "TickPacer",
]

import math
import time
from collections import deque
from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, QTimer, Signal

from utils.system_clock import SystemClock

MILLISECONDS_PER_SECOND = 1000

#: Real seconds of owed ticks kept for catching up; more are dropped.
MAX_LAG_S = 0.5
#: Most of real time the harness keeps the modules busy for.
MAX_BUSY_FRACTION = 0.8
#: Longest rest after one tick, in real seconds.
MAX_REST_S = 0.05
#: Real seconds of running the actual speed is measured over.
SPEED_WINDOW_S = 5.0
#: Real seconds of running before the actual speed is reported.
MIN_SPEED_SPAN_S = 1.0
#: Whole ticks owed that still count as keeping up.
KEEPING_UP_TICKS = 2
# Guards a whole number of ticks against float division.
_EPSILON = 1e-9


class TickPacer(QObject):
    """Tick a ``SystemClock`` in real time, one tick at a time."""

    #: Owed ticks were dropped; carries how many.
    backlogDropped = Signal(int)

    def __init__(
        self,
        clock: SystemClock,
        now_s: Callable[[], float] = time.perf_counter,
        parent: QObject | None = None,
        *,
        max_lag_s: float = MAX_LAG_S,
        max_busy_fraction: float = MAX_BUSY_FRACTION,
    ) -> None:
        """Attach a pacer to ``clock``; ``start`` sets it going.

        Args:
            clock: The clock to tick.
            now_s: Real time in seconds, for tests to replace. The
                default is high-resolution on every platform.
            parent: Optional Qt parent.
            max_lag_s: Real seconds of owed ticks kept for catching
                up.
            max_busy_fraction: Most of real time the modules are kept
                busy for, above 0 and at most 1; 1 never rests.

        Raises:
            ValueError: If ``max_lag_s`` is not positive or
                ``max_busy_fraction`` is outside (0, 1].
        """
        super().__init__(parent)
        if not max_lag_s > 0:
            raise ValueError(f"max_lag_s must be positive, got {max_lag_s}")
        if not 0 < max_busy_fraction <= 1:
            raise ValueError(
                "max_busy_fraction must be above 0 and at most 1, got "
                f"{max_busy_fraction}"
            )
        self._clock = clock
        self._now_s = now_s
        self._max_lag_s = max_lag_s
        # Real seconds of rest per real second of a tick's round trip.
        self._rest_ratio = (1 - max_busy_fraction) / max_busy_fraction
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
        # When the tick in flight started, and when the rest after the
        # last one ends.
        self._tick_started_s = 0.0
        self._rest_until_s = -math.inf
        # Real time of each tick started in the speed window, and since
        # when ticks have been earned without a pause.
        self._starts: deque[float] = deque()
        self._earning_since_s: float | None = None
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

    @property
    def catch_up_limit(self) -> int:
        """Whole ticks that may be owed at the current speed."""
        return self._limit_for(self._clock.tick_interval_s)

    @property
    def lag_s(self) -> float:
        """Real seconds the run is behind: whole ticks owed, as time.

        Zero while the clock is paused, since nothing is owed then.
        """
        if self._anchor_s is None:
            return 0.0
        return math.floor(self._earned_ticks()) * self._anchor_interval_s

    @property
    def is_keeping_up(self) -> bool:
        """Whether at most ``KEEPING_UP_TICKS`` whole ticks are owed."""
        return math.floor(self._earned_ticks()) <= KEEPING_UP_TICKS

    @property
    def actual_speed(self) -> float | None:
        """Simulated seconds per real second, as the run achieves it.

        Measured over the last ``SPEED_WINDOW_S`` of running, from the
        ticks started in it. None while the clock is paused, and until
        it has run for ``MIN_SPEED_SPAN_S``.
        """
        if self._earning_since_s is None:
            return None
        now_s = self._now_s()
        span_s = min(SPEED_WINDOW_S, now_s - self._earning_since_s)
        if span_s < MIN_SPEED_SPAN_S:
            return None
        # What is left is inside the span: older starts are forgotten,
        # and a pause or a speed change clears them.
        self._forget_starts(now_s)
        return len(self._starts) * self._clock.tick_s / span_s

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
            now_s = self._now_s()
            busy_s = max(0.0, now_s - self._tick_started_s)
            self._rest_until_s = now_s + min(
                busy_s * self._rest_ratio, MAX_REST_S
            )
            self._schedule()

    def poll(self) -> None:
        """Start the next tick if one is due and none is in flight.

        The pacer's own timer calls this; tests with a fake ``now_s``
        call it by hand.
        """
        if not self._running or self._in_flight or self._anchor_s is None:
            return
        now_s = self._now_s()
        earned = self._earned_ticks()
        if earned < 1 or now_s < self._rest_until_s:
            # Woke a little early, or still resting; wait for the rest.
            self._schedule()
            return
        due = math.floor(earned)
        if due > self._limit_for(self._anchor_interval_s):
            # Too far behind to catch up: drop all but this tick and
            # count real time from now.
            self._drop(due - 1)
            self._anchor_s = now_s
            self._carry_ticks = 1.0
            self._ticks_since_anchor = 0
        # Mark the tick as in flight and spent before running it: the
        # harness may finish it, or change the clock, from inside.
        self._in_flight = True
        self._tick_started_s = now_s
        self._ticks_since_anchor += 1
        self._forget_starts(now_s)
        self._starts.append(now_s)
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

    def _limit_for(self, interval_s: float) -> int:
        # Whole ticks of ``interval_s`` that fit in the catch-up limit;
        # always at least the next one.
        return max(1, math.floor(self._max_lag_s / interval_s + _EPSILON))

    def _retime(self) -> None:
        # Re-anchor real time at the current speed, keeping what was
        # earned up to the limit at that speed; a pause keeps at most
        # the next tick.
        if self._clock.is_paused:
            self._hold()
            return
        now_s = self._now_s()
        carry = self._earned_ticks()
        interval_s = self._clock.tick_interval_s
        due = math.floor(carry)
        if due > self._limit_for(interval_s):
            self._drop(due - 1)
            carry -= due - 1
        self._carry_ticks = carry
        self._ticks_since_anchor = 0
        self._anchor_s = now_s
        if self._earning_since_s is None:
            self._earning_since_s = now_s
        if interval_s != self._anchor_interval_s:
            # The speed window measures one speed at a time.
            self._starts.clear()
            self._earning_since_s = now_s
        self._anchor_interval_s = interval_s
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
        self._starts.clear()
        self._earning_since_s = None
        self._timer.stop()

    def _schedule(self) -> None:
        # Wake when the next tick falls due and the rest is over, or at
        # once if both are. Rounding up keeps the wake from landing
        # early.
        if not self._running or self._in_flight or self._anchor_s is None:
            self._timer.stop()
            return
        earned = self._earned_ticks()
        wait_s = 0.0 if earned >= 1 else (1 - earned) * self._anchor_interval_s
        wait_s = max(wait_s, self._rest_until_s - self._now_s())
        if wait_s <= 0:
            self._timer.start(0)
            return
        self._timer.start(math.ceil(wait_s * MILLISECONDS_PER_SECOND))

    def _forget_starts(self, now_s: float) -> None:
        # Keep only the starts inside the speed window.
        since_s = now_s - SPEED_WINDOW_S
        while self._starts and self._starts[0] <= since_s:
            self._starts.popleft()

    def _drop(self, count: int) -> None:
        # Count and report owed ticks that will never run.
        self._dropped_ticks += count
        self.backlogDropped.emit(count)
