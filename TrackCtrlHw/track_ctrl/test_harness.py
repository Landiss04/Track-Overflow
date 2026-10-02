"""Test harness state for the standalone Track Controller test window.

The harness supplies every input the wayside controller would otherwise
receive from the CTC Office, from the Track Model, and from the
programmer, and reads back every output it sends to the CTC Office and
to the Track Model. Signal names, directions and types come from the
wayside controller interface diagram; nothing else on the controller's
current UI is represented here.

IDs are strings, per ``truth/conventions/identifiers.md`` — including
authority, which names a destination block. Values are in backend units
(m/s, m), because this page probes the module interface rather than
presenting it to an operator.
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

#: Sample territory. The wayside under test owns these blocks, and the
#: CTC inputs below are sent for one train at a time.
TRAIN_IDS: tuple[str, ...] = ("TRN-011", "TRN-014", "TRN-021")
BLOCK_IDS: tuple[str, ...] = (
    "GREEN E-13",
    "GREEN E-14",
    "GREEN E-15",
    "GREEN E-16",
)

#: CTC Office to wayside controller. Per train, except the block
#: open/close command and maintenance mode, which are per block.
_CTC_INPUT_SPEC: tuple[dict[str, Any], ...] = (
    {
        "name": "suggested_speed",
        "kind": "float",
        "unit": "m/s",
        "value": 15.0,
    },
    {
        "name": "authority_block_1",
        "kind": "string",
        "unit": "",
        "value": "GREEN E-16",
    },
    {
        "name": "authority_block_2",
        "kind": "string",
        "unit": "",
        "value": "GREEN E-17",
    },
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

#: Track Model to wayside controller. Per block.
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

#: Wayside controller to CTC Office.
_CTC_OUTPUT_SPEC: tuple[dict[str, Any], ...] = (
    {"name": "block_occupancy", "kind": "bool", "unit": "", "value": None},
    {
        "name": "train_location_block",
        "kind": "string",
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
    {"name": "switch_state", "kind": "enum", "unit": "", "value": None},
    {"name": "crossing_state", "kind": "enum", "unit": "", "value": None},
    {
        "name": "track_failure_report",
        "kind": "enum",
        "unit": "",
        "value": None,
    },
)

#: Wayside controller to Track Model. Per block, except the commanded
#: authority, which names the destination block for one train.
_TRACK_MODEL_OUTPUT_SPEC: tuple[dict[str, Any], ...] = (
    {
        "name": "commanded_speed",
        "kind": "float",
        "unit": "m/s",
        "value": None,
    },
    {
        "name": "commanded_authority",
        "kind": "string",
        "unit": "",
        "value": None,
    },
    {
        "name": "switch_position_command",
        "kind": "enum",
        "unit": "",
        "value": None,
    },
    {
        "name": "crossing_gate_closed",
        "kind": "bool",
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
    (CTC_GROUP, "authority_block_1"): (
        TRACK_MODEL_GROUP,
        "commanded_authority",
    ),
}

_DEFAULT_DT = 0.100


def _coerce(kind: str, value: Any) -> Any:
    """Return ``value`` as the type the named signal kind declares."""
    if kind == "bool":
        return bool(value)
    if kind == "int":
        return int(value)
    if kind == "float":
        return float(value)
    return str(value)


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
        self._inputs: dict[str, list[dict[str, Any]]] = {
            CTC_GROUP: [dict(row) for row in _CTC_INPUT_SPEC],
            TRACK_MODEL_GROUP: [
                dict(row) for row in _TRACK_MODEL_INPUT_SPEC
            ],
        }
        self._outputs: dict[str, list[dict[str, Any]]] = {
            CTC_GROUP: [dict(row) for row in _CTC_OUTPUT_SPEC],
            TRACK_MODEL_GROUP: [
                dict(row) for row in _TRACK_MODEL_OUTPUT_SPEC
            ],
        }
        self._selected_train = TRAIN_IDS[1]
        self._selected_block = BLOCK_IDS[2]
        self._program_name = ""
        self._running = False
        self._tick = 0
        self._dt = _DEFAULT_DT

    # -- signal tables ---------------------------------------------------

    @Property("QVariantList", notify=inputsChanged)
    def ctcInputs(self) -> list[dict[str, Any]]:
        """Editable rows the CTC Office would send to the wayside."""
        return [dict(row) for row in self._inputs[CTC_GROUP]]

    @Property("QVariantList", notify=inputsChanged)
    def trackModelInputs(self) -> list[dict[str, Any]]:
        """Editable rows the Track Model would send to the wayside."""
        return [dict(row) for row in self._inputs[TRACK_MODEL_GROUP]]

    @Property("QVariantList", notify=outputsChanged)
    def ctcOutputs(self) -> list[dict[str, Any]]:
        """Read-only rows the wayside reports to the CTC Office."""
        return [dict(row) for row in self._outputs[CTC_GROUP]]

    @Property("QVariantList", notify=outputsChanged)
    def trackModelOutputs(self) -> list[dict[str, Any]]:
        """Read-only rows the wayside commands onto the Track Model."""
        return [dict(row) for row in self._outputs[TRACK_MODEL_GROUP]]

    # -- selection and program -------------------------------------------

    @Property("QVariantList", constant=True)
    def trains(self) -> list[str]:
        """Train IDs the CTC inputs can be addressed to."""
        return list(TRAIN_IDS)

    @Property("QVariantList", constant=True)
    def blocks(self) -> list[str]:
        """Block IDs this wayside governs."""
        return list(BLOCK_IDS)

    @Property(str, notify=selectionChanged)
    def selectedTrain(self) -> str:
        """Train the per-train inputs apply to."""
        return self._selected_train

    @Property(str, notify=selectionChanged)
    def selectedBlock(self) -> str:
        """Block the per-block inputs and outputs apply to."""
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
        """Write one input row, coercing to the declared kind."""
        for row in self._inputs.get(group, ()):
            if row["name"] == name:
                row["value"] = _coerce(row["kind"], value)
                self.inputsChanged.emit()
                return

    @Slot(str)
    def setSelectedTrain(self, train_id: str) -> None:
        """Address the per-train inputs to another train."""
        if train_id != self._selected_train:
            self._selected_train = train_id
            self.selectionChanged.emit()

    @Slot(str)
    def setSelectedBlock(self, block_id: str) -> None:
        """Address the per-block inputs and outputs to another block."""
        if block_id != self._selected_block:
            self._selected_block = block_id
            self.selectionChanged.emit()

    @Slot(str)
    def loadProgram(self, path: str) -> None:
        """Record the PLC program the programmer uploaded."""
        self._program_name = Path(path).name
        self.programChanged.emit()

    @Slot()
    def sendInputs(self) -> None:
        """Push the inputs at the module and read the outputs back.

        Only the declared pass-through relays resolve until the PLC
        program drives the rest; every other output stays an em dash.
        """
        for (in_group, in_name), (out_group, out_name) in (
            _PASS_THROUGH.items()
        ):
            value = self._input_value(in_group, in_name)
            self._set_output(out_group, out_name, value)
        self._set_output(
            CTC_GROUP, "train_location_block", self._selected_block
        )
        self.outputsChanged.emit()

    @Slot(bool)
    def setRunning(self, running: bool) -> None:
        """Start or hold the simulation clock."""
        if running != self._running:
            self._running = running
            self.runControlChanged.emit()

    @Slot()
    def advanceTick(self) -> None:
        """Step the simulation clock by one tick."""
        self._tick += 1
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

    def _input_value(self, group: str, name: str) -> Any:
        """Return the current value of one input row."""
        for row in self._inputs[group]:
            if row["name"] == name:
                return row["value"]
        raise KeyError(f"no input {group}.{name}")

    def _set_output(self, group: str, name: str, value: Any) -> None:
        """Write one output row without emitting."""
        for row in self._outputs[group]:
            if row["name"] == name:
                row["value"] = value
                return
