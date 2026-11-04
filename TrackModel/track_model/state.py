"""Track Model UI state: the snapshot, in display units, for QML.

Reads ``TrackModel.snapshot()`` and converts to imperial at this layer
only (``truth/conventions/units.md``). Murphy's failure injection and
loading a track from a JSON file are the actions; each calls the module,
then ``on_ui_action`` so the host can tell the test UI at once.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot

from track_model.interface import (
    Block,
    TrackFailure,
    TrackModel,
    TrackModelError,
    TrackModelSnapshot,
)

FT_PER_M = 3.280840
MPH_PER_MPS = 2.236936
#: Paused once no step has arrived for this long.
PAUSED_AFTER_MS = 500

FAILURE_MODES: tuple[str, ...] = tuple(f.name for f in TrackFailure)


SECONDS_PER_DAY = 86_400.0

#: One table's rows, as QML reads them.
Rows = list[dict[str, Any]]


def c_to_f(temp_c: float) -> float:
    """Convert degrees Celsius to Fahrenheit."""
    return temp_c * 9.0 / 5.0 + 32.0


def _clock(seconds: float) -> str:
    # Simulated time as hh:mm:ss.
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class TrackModelState(QObject):
    """Bindable view of one Track Model for the Track Model UI."""

    changed = Signal()
    runningChanged = Signal()
    viewChanged = Signal()
    linesChanged = Signal()
    loadMessageChanged = Signal()
    # One per table, sent only when its rows change (see _publish).
    blockRowsChanged = Signal()
    switchRowsChanged = Signal()
    signalRowsChanged = Signal()
    sectionRowsChanged = Signal()
    trainRowsChanged = Signal()
    stationRowsChanged = Signal()
    selectedDetailsChanged = Signal()

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
        self._load_message = ""
        self._running = False
        # The rows of each table as last told to QML.
        self._tables: dict[str, Rows] = {}
        self._pause_timer = QTimer(self)
        self._pause_timer.setSingleShot(True)
        self._pause_timer.setInterval(PAUSED_AFTER_MS)
        self._pause_timer.timeout.connect(lambda: self._set_running(False))

    # -- host hooks --------------------------------------------------------

    @Slot()
    def refresh(self) -> None:
        """Re-read the module after a step or an action."""
        self._snap = self._model.snapshot()
        self._publish()

    def _publish(self) -> None:
        # Every value may have changed: the header's re-read at once, a
        # table only when its rows differ from those on show. A new
        # rows array re-runs every cell binding, about 2,000 for a
        # line's blocks, and at 10x that held up each step reply.
        self.changed.emit()
        for name, (build, signal) in self._table_builders().items():
            rows = build()
            if rows != self._tables.get(name):
                self._tables[name] = rows
                signal.emit()

    def _table_builders(self) -> dict[str, tuple[Callable[[], Rows], Any]]:
        # Each table's rows builder and its change signal.
        return {
            "blockRows": (self._block_rows, self.blockRowsChanged),
            "switchRows": (self._switch_rows, self.switchRowsChanged),
            "signalRows": (self._signal_rows, self.signalRowsChanged),
            "sectionRows": (self._section_rows, self.sectionRowsChanged),
            "trainRows": (self._train_rows, self.trainRowsChanged),
            "stationRows": (self._station_rows, self.stationRowsChanged),
            "selectedDetails": (
                self._selected_details, self.selectedDetailsChanged
            ),
        }

    def _table(self, name: str) -> Rows:
        # A table's rows as on show, built on first use.
        if name not in self._tables:
            self._tables[name] = self._table_builders()[name][0]()
        return self._tables[name]

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
        """Central clock time of day, or time stepped since reset."""
        sim_time_s = self._snap.sim_time_s
        if sim_time_s is None:
            return _clock(self._snap.elapsed_s)
        # Central clock: 24-hour time of day (D017).
        return _clock(sim_time_s % SECONDS_PER_DAY)

    @Property(str, notify=changed)
    def ambient(self) -> str:
        """Ambient temperature for display."""
        return f"{c_to_f(self._snap.ambient_temp_c):.0f} °F"

    @Property(float, notify=changed)
    def ambientF(self) -> float:
        """Ambient temperature in °F, to edit."""
        return round(c_to_f(self._snap.ambient_temp_c), 1)

    @Slot(float)
    def setAmbientF(self, temp_f: float) -> None:
        """Set the ambient temperature, entered in °F."""
        try:
            self._model.set_ambient_temp((temp_f - 32.0) * 5.0 / 9.0)
        except TrackModelError:
            return
        self._on_ui_action()
        self.refresh()

    # -- line and filter ---------------------------------------------------

    @Property(list, notify=linesChanged)
    def lines(self) -> list[str]:
        """Every loaded line."""
        return list(self._lines)

    @Property(str, notify=loadMessageChanged)
    def loadMessage(self) -> str:
        """Why the last track load failed, or empty."""
        return self._load_message

    @Slot(str)
    def loadLayout(self, url: str) -> None:
        """Load a track from a JSON file chosen in the file dialog.

        ``url`` is the dialog's file URL. The file replaces its line, or
        adds one, and the module restarts. A bad file changes nothing.
        """
        path = QUrl(url).toLocalFile() or url
        try:
            line = self._model.load_layout_file(path)
        except TrackModelError as error:
            self._set_load_message(str(error))
            return
        self._set_load_message("")
        self._snap = self._model.snapshot()
        self._lines = sorted({b.line for b in self._snap.blocks})
        self._line = line
        self._selected = ""
        self._filter = ""
        self.linesChanged.emit()
        self.viewChanged.emit()
        self._on_ui_action()
        self._publish()

    @Slot()
    def clearLoadMessage(self) -> None:
        """Dismiss the load error."""
        self._set_load_message("")

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
            self._publish()

    @Slot(str)
    def setFilter(self, text: str) -> None:
        """Show only blocks whose ID or station contains ``text``."""
        if text != self._filter:
            self._filter = text
            self._publish()

    # -- tables ------------------------------------------------------------

    @Property(list, notify=blockRowsChanged)
    def blockRows(self) -> Rows:
        """Blocks on the current line, after the filter."""
        return self._table("blockRows")

    @Property(list, notify=switchRowsChanged)
    def switchRows(self) -> Rows:
        """Switches on the current line and the light before each."""
        return self._table("switchRows")

    @Property(list, notify=signalRowsChanged)
    def signalRows(self) -> Rows:
        """Signal lights on the current line."""
        return self._table("signalRows")

    @Property(list, notify=sectionRowsChanged)
    def sectionRows(self) -> Rows:
        """Heaters and track temperature for each section of the line."""
        return self._table("sectionRows")

    @Property(list, notify=trainRowsChanged)
    def trainRows(self) -> Rows:
        """Every train on the track."""
        return self._table("trainRows")

    @Property(list, notify=stationRowsChanged)
    def stationRows(self) -> Rows:
        """Waiting passengers by station, on the current line."""
        return self._table("stationRows")

    def _block_rows(self) -> Rows:
        out = self._snap.outputs.controller
        circuit = self._snap.track_circuit
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
                # The line is already in the title, so the table drops it.
                "name": f"{b.section}-{b.number}",
                "direction": self._direction_short(b),
                "length": f"{b.length_m * FT_PER_M:.0f}",
                "grade": f"{b.grade_deg:.2f}",
                "limit": f"{b.speed_limit_mps * MPH_PER_MPS:.0f}",
                "cmdSpeed": self._cmd_speed(b.block_id),
                "authority": str(circuit[b.block_id].authority_blocks),
                "station": station,
                "beacon": self._beacon_short(b.block_id),
                "heat": "ON" if out.heater_states.get(b.section_id) else "",
                "occupied": "TRUE" if out.block_occupancy[b.block_id] else "",
                "signal": self._aspect(b.block_id),
                "failure": "" if failure is TrackFailure.NONE
                else failure.name,
            })
        return rows

    def _switch_rows(self) -> Rows:
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

    def _signal_rows(self) -> Rows:
        return [
            {"id": block_id, "aspect": self._aspect(block_id)}
            for block_id in self._snap.signal_block_ids
            if block_id.startswith(self._line + " ")
        ]

    def _section_rows(self) -> Rows:
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

    def _train_rows(self) -> Rows:
        return [
            {
                "id": t.train_id,
                "block": t.block_id,
                "offset": f"{t.offset_m * FT_PER_M:.0f}",
                "speed": f"{t.actual_speed_mps * MPH_PER_MPS:.1f}",
            }
            for t in self._snap.trains
        ]

    def _station_rows(self) -> Rows:
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
            self._publish()

    @Property(str, notify=changed)
    def selectedSignal(self) -> str:
        """Signal colour on the block in focus, or empty with no light."""
        return self._aspect(self._selected)

    @Property(list, notify=selectedDetailsChanged)
    def selectedDetails(self) -> Rows:
        """Key/value rows describing the block in focus."""
        return self._table("selectedDetails")

    def _selected_details(self) -> Rows:
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
            ("Commanded speed",
             f"{self._cmd_speed(block.block_id)} mph"),
            ("Authority", self._authority(block.block_id)),
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
            ("Switch", self._switch_position(block.block_id)),
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

    def _cmd_speed(self, block_id: str) -> str:
        # Track circuit speed for a block in mph; 0 on a dead circuit.
        signal = self._snap.track_circuit[block_id]
        return f"{signal.commanded_speed_mps * MPH_PER_MPS:.0f}"

    def _authority(self, block_id: str) -> str:
        # Track circuit authority: how many blocks it may still enter.
        blocks = self._snap.track_circuit[block_id].authority_blocks
        return f"{blocks} block" + ("" if blocks == 1 else "s")

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

    def _switch_position(self, block_id: str) -> str:
        # Normal or reverse where the block holds a switch, else a dash.
        state = self._snap.outputs.controller.switch_states.get(block_id)
        return "—" if state is None else state.name

    def _crossing(self, block_id: str) -> str:
        # Gate state on a block, or a dash where there is no crossing.
        closed = self._snap.outputs.controller.crossing_states.get(block_id)
        if closed is None:
            return "—"
        return "Gates down" if closed else "Gates up"

    def _set_load_message(self, message: str) -> None:
        # Emit only on change.
        if message != self._load_message:
            self._load_message = message
            self.loadMessageChanged.emit()

    def _set_running(self, running: bool) -> None:
        # Emit only on change.
        if running != self._running:
            self._running = running
            self.runningChanged.emit()
