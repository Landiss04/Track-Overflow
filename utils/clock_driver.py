"""Real-time driver for the shared simulation clock.

``ClockDriver`` ticks a ``SystemClock`` from the Qt event loop so that
simulation time keeps pace with real time at the clock's speed. The
driver does not poll: after each fire it schedules the next one for the
moment the next tick falls due. Each fire runs every tick real time
says is due, so a late fire changes how many ticks run at once, never
the length of a tick or the long-run rate.

Progress toward the next tick is carried across pause, resume, and
speed changes, so changing state does not lose or gain time.
"""

from __future__ import annotations

__all__ = ["ClockDriver"]

import math

from PySide6.QtCore import QElapsedTimer, QObject, Qt, QTimer

from utils.system_clock import SystemClock

NANOSECONDS_PER_SECOND = 1_000_000_000
MILLISECONDS_PER_SECOND = 1000

# Ticks one timer fire may run before the backlog is dropped. Beyond
# this the application has stalled, and replaying every missed tick at
# once would freeze it further; simulation time slips instead.
MAX_CATCH_UP_TICKS = 100


class ClockDriver(QObject):
    """Tick a ``SystemClock`` in real time from the Qt event loop.

    The driver follows the clock's state: it stops ticking while the
    clock is paused and retimes itself when the speed changes. Control
    speed and pause through the clock, not the driver.
    """

    def __init__(
        self,
        clock: SystemClock,
        parent: QObject | None = None,
    ) -> None:
        """Attach a driver to ``clock``.

        Args:
            clock: The clock to tick.
            parent: Optional Qt parent that owns this driver.
        """
        super().__init__(parent)
        self._clock = clock
        self._running = False
        self._wall_timer = QElapsedTimer()
        # Real seconds per tick while timing an interval, or None while
        # no real time is counting toward ticks.
        self._anchor_interval_s: float | None = None
        # Ticks already earned when the current anchor was set.
        self._carry_ticks = 0.0
        self._ticks_since_anchor = 0
        self._anchor_reset_count = clock.reset_count
        self._anchor_generation = 0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._on_timeout)
        clock.add_state_listener(self._on_clock_state_changed)

    @property
    def clock(self) -> SystemClock:
        """The clock this driver ticks."""
        return self._clock

    @property
    def is_running(self) -> bool:
        """Whether the driver is started."""
        return self._running

    def start(self) -> None:
        """Start ticking the clock whenever it is not paused."""
        if not self._running:
            self._running = True
            self._retime()

    def stop(self) -> None:
        """Stop ticking the clock, whatever its pause state."""
        if self._running:
            self._carry_ticks = self._earned_ticks()
            self._anchor_interval_s = None
            self._running = False
            self._timer.stop()

    def _on_clock_state_changed(self) -> None:
        # Speed, pause, or reset changed. Ticks that fell due under the
        # old state run first, so a pause does not hold them until the
        # next resume; a reset discards them. Then retime from now.
        if not self._running:
            return
        reset = self._clock.reset_count != self._anchor_reset_count
        if (
            not reset
            and self._anchor_interval_s is not None
            and math.floor(self._earned_ticks()) <= MAX_CATCH_UP_TICKS
            and not self._run_due_ticks()
        ):
            # A listener changed state again and the driver has already
            # retimed for the newest state.
            return
        self._retime()

    def _earned_ticks(self) -> float:
        # Ticks earned since the anchor but not yet run, including the
        # fraction of the tick in progress.
        earned = self._carry_ticks - self._ticks_since_anchor
        if self._anchor_interval_s is not None:
            wall_elapsed_s = (
                self._wall_timer.nsecsElapsed() / NANOSECONDS_PER_SECOND
            )
            earned += wall_elapsed_s / self._anchor_interval_s
        return max(0.0, earned)

    def _retime(self) -> None:
        # Re-anchor real time at the current speed, keeping progress
        # already earned unless the clock was reset.
        reset = self._clock.reset_count != self._anchor_reset_count
        self._carry_ticks = 0.0 if reset else self._earned_ticks()
        self._wall_timer.start()
        self._ticks_since_anchor = 0
        self._anchor_reset_count = self._clock.reset_count
        self._anchor_generation += 1
        if self._clock.is_paused:
            self._anchor_interval_s = None
            self._timer.stop()
            return
        self._anchor_interval_s = self._clock.tick_interval_s
        self._schedule_next_fire()

    def _schedule_next_fire(self) -> None:
        # Fire when the next tick falls due, or at once if one already
        # has. Rounding up keeps fires from landing early.
        if self._anchor_interval_s is None:
            return
        earned = self._earned_ticks()
        if earned >= 1:
            self._timer.start(0)
            return
        wait_s = (1 - earned) * self._anchor_interval_s
        self._timer.start(math.ceil(wait_s * MILLISECONDS_PER_SECOND))

    def _on_timeout(self) -> None:
        # Run the ticks real time says are due, then wait for the next.
        if self._clock.is_paused or self._anchor_interval_s is None:
            return
        due_ticks = math.floor(self._earned_ticks())
        if due_ticks > MAX_CATCH_UP_TICKS:
            self._clock.tick()
            self._carry_ticks = 0.0
            self._wall_timer.start()
            self._ticks_since_anchor = 0
            self._schedule_next_fire()
            return
        if self._run_due_ticks():
            self._schedule_next_fire()

    def _run_due_ticks(self) -> bool:
        # Run every tick real time says is due. Return False if a
        # listener changed the clock's state mid-burst: that retimes the
        # driver, so the remaining ticks no longer apply.
        generation = self._anchor_generation
        for _ in range(math.floor(self._earned_ticks())):
            # Count the tick before running it: a listener that retimes
            # the driver from inside the tick must see it as spent.
            self._ticks_since_anchor += 1
            self._clock.tick()
            if self._anchor_generation != generation:
                return False
        return True
