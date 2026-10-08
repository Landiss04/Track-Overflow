"""The shared simulation clock, exposed to the CTC Office QML.

The CTC Office owns the one ``SystemClock`` instance for now and drives
it in real time. When the central harness exists it will own the clock
(D005) and the CTC will control it through the harness; this bridge is
the stand-in until then.

QML reads ``timeText``, ``paused`` and ``speed`` and calls ``pause()``,
``resume()`` and ``setSpeed()``. The clock starts paused at 05:00:00.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from utils.clock_driver import ClockDriver
from utils.system_clock import SystemClock


class SimulationClockBridge(QObject):
    """Own the simulation clock and its real-time driver for QML."""

    timeTextChanged = Signal()
    pausedChanged = Signal()
    speedChanged = Signal()

    def __init__(
        self,
        clock: SystemClock | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Create the bridge and start driving the clock in real time.

        Args:
            clock: The clock to expose. A new default clock is created
                if omitted.
            parent: Optional Qt parent that owns this bridge.
        """
        super().__init__(parent)
        self._clock = clock if clock is not None else SystemClock()
        self._time_text = self._clock.format_time_of_day()
        self._clock.add_tick_listener(self._on_tick)
        self._clock.add_state_listener(self._on_state_changed)
        self._driver = ClockDriver(self._clock, self)
        self._driver.start()

    @property
    def clock(self) -> SystemClock:
        """The clock this bridge exposes."""
        return self._clock

    def _get_time_text(self) -> str:
        # Simulated time of day, 24-hour HH:MM:SS.
        return self._time_text

    def _get_paused(self) -> bool:
        # Whether the clock is held.
        return self._clock.is_paused

    def _get_speed(self) -> int:
        # Current speed multiplier, 1 or 10.
        return self._clock.speed

    timeText = Property(str, _get_time_text, notify=timeTextChanged)
    paused = Property(bool, _get_paused, notify=pausedChanged)
    speed = Property(int, _get_speed, notify=speedChanged)

    @Slot()
    def pause(self) -> None:
        """Hold the simulation clock."""
        self._clock.pause()

    @Slot()
    def resume(self) -> None:
        """Run the simulation clock."""
        self._clock.resume()

    @Slot(int)
    def setSpeed(self, speed: int) -> None:  # noqa: N802
        """Set the speed multiplier to 1 or 10."""
        self._clock.set_speed(speed)

    def _on_tick(self, sim_time_s: float, tick_s: float) -> None:
        # Ten ticks make a second, so only notify when the shown second
        # changes rather than on every tick.
        text = self._clock.format_time_of_day()
        if text != self._time_text:
            self._time_text = text
            self.timeTextChanged.emit()

    def _on_state_changed(self) -> None:
        # Pause, speed, or reset changed; a reset also moves the time.
        self.pausedChanged.emit()
        self.speedChanged.emit()
        self._on_tick(self._clock.sim_time_s, self._clock.tick_s)
