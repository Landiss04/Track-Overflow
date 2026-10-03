"""The CTC Office module as hosted by the CTC Office window.

The window owns the one live CTC module. It also serves that module to
the CTC test UI over ``ctc.socket_link``, so both windows act on the
same state. Actions taken in the window (the operating mode and the
clock speed) are applied to the module and pushed to any connected test UI.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from ctc.interface import CtcOffice
from ctc.model import StubCtcOffice
from ctc.schedule import ScheduleError, load_schedule
from ctc.socket_link import CtcLinkServer

if TYPE_CHECKING:
    from ctc_ui.sim_clock import SimulationClockBridge

#: The shared clock's fast-forward speed; clock_speedup means this.
SPEEDUP_FACTOR = 10


def _offset(seconds: int) -> str:
    """``+m:ss`` after the schedule start."""
    return f"+{seconds // 60}:{seconds % 60:02d}"


class CtcHost(QObject):
    """Bindable CTC module for ``Main.qml``, served to the test UI."""

    maintenanceModeChanged = Signal()
    clockSpeedupChanged = Signal()
    scheduleChanged = Signal()

    def __init__(self, module: CtcOffice | None = None,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._module = module if module is not None else StubCtcOffice()
        self._server = CtcLinkServer(self._module, parent=self)
        self._schedule_file = ""
        self._schedule_error = ""

    def start(self) -> None:
        """Start serving the test UI. The window works either way."""
        if not self._server.listen():
            print("CTC test UI link unavailable: could not listen.",
                  file=sys.stderr)

    def stop(self) -> None:
        """Stop serving the test UI; call before the app shuts down."""
        self._server.close()

    @Property(bool, notify=maintenanceModeChanged)
    def maintenanceMode(self) -> bool:  # noqa: N802
        outputs = self._module.snapshot().outputs
        return outputs.track_controller.maintenance_mode

    @Slot(bool)
    def setMaintenanceMode(self, active: bool) -> None:  # noqa: N802
        """Apply the window's operating mode to the module."""
        if active == self.maintenanceMode:
            return
        self._module.set_maintenance_mode(active)
        self.maintenanceModeChanged.emit()
        self._server.push()

    @Property(bool, notify=clockSpeedupChanged)
    def clockSpeedup(self) -> bool:  # noqa: N802
        return self._module.snapshot().outputs.clock_speedup

    def follow_clock(self, clock: SimulationClockBridge) -> None:
        """Keep clock_speedup in step with the window's clock speed."""
        def apply() -> None:
            # speedChanged also fires on pause; repeats are ignored.
            self.setClockSpeedup(clock.speed == SPEEDUP_FACTOR)
        clock.speedChanged.connect(apply)
        apply()

    @Slot(bool)
    def setClockSpeedup(self, active: bool) -> None:  # noqa: N802
        """Apply the window's clock speed (10x is True) to the module."""
        if active == self.clockSpeedup:
            return
        self._module.set_clock_speedup(active)
        self.clockSpeedupChanged.emit()
        self._server.push()

    # -- Schedule -----------------------------------------------------

    @Property(str, notify=scheduleChanged)
    def scheduleFile(self) -> str:  # noqa: N802
        return self._schedule_file

    @Property(str, notify=scheduleChanged)
    def scheduleError(self) -> str:  # noqa: N802
        return self._schedule_error

    @Property(list, notify=scheduleChanged)
    def departures(self) -> list[dict[str, Any]]:
        """Queued runs as rows for the Next departures table."""
        return [
            {"time": _offset(q.departure_s),
             "train": f"{q.line} {q.train_id}",
             "status": "Queued"}
            for q in self._module.snapshot().queued_trains
        ]

    @Slot(QUrl)
    def loadSchedule(self, url: QUrl) -> None:  # noqa: N802
        """Load a schedule file; on failure keep the current one."""
        path = Path(url.toLocalFile())
        try:
            schedule = load_schedule(path)
        except ScheduleError as error:
            self._schedule_error = str(error)
        else:
            self._module.load_schedule(schedule)
            self._schedule_file = path.name
            self._schedule_error = ""
            self._server.push()
        self.scheduleChanged.emit()
