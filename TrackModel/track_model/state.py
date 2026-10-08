"""Track Model UI state: the snapshot, in display units, for QML.

Reads ``TrackModel.snapshot()`` and converts to imperial at this layer
only (``truth/conventions/units.md``). Murphy's failure injection is the
one action; it calls the module, then ``on_ui_action`` so the host can
tell the test UI at once.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from track_model.interface import (
    Block,
    TrackFailure,
    TrackModel,
    TrackModelSnapshot,
)

FT_PER_M = 3.280840
MPH_PER_MPS = 2.236936
#: Paused once no step has arrived for this long.
PAUSED_AFTER_MS = 500

FAILURE_MODES: tuple[str, ...] = tuple(f.name for f in TrackFailure)


def c_to_f(temp_c: float) -> float:
    """Convert degrees Celsius to Fahrenheit."""
    return temp_c * 9.0 / 5.0 + 32.0


def _clock(seconds: float) -> str:
    # Elapsed simulated time as hh:mm:ss.
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class TrackModelState(QObject):
    """Bindable view of one Track Model for the Track Model UI."""

    changed = Signal()
    runningChanged = Signal()
    viewChanged = Signal()

    def __init__(
        self,
        model: TrackModel,
        on_ui_action: Callable[[], None] = lambda: None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._on_ui_action = on_ui_action
        self._snap: TrackModelSnapshot = model.snapshot()
        self._lines = sorted({b.line for b in self._snap.blocks})
        self._line = "GREEN" if "GREEN" in self._lines else self._lines[0]
        self._filter = ""
        self._selected = ""
        self._running = False
        self._pause_timer = QTimer(self)
        self._pause_timer.setSingleShot(True)
        self._pause_timer.setInterval(PAUSED_AFTER_MS)
        self._pause_timer.timeout.connect(lambda: self._set_running(False))

    # -- host hooks --------------------------------------------------------

    @Slot()
    def refresh(self) -> None:
        """Re-read the module after a step or an action."""
        self._snap = self._model.snapshot()
        self.changed.emit()

    @Slot()
    def mark_step(self) -> None:
        """Note that a step arrived: Running until they stop."""
        self._set_running(True)
        self._pause_timer.start()

    # -- header ------------------------------------------------------------

    @Property(bool, notify=runningChanged)
    def running(self) -> bool:
        """Whether steps are arriving, from whoever sends them."""
        return self._running

    @Property(str, notify=changed)
    def elapsed(self) -> str:
        """Simulated time since start or reset."""
        return _clock(self._snap.elapsed_s)

    @Property(str, notify=changed)
    def ambient(self) -> str:
        """Ambient temperature for display."""
        return f"{c_to_f(self._snap.ambient_temp_c):.0f} °F"

    # -- line and filter ---------------------------------------------------

    @Property(list, constant=True)
    def lines(self) -> list[str]:
        """Every loaded line."""
        return list(self._lines)

    @Property(str, notify=viewChanged)
    def line(self) -> str:
        """The line on show."""
        return self._line

    @Slot(str)
    def setLine(self, line: str) -> None:
        """Show another line."""
        if line in self._lines and line != self._line:
            self._line = line
            self.viewChanged.emit()
            self.changed.emit()

    @Slot(str)
    def setFilter(self, text: str) -> None:
        """Show only blocks whose ID or station contains ``text``."""
        if text != self._filter:
            self._filter = text
            self.changed.emit()

    # -- tables ------------------------------------------------------------

    @Property(list, notify=changed)
    def blockRows(self) -> list[dict[str, Any]]:
        """Blocks on the current line, after the filter."""
        out = self._snap.outputs.controller
        needle = self._filter.strip().upper()
        rows = []
        for b in self._snap.blocks:
            if b.line != self._line:
                continue
            station = b.station_name or ""
            if needle and needle not in b.block_id and needle not in station:
                continue
            failure = out.failure_status[b.block_id]
            rows.append({
                "id": b.block_id,
                "direction": self._direction_short(b),
                "length": f"{b.length_m * FT_PER_M:.0f}",
                "grade": f"{b.grade_deg:.2f}",
                "limit": f"{b.speed_limit_mps * MPH_PER_MPS:.0f}",
                "station": station,
                "beacon": self._beacon_short(b.block_id),
                "heat": "ON" if out.heater_states.get(b.section_id) else "",
                "occupied": "OCC" if out.block_occupancy[b.block_id] else "",
                "signal": self._aspect(b.block_id),
                "failure": "" if failure is TrackFailure.NONE
                else failure.name,
            })
        return rows

    @Property(list, notify=changed)
    def switchRows(self) -> list[dict[str, Any]]:
        """Switches on the current line and the light before each."""
        states = self._snap.outputs.controller.switch_states
        return [
            {
                "id": s.switch_id,
                "normal": s.normal_block_id or "YARD",
                "reverse": s.reverse_block_id or "YARD",
                "position": states[s.switch_id].name,
                "source": s.source,
            }
            for s in self._snap.switches if s.line == self._line
        ]

    @Property(list, notify=changed)
    def signalRows(self) -> list[dict[str, Any]]:
        """Signal lights on the current line."""
        return [
            {"id": block_id, "aspect": self._aspect(block_id)}
            for block_id in self._snap.signal_block_ids
            if block_id.startswith(self._line + " ")
        ]

    @Property(list, notify=changed)
    def sectionRows(self) -> list[dict[str, Any]]:
        """Heaters and track temperature for each section of the line."""
        out = self._snap.outputs.controller
        sections: dict[str, None] = {}
        for b in self._snap.blocks:
            if b.line == self._line:
                sections.setdefault(b.section_id)
        return [
            {
                "section": s.split(" ", 1)[1],
                "heater": "ON" if out.heater_states.get(s) else "OFF",
                "temp": self._temp_f(out.track_temp_c.get(s)),
            }
            for s in sections
        ]

    @Property(list, notify=changed)
    def trainRows(self) -> list[dict[str, Any]]:
        """Every train on the track."""
        return [
            {
                "id": t.train_id,
                "block": t.block_id,
                "offset": f"{t.offset_m * FT_PER_M:.0f}",
                "speed": f"{t.actual_speed_mps * MPH_PER_MPS:.1f}",
            }
            for t in self._snap.trains
        ]

    @Property(list, notify=changed)
    def stationRows(self) -> list[dict[str, Any]]:
        """Waiting passengers by station, on the current line."""
        names = {
            b.station_name for b in self._snap.blocks
            if b.line == self._line and b.station_name is not None
        }
        return [
            {"station": name, "waiting": count}
            for name, count in sorted(self._snap.waiting_passengers.items())
            if name in names
        ]

    @Property(int, notify=changed)
    def failureCount(self) -> int:
        """Blocks with an active failure, on every line."""
        return sum(
            f is not TrackFailure.NONE
            for f in self._snap.outputs.controller.failure_status.values()
        )

    # -- selected block and Murphy -----------------------------------------

    @Property(str, notify=viewChanged)
    def selectedBlock(self) -> str:
        """The block in focus, or empty."""
        return self._selected

    @Slot(str)
    def selectBlock(self, block_id: str) -> None:
        """Focus a block."""
        if block_id != self._selected:
            self._selected = block_id
            self.viewChanged.emit()
            self.changed.emit()

    @Property(list, notify=changed)
    def selectedDetails(self) -> list[dict[str, str]]:
        """Key/value rows describing the block in focus."""
        block = next(
            (b for b in self._snap.blocks if b.block_id == self._selected),
            None,
        )
        if block is None:
            return []
        out = self._snap.outputs.controller
        rows = [
            ("Length", f"{block.length_m * FT_PER_M:.0f} ft"),
            ("Grade", f"{block.grade_deg:.2f}°"),
            ("Speed limit",
             f"{block.speed_limit_mps * MPH_PER_MPS:.0f} mph"),
            ("Elevation", f"{block.elevation_m * FT_PER_M:.1f} ft"),
            ("Station", block.station_name or "—"),
            ("Platform", block.platform_side or "—"),
            ("Direction", self._direction_long(block)),
            ("Beacon", self._beacon_long(block.block_id)),
            ("Heater",
             f"Section {block.section}: "
             + ("ON" if out.heater_states.get(block.section_id) else "OFF")),
            ("Track temp",
             self._temp_f(out.track_temp_c.get(block.section_id))),
            ("Underground", "Yes" if block.underground else "No"),
            ("Crossing", self._crossing(block.block_id)),
            ("Signal", self._aspect(block.block_id) or "—"),
            ("Occupied",
             "Yes" if out.block_occupancy[block.block_id] else "No"),
        ]
        return [{"label": k, "value": v} for k, v in rows]

    @Property(list, constant=True)
    def failureModes(self) -> list[str]:
        """Failure modes Murphy can choose."""
        return list(FAILURE_MODES)

    @Property(int, notify=changed)
    def selectedFailureIndex(self) -> int:
        """Index into ``failureModes`` of the focused block's failure."""
        status = self._snap.outputs.controller.failure_status
        failure = status.get(self._selected, TrackFailure.NONE)
        return FAILURE_MODES.index(failure.name)

    @Slot(str)
    def setSelectedFailure(self, name: str) -> None:
        """Murphy: inject or clear a failure on the block in focus."""
        if not self._selected or name not in FAILURE_MODES:
            return
        self._model.set_block_failure(self._selected, TrackFailure[name])
        self._on_ui_action()
        self.refresh()

    # -- internals ---------------------------------------------------------

    def _beacon_short(self, block_id: str) -> str:
        # Table cell: the beacon's station, or empty.
        beacon = self._snap.beacons.get(block_id)
        return "" if beacon is None else beacon.station_name

    def _beacon_long(self, block_id: str) -> str:
        # Detail row: station, platform side and underground flag.
        beacon = self._snap.beacons.get(block_id)
        if beacon is None:
            return "—"
        side = {"L": "left", "R": "right", "LR": "both sides"}.get(
            beacon.platform_side or "", "side unknown")
        where = "underground" if beacon.underground else "above ground"
        return f"{beacon.station_name}, {side}, {where}"

    @staticmethod
    def _temp_f(temp_c: float | None) -> str:
        # A backend temperature for display, in Fahrenheit.
        return "—" if temp_c is None else f"{c_to_f(temp_c):.1f} °F"

    @staticmethod
    def _direction_short(block: Block) -> str:
        # Table cell: "<->" both ways, "-> C-11" one way, "" unannotated.
        if not block.next_block_ids:
            return ""
        if block.bidirectional:
            return "↔"
        return "→ " + ", ".join(
            "YARD" if b is None else b.split(" ", 1)[1]
            for b in block.next_block_ids
        )

    @staticmethod
    def _direction_long(block: Block) -> str:
        # Detail row, naming every block a train may move on to.
        if not block.next_block_ids:
            return "Not set for this line"
        names = ", ".join(
            "the yard" if b is None else b for b in block.next_block_ids
        )
        return ("Both ways: " if block.bidirectional
                else "One way to ") + names

    def _aspect(self, block_id: str) -> str:
        # Signal colour on a block, or empty where there is no light.
        aspect = self._snap.outputs.controller.signal_states.get(block_id)
        return "" if aspect is None else aspect.name

    def _crossing(self, block_id: str) -> str:
        # Gate state on a block, or a dash where there is no crossing.
        closed = self._snap.outputs.controller.crossing_states.get(block_id)
        if closed is None:
            return "—"
        return "Gates down" if closed else "Gates up"

    def _set_running(self, running: bool) -> None:
        # Emit only on change.
        if running != self._running:
            self._running = running
            self.runningChanged.emit()
