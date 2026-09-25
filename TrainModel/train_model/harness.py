"""Test harness state for the standalone Train Model page.

The harness supplies every input the Train Model would otherwise receive
from the Track Model and the Train Controller, so the module can be run and
graded on its own.

Rows are built from the interface dictionary (v0.2). Array-valued signals
are presented as one row per element: ``Light Command`` (``bool[2]``) becomes
the cabin and headlight rows, ``Door command`` (``bool[2]``) becomes left and
right, and the ``Track Signal`` struct is flattened into its fields.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from train_model.state import FAILURE_MODES, TrainModelState

#: Inputs, in interface-dictionary order. ``kind`` drives which editor the
#: view renders; ``unit`` is empty where the signal is dimensionless.
INPUT_SPEC: tuple[dict[str, Any], ...] = (
    {"name": "power_command", "kind": "float", "unit": "W", "value": 118000.0},
    {
        "name": "service_brake_command",
        "kind": "bool",
        "unit": "",
        "value": False,
    },
    {
        "name": "emergency_brake_command",
        "kind": "bool",
        "unit": "",
        "value": False,
    },
    {"name": "cabin_light_command", "kind": "bool", "unit": "", "value": True},
    {"name": "headlight_command", "kind": "bool", "unit": "", "value": True},
    {"name": "left_door_command", "kind": "bool", "unit": "", "value": False},
    {"name": "right_door_command", "kind": "bool", "unit": "", "value": False},
    {"name": "commanded_speed", "kind": "float", "unit": "m/s", "value": 16.0},
    {
        "name": "authority_block",
        "kind": "string",
        "unit": "",
        "value": "GREEN M",
    },
    {
        "name": "authority_distance",
        "kind": "float",
        "unit": "m",
        "value": 410.0,
    },
    {
        "name": "beacon_station",
        "kind": "string",
        "unit": "",
        "value": "Dormont",
    },
    {
        "name": "beacon_platform_side",
        "kind": "string",
        "unit": "",
        "value": "L",
    },
    {
        "name": "beacon_underground",
        "kind": "bool",
        "unit": "",
        "value": False,
    },
    {"name": "grade", "kind": "float", "unit": "deg", "value": 0.7},
    {"name": "elevation", "kind": "float", "unit": "m", "value": 0.0},
    {"name": "speed_limit", "kind": "float", "unit": "m/s", "value": 18.0},
    {"name": "passengers_boarded", "kind": "int", "unit": "", "value": 12},
    {"name": "temperature_setpoint", "kind": "int", "unit": "F", "value": 68},
    {
        "name": "announcement",
        "kind": "string",
        "unit": "",
        "value": "Next stop Dormont",
    },
)

#: Which harness input feeds which snapshot field on the Train Model. Only
#: the dictionary's declared pass-through outputs are wired; everything else
#: waits on the simulation.
_PASS_THROUGH: dict[str, str] = {
    "commanded_speed": "commanded_speed",
    "authority_block": "authority_block",
    "authority_distance": "authority_distance",
    "beacon_station": "next_station",
    "beacon_platform_side": "platform_side",
    "grade": "grade",
    "elevation": "elevation",
    "speed_limit": "speed_limit",
    "temperature_setpoint": "cabin_temp",
    "cabin_light_command": "cabin_light",
    "headlight_command": "headlight",
    "left_door_command": "left_door",
    "right_door_command": "right_door",
    "emergency_brake_command": "emergency_brake",
}

#: Outputs read back from the module, in interface-dictionary order.
_OUTPUT_SPEC: tuple[tuple[str, str, str, str], ...] = (
    ("emergency_brake_state", "bool", "", "emergency_brake"),
    ("left_door_state", "bool", "", "left_door"),
    ("right_door_state", "bool", "", "right_door"),
    ("cabin_light_state", "bool", "", "cabin_light"),
    ("headlight_state", "bool", "", "headlight"),
    ("cabin_temp", "int", "F", "cabin_temp"),
    ("commanded_speed", "float", "m/s", "commanded_speed"),
    ("authority", "float", "m", "authority_distance"),
    ("beacon_station", "string", "", "next_station"),
    ("beacon_platform_side", "string", "", "platform_side"),
    ("position_block", "string", "", "current_block"),
    ("position_offset", "float", "m", "position_offset"),
    ("actual_speed", "float", "m/s", "actual_speed"),
)

_DEFAULT_DT = 0.100


class TestHarnessState(QObject):
    """Editable inputs, read-only outputs and run control for page 3b."""

    inputsChanged = Signal()
    outputsChanged = Signal()
    runControlChanged = Signal()

    def __init__(
        self, model: TrainModelState, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._inputs: list[dict[str, Any]] = [dict(row) for row in INPUT_SPEC]
        self._running = False
        self._tick = 0
        self._dt = _DEFAULT_DT
        self._model.snapshotChanged.connect(self.outputsChanged)
        self._model.failuresChanged.connect(self.outputsChanged)

    @Property("QVariantList", notify=inputsChanged)
    def inputs(self) -> list[dict[str, Any]]:
        """Editable input rows."""
        return [dict(row) for row in self._inputs]

    @Property("QVariantList", notify=outputsChanged)
    def outputs(self) -> list[dict[str, Any]]:
        """Read-only output rows, resolved from the module's snapshot."""
        snapshot = self._model.snapshot
        rows: list[dict[str, Any]] = [
            {
                "name": name,
                "kind": kind,
                "unit": unit,
                "value": snapshot[field],
            }
            for name, kind, unit, field in _OUTPUT_SPEC
        ]
        rows.extend(
            {
                "name": name,
                "kind": "bool",
                "unit": "",
                "value": self._model.isFailed(name),
            }
            for name in FAILURE_MODES
        )
        return rows

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

    @Slot(str, "QVariant")
    def setInput(self, name: str, value: Any) -> None:
        """Write one input row, coercing to the declared type."""
        for row in self._inputs:
            if row["name"] != name:
                continue
            coerced = self._coerce(row["kind"], value)
            if row["value"] == coerced:
                return
            row["value"] = coerced
            self.inputsChanged.emit()
            return
        raise KeyError(f"unknown input: {name}")

    @Slot()
    def sendInputs(self) -> None:
        """Push the declared pass-through inputs into the module."""
        for row in self._inputs:
            field = _PASS_THROUGH.get(row["name"])
            if field is not None:
                self._model.update(field, row["value"])

    @Slot(bool)
    def setRunning(self, running: bool) -> None:
        """Run or hold the simulation clock."""
        if self._running == running:
            return
        self._running = running
        self.runControlChanged.emit()

    @Slot()
    def advanceTick(self) -> None:
        """Advance the tick counter by one."""
        self._tick += 1
        self.runControlChanged.emit()

    @Slot()
    def resetModule(self) -> None:
        """Restore the seeded inputs and zero the run counters."""
        self._inputs = [dict(row) for row in INPUT_SPEC]
        self._tick = 0
        self._running = False
        self.inputsChanged.emit()
        self.runControlChanged.emit()

    @staticmethod
    def _coerce(kind: str, value: Any) -> Any:
        """Convert a value from QML into the type the row declares."""
        if kind == "bool":
            return bool(value)
        if kind == "int":
            return int(float(value))
        if kind == "float":
            return float(value)
        return str(value)