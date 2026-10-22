"""The CTC Office header's clock under the central harness.

The harness owns the one simulation clock (D005, D017). The CTC Office
window shows the time the harness sends with each step, and its Run,
Pause and 1x / 10x controls set the module's ``clock_paused`` and
``clock_speedup`` outputs, which the harness reads (R3,
``signals/clock-speedup``). Nothing ticks while the clock is paused, so
each press also goes to the harness at once, as ``STATE`` (R51): this
bridge hands the new values to ``on_change``.

It has the same face for QML as ``ctc_ui.sim_clock``: ``timeText``,
``paused`` and ``speed``, with ``pause()``, ``resume()`` and
``setSpeed()``, so the window's QML is the same in both. ``paused`` and
``speed`` are what the dispatcher asked for. The clock also waits for
every module to be ready, and the harness window says why it holds.
"""

from __future__ import annotations

__all__ = ["HarnessClockBridge"]

from collections.abc import Callable

from PySide6.QtCore import Property, QObject, Signal, Slot

from ctc_ui.ctc_host import SPEEDUP_FACTOR, CtcHost

#: The clock's normal speed.
NORMAL_SPEED = 1

_SECONDS_PER_DAY = 86_400
_SECONDS_PER_HOUR = 3600
_SECONDS_PER_MINUTE = 60

#: Called with the clock controls whenever the dispatcher changes one.
ControlsHandler = Callable[[dict[str, bool]], None]


def time_of_day_text(sim_time_s: float) -> str:
    """Return the 24-hour ``HH:MM:SS`` of an unwrapped time (D017)."""
    total = int(sim_time_s) % _SECONDS_PER_DAY
    hours, rest = divmod(total, _SECONDS_PER_HOUR)
    minutes, seconds = divmod(rest, _SECONDS_PER_MINUTE)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class HarnessClockBridge(QObject):
    """The harness's time, and the dispatcher's clock controls."""

    timeTextChanged = Signal()  # noqa: N815 - Qt name
    pausedChanged = Signal()  # noqa: N815 - Qt name
    speedChanged = Signal()  # noqa: N815 - Qt name

    def __init__(
        self,
        host: CtcHost,
        start_s: float,
        on_change: ControlsHandler,
        parent: QObject | None = None,
    ) -> None:
        """Show ``start_s``, paused at 1x, as the clock starts (D017).

        Args:
            host: The CTC Office the controls act on.
            start_s: The harness's time before the first step.
            on_change: Called with ``controls()`` after every change.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._host = host
        self._on_change = on_change
        self._time_text = time_of_day_text(start_s)
        self._paused = True
        self._speedup = False
        host.setClockPaused(True)
        host.setClockSpeedup(False)

    def controls(self) -> dict[str, bool]:
        """The CTC Office's two clock outputs, as the harness reads them."""
        return {"clock_paused": self._paused, "clock_speedup": self._speedup}

    def show_time(self, sim_time_s: float) -> None:
        """Show the time of a step; the text changes once a second."""
        text = time_of_day_text(sim_time_s)
        if text != self._time_text:
            self._time_text = text
            self.timeTextChanged.emit()

    def _get_time_text(self) -> str:
        # The harness's time of day, 24-hour HH:MM:SS.
        return self._time_text

    def _get_paused(self) -> bool:
        # Whether the dispatcher has the clock paused.
        return self._paused

    def _get_speed(self) -> int:
        # The speed the dispatcher asked for, 1 or 10.
        return SPEEDUP_FACTOR if self._speedup else NORMAL_SPEED

    timeText = Property(  # noqa: N815 - Qt name
        str, _get_time_text, notify=timeTextChanged
    )
    paused = Property(bool, _get_paused, notify=pausedChanged)
    speed = Property(int, _get_speed, notify=speedChanged)

    @Slot()
    def pause(self) -> None:
        """Ask the harness to pause the clock."""
        self._set_paused(True)

    @Slot()
    def resume(self) -> None:
        """Ask the harness to run the clock."""
        self._set_paused(False)

    @Slot(int)
    def setSpeed(self, speed: int) -> None:  # noqa: N802
        """Ask for 10x, or 1x; any other speed is ignored."""
        if speed not in (NORMAL_SPEED, SPEEDUP_FACTOR):
            return
        speedup = speed == SPEEDUP_FACTOR
        if speedup == self._speedup:
            return
        self._speedup = speedup
        self._host.setClockSpeedup(speedup)
        self.speedChanged.emit()
        self._on_change(self.controls())

    def _set_paused(self, paused: bool) -> None:
        # Run or Pause pressed: the module's output, then the harness.
        if paused == self._paused:
            return
        self._paused = paused
        self._host.setClockPaused(paused)
        self.pausedChanged.emit()
        self._on_change(self.controls())
