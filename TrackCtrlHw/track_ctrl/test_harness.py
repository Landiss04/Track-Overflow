"""Test harness state for the standalone Track Controller test window.

The harness supplies every input the wayside controller would otherwise
receive from the CTC Office, from the Track Model, and from the
programmer, and reads back every output it sends to the CTC Office and
to the Track Model. Signal names, directions and types come from the
wayside controller interface diagram; nothing else on the controller's
current UI is represented here.

Every signal is per block, including speed and authority, which reach a
train down the track circuit of the block it occupies. One block
selector addresses all four signal tables at once.

Values are in backend units (m/s, m), because this page probes the
module interface rather than presenting it to an operator. Authority is
a count of blocks remaining, not a block ID.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, Signal, Slot

#: Enumerations the diagram names but does not enumerate. Kept as plain
#: strings so the harness stays independent of the module's own types.
SWITCH_POSITIONS: tuple[str, ...] = ("NORMAL", "REVERSE")
CROSSING_STATES: tuple[str, ...] = ("GATES UP", "GATES DOWN")
SIGNAL_COLORS: tuple[str, ...] = ("RED", "YELLOW", "GREEN", "SUPER GREEN")
FAILURE_STATUSES: tuple[str, ...] = (
    "NONE",
    "BROKEN_RAIL",
    "TRACK_CIRCUIT",
    "POWER_FAILURE",
)
BLOCK_COMMANDS: tuple[str, ...] = ("OPEN", "CLOSE")

#: Sample territory. Not every block carries a switch, a crossing or a
#: signal; a signal that needs absent equipment is marked as not
#: applying, and the view greys it out and leaves it empty.
BLOCK_SPEC: tuple[dict[str, Any], ...] = (
    {"id": "GREEN E-13", "switch": False, "crossing": False,
     "signal": True},
    {"id": "GREEN E-14", "switch": True, "crossing": False,
     "signal": True},
    {"id": "GREEN E-15", "switch": False, "crossing": True,
     "signal": True},
    {"id": "GREEN E-16", "switch": False, "crossing": False,
     "signal": False},
)

#: Which piece of wayside equipment each signal needs. A signal absent
#: from this table applies to every block.
_EQUIPMENT_BY_SIGNAL: dict[str, str] = {
    "switch_state": "switch",
    "switch_position_command": "switch",
    "crossing_state": "crossing",
    "crossing_state_command": "crossing",
    "signal_color": "signal",
    "signal_light_command": "signal",
}

#: CTC Office to wayside controller, per block.
_CTC_INPUT_SPEC: tuple[dict[str, Any], ...] = (
    {"name": "suggested_speed", "kind": "int", "unit": "m/s", "value": 15},
    {"name": "authority", "kind": "int", "unit": "blocks", "value": 3},
    {
        "name": "block_open_close",
        "kind": "enum",
        "unit": "",
        "options": list(BLOCK_COMMANDS),
        "value": "OPEN",
    },
    {
        "name": "maintenance_mode",
        "kind": "bool",
        "unit": "",
        "value": False,
    },
)

#: Track Model to wayside controller, per block.
_TRACK_MODEL_INPUT_SPEC: tuple[dict[str, Any], ...] = (
    {
        "name": "block_occupancy",
        "kind": "bool",
        "unit": "",
        "value": True,
    },
    {
        "name": "switch_state",
        "kind": "enum",
        "unit": "",
        "options": list(SWITCH_POSITIONS),
        "value": "NORMAL",
    },
    {
        "name": "crossing_state",
        "kind": "enum",
        "unit": "",
        "options": list(CROSSING_STATES),
        "value": "GATES UP",
    },
    {
        "name": "signal_color",
        "kind": "enum",
        "unit": "",
        "options": list(SIGNAL_COLORS),
        "value": "GREEN",
    },
    {
        "name": "track_failure_status",
        "kind": "enum",
        "unit": "",
        "options": list(FAILURE_STATUSES),
        "value": "NONE",
    },
)

#: Wayside controller to CTC Office, per block. Train location and speed
#: report the train occupying this block, if any.
_CTC_OUTPUT_SPEC: tuple[dict[str, Any], ...] = (
    {"name": "block_occupancy", "kind": "bool", "unit": "", "value": None},
    {"name": "switch_state", "kind": "enum", "unit": "", "value": None},
    {"name": "crossing_state", "kind": "enum", "unit": "", "value": None},
    {
        "name": "track_failure_report",
        "kind": "enum",
        "unit": "",
        "value": None,
    },
    {
        "name": "train_location_offset",
        "kind": "float",
        "unit": "m",
        "value": None,
    },
    {"name": "train_speed", "kind": "float", "unit": "m/s", "value": None},
)

#: Wayside controller to Track Model, per block. Speed and authority are
#: addressed to a block because they reach the train down that block's
#: track circuit.
_TRACK_MODEL_OUTPUT_SPEC: tuple[dict[str, Any], ...] = (
    {"name": "commanded_speed", "kind": "int", "unit": "m/s", "value": None},
    {
        "name": "commanded_authority",
        "kind": "int",
        "unit": "blocks",
        "value": None,
    },
    {
        "name": "switch_position_command",
        "kind": "enum",
        "unit": "",
        "value": None,
    },
    {
        "name": "crossing_state_command",
        "kind": "enum",
        "unit": "",
        "value": None,
    },
    {
        "name": "signal_light_command",
        "kind": "enum",
        "unit": "",
        "value": None,
    },
)

#: Group keys, as the view passes them back to ``setInput``.
CTC_GROUP = "ctc"
TRACK_MODEL_GROUP = "track_model"

#: Inputs that relay straight through to an output without PLC logic,
#: as ``(input group, input name) -> (output group, output name)``.
#: Everything else waits on the PLC program, so it stays an em dash.
_PASS_THROUGH: dict[tuple[str, str], tuple[str, str]] = {
    (TRACK_MODEL_GROUP, "block_occupancy"): (CTC_GROUP, "block_occupancy"),
    (TRACK_MODEL_GROUP, "switch_state"): (CTC_GROUP, "switch_state"),
    (TRACK_MODEL_GROUP, "crossing_state"): (CTC_GROUP, "crossing_state"),
    (TRACK_MODEL_GROUP, "track_failure_status"): (
        CTC_GROUP,
        "track_failure_report",
    ),
    (CTC_GROUP, "suggested_speed"): (TRACK_MODEL_GROUP, "commanded_speed"),
    (CTC_GROUP, "authority"): (TRACK_MODEL_GROUP, "commanded_authority"),
}

_DEFAULT_DT = 0.100
_DEFAULT_TICK_STEP = 10


def _coerce(kind: str, value: Any) -> Any:
    """Return ``value`` as the type the named signal kind declares."""
    if kind == "bool":
        return bool(value)
    if kind == "int":
        return int(float(value))
    if kind == "float":
        return float(value)
    return str(value)


def _rows_for_block(
    spec: tuple[dict[str, Any], ...], block: dict[str, Any]
) -> list[dict[str, Any]]:
    """Return one block's own copy of a signal spec.

    A signal needing equipment the block does not have is marked as not
    applying and carries no value, so the view can grey it out.
    """
    rows: list[dict[str, Any]] = []
    for template in spec:
        row = dict(template)
        equipment = _EQUIPMENT_BY_SIGNAL.get(row["name"])
        row["applies"] = equipment is None or bool(block[equipment])
        if not row["applies"]:
            row["value"] = None
        rows.append(row)
    return rows


class TrackCtrlTestHarness(QObject):
    """Editable inputs, read-only outputs, PLC upload and run control."""

    inputsChanged = Signal()
    outputsChanged = Signal()
    selectionChanged = Signal()
    programChanged = Signal()
    runControlChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Set every input, output and clock field to its default."""
        self._inputs = {
            CTC_GROUP: {
                block["id"]: _rows_for_block(_CTC_INPUT_SPEC, block)
                for block in BLOCK_SPEC
            },
            TRACK_MODEL_GROUP: {
                block["id"]: _rows_for_block(_TRACK_MODEL_INPUT_SPEC, block)
                for block in BLOCK_SPEC
            },
        }
        self._outputs = {
            CTC_GROUP: {
                block["id"]: _rows_for_block(_CTC_OUTPUT_SPEC, block)
                for block in BLOCK_SPEC
            },
            TRACK_MODEL_GROUP: {
                block["id"]: _rows_for_block(_TRACK_MODEL_OUTPUT_SPEC, block)
                for block in BLOCK_SPEC
            },
        }
        self._selected_block = str(BLOCK_SPEC[0]["id"])
        self._program_name = ""
        self._running = False
        self._tick = 0
        self._tick_step = _DEFAULT_TICK_STEP
        self._dt = _DEFAULT_DT

    # -- signal tables ---------------------------------------------------

    @Property("QVariantList", notify=inputsChanged)
    def ctcInputs(self) -> list[dict[str, Any]]:
        """Editable rows the CTC Office would send for this block."""
        return self._rows(self._inputs, CTC_GROUP)

    @Property("QVariantList", notify=inputsChanged)
    def trackModelInputs(self) -> list[dict[str, Any]]:
        """Editable rows the Track Model would send for this block."""
        return self._rows(self._inputs, TRACK_MODEL_GROUP)

    @Property("QVariantList", notify=outputsChanged)
    def ctcOutputs(self) -> list[dict[str, Any]]:
        """Read-only rows reported to the CTC Office for this block."""
        return self._rows(self._outputs, CTC_GROUP)

    @Property("QVariantList", notify=outputsChanged)
    def trackModelOutputs(self) -> list[dict[str, Any]]:
        """Read-only rows commanded onto the Track Model for this block."""
        return self._rows(self._outputs, TRACK_MODEL_GROUP)

    # -- selection and program -------------------------------------------

    @Property("QVariantList", constant=True)
    def blocks(self) -> list[str]:
        """Block IDs this wayside governs."""
        return [str(block["id"]) for block in BLOCK_SPEC]

    @Property(str, notify=selectionChanged)
    def selectedBlock(self) -> str:
        """Block every signal table on the page is addressed to."""
        return self._selected_block

    @Property(str, notify=programChanged)
    def programName(self) -> str:
        """File name of the uploaded PLC program, empty if none."""
        return self._program_name

    # -- run control ------------------------------------------------------

    @Property(bool, notify=runControlChanged)
    def running(self) -> bool:
        """Whether the simulation clock is running rather than held."""
        return self._running

    @Property(int, notify=runControlChanged)
    def tick(self) -> int:
        """Ticks elapsed since the last reset."""
        return self._tick

    @Property(int, notify=runControlChanged)
    def tickStep(self) -> int:
        """Ticks one advance moves the clock by."""
        return self._tick_step

    @Property(float, notify=runControlChanged)
    def dt(self) -> float:
        """Seconds per tick."""
        return self._dt

    @Property(str, notify=runControlChanged)
    def elapsed(self) -> str:
        """Elapsed simulated time as ``hh:mm:ss``."""
        total = int(self._tick * self._dt)
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    # -- commands ---------------------------------------------------------

    @Slot(str, str, "QVariant")
    def setInput(self, group: str, name: str, value: Any) -> None:
        """Write one input row of the selected block."""
        rows = self._inputs.get(group, {}).get(self._selected_block, ())
        for row in rows:
            if row["name"] == name and row["applies"]:
                row["value"] = _coerce(row["kind"], value)
                self.inputsChanged.emit()
                return

    @Slot(str)
    def setSelectedBlock(self, block_id: str) -> None:
        """Address every signal table on the page to another block."""
        if block_id != self._selected_block:
            self._selected_block = block_id
            self.selectionChanged.emit()
            self.inputsChanged.emit()
            self.outputsChanged.emit()

    @Slot(str)
    def loadProgram(self, path: str) -> None:
        """Record the PLC program the programmer uploaded."""
        self._program_name = Path(path).name
        self.programChanged.emit()

    @Slot()
    def sendInputs(self) -> None:
        """Push the inputs at the module and read the outputs back.

        Every block resolves, not only the one on screen. Only the
        declared pass-through relays resolve until the PLC program
        drives the rest; every other output stays an em dash.
        """
        for block in BLOCK_SPEC:
            block_id = str(block["id"])
            for (in_group, in_name), (out_group, out_name) in (
                _PASS_THROUGH.items()
            ):
                value = self._value(self._inputs, in_group, block_id, in_name)
                self._set_output(out_group, block_id, out_name, value)
        self.outputsChanged.emit()

    @Slot(bool)
    def setRunning(self, running: bool) -> None:
        """Start or hold the simulation clock."""
        if running != self._running:
            self._running = running
            self.runControlChanged.emit()

    @Slot("QVariant")
    def setTickStep(self, ticks: Any) -> None:
        """Set how many ticks one advance moves the clock by."""
        step = max(1, int(float(ticks)))
        if step != self._tick_step:
            self._tick_step = step
            self.runControlChanged.emit()

    @Slot()
    def advanceTicks(self) -> None:
        """Step the simulation clock by ``tickStep`` ticks."""
        self._tick += self._tick_step
        self.runControlChanged.emit()

    @Slot()
    def resetModule(self) -> None:
        """Restore every input, output and the clock to its default."""
        self._load_defaults()
        self.inputsChanged.emit()
        self.outputsChanged.emit()
        self.selectionChanged.emit()
        self.programChanged.emit()
        self.runControlChanged.emit()

    # -- internals --------------------------------------------------------

    def _rows(
        self, table: dict[str, dict[str, list[dict[str, Any]]]], group: str
    ) -> list[dict[str, Any]]:
        """Return a copy of one group's rows for the selected block."""
        return [dict(row) for row in table[group][self._selected_block]]

    def _value(
        self,
        table: dict[str, dict[str, list[dict[str, Any]]]],
        group: str,
        block_id: str,
        name: str,
    ) -> Any:
        """Return the current value of one row."""
        for row in table[group][block_id]:
            if row["name"] == name:
                return row["value"]
        raise KeyError(f"no signal {group}.{block_id}.{name}")

    def _set_output(
        self, group: str, block_id: str, name: str, value: Any
    ) -> None:
        """Write one output row without emitting."""
        for row in self._outputs[group][block_id]:
            if row["name"] == name and row["applies"]:
                row["value"] = value
                return
