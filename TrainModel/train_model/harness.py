"""Test harness state for the standalone Train Model page.

The harness supplies every input the Train Model would otherwise receive
from the Track Model and the Train Controller, so the module can be run
and graded on its own.

Rows are built from the interface dictionary (v0.2). Array-valued
signals are presented as one row per element: ``Light Command``
(``bool[2]``) becomes the interior and exterior rows, ``Door command``
(``bool[2]``) becomes left and right, and the ``Track Signal`` struct is
flattened into its fields.

Sending the inputs hands them to the Train Model and advances one tick.
The model then keeps receiving the last sent inputs on every tick,
whether advanced by hand or by the running clock, except that
``passengers_boarded`` is applied once per send: the Track Model reports
a boarding count on one tick only.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from train_model.interface import (
    Beacon,
    ControllerCommands,
    TrackInfo,
    TrackInputs,
    TrackSignal,
    TrainModelInputs,
)
from train_model.state import FAILURE_MODES, TrainModelState

#: Inputs, in interface-dictionary order. ``kind`` drives which editor
#: the view renders; ``unit`` is empty where the signal is
#: dimensionless.
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
    {
        "name": "interior_light_command",
        "kind": "bool",
        "unit": "",
        "value": True,
    },
    {
        "name": "exterior_light_command",
        "kind": "bool",
        "unit": "",
        "value": True,
    },
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
    {"name": "block", "kind": "string", "unit": "", "value": "GREEN I"},
    {"name": "grade", "kind": "float", "unit": "deg", "value": 0.7},
    {"name": "elevation", "kind": "float", "unit": "m", "value": 0.0},
    {"name": "speed_limit", "kind": "float", "unit": "m/s", "value": 18.0},
    # Track circuit polarity; flipping it is a block change.
    {"name": "polarity", "kind": "bool", "unit": "", "value": False},
    {"name": "passengers_boarded", "kind": "int", "unit": "", "value": 12},
    {"name": "temperature_setpoint", "kind": "int", "unit": "C", "value": 20},
    {
        "name": "announcement",
        "kind": "string",
        "unit": "",
        "value": "Next stop Dormont",
    },
)

#: Harness inputs the Train Model does not report back, shown on the
#: overview as sent: the ``grade`` and ``elevation`` readouts.
_DISPLAY_ONLY: dict[str, str] = {
    "grade": "grade",
    "elevation": "elevation",
}

#: Outputs read back from the module, in interface-dictionary order.
_OUTPUT_SPEC: tuple[tuple[str, str, str, str], ...] = (
    ("emergency_brake_state", "bool", "", "emergency_brake"),
    ("service_brake_state", "bool", "", "service_brake"),
    ("left_door_state", "bool", "", "left_door"),
    ("right_door_state", "bool", "", "right_door"),
    ("interior_light_state", "bool", "", "interior_light"),
    ("exterior_light_state", "bool", "", "exterior_light"),
    ("cabin_temp", "int", "C", "cabin_temp"),
    ("commanded_speed", "float", "m/s", "commanded_speed"),
    ("authority", "string", "", "authority_block"),
    ("beacon_station", "string", "", "next_station"),
    ("beacon_platform_side", "string", "", "platform_side"),
    ("position_block", "string", "", "current_block"),
    ("position_offset", "float", "m", "position_offset"),
    ("actual_speed", "float", "m/s", "actual_speed"),
    ("passengers", "int", "", "passengers"),
)

# Float outputs are shown to this many decimal places.
_OUTPUT_DECIMALS = 3

_DEFAULT_DT = 0.100


class TestHarnessState(QObject):
    """Editable inputs, read-only outputs and run control (page 3b)."""

    inputsChanged = Signal()
    outputsChanged = Signal()
    runControlChanged = Signal()

    def __init__(
        self, model: TrainModelState, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._inputs: list[dict[str, Any]] = [dict(row) for row in INPUT_SPEC]
        # The inputs the model receives each tick; None until a send.
        self._sent: TrainModelInputs | None = None
        self._running = False
        self._tick = 0
        self._dt = _DEFAULT_DT
        self._timer = QTimer(self)
        self._timer.setInterval(round(self._dt * 1000))
        self._timer.timeout.connect(self._step)
        self._model.snapshotChanged.connect(self.outputsChanged)
        self._model.failuresChanged.connect(self.outputsChanged)

    @Property("QVariantList", notify=inputsChanged)
    def inputs(self) -> list[dict[str, Any]]:
        """Editable input rows."""
        return [dict(row) for row in self._inputs]

    @Property("QVariantList", notify=outputsChanged)
    def outputs(self) -> list[dict[str, Any]]:
        """Read-only output rows resolved from the module snapshot."""
        snapshot = self._model.snapshot
        rows: list[dict[str, Any]] = [
            {
                "name": name,
                "kind": kind,
                "unit": unit,
                "value": self._format(kind, snapshot[field]),
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
        """Hand the inputs to the Train Model and advance one tick."""
        values = {row["name"]: row["value"] for row in self._inputs}
        self._sent = self._build_inputs(values)
        self._model.update_many(
            {field: values[name] for name, field in _DISPLAY_ONLY.items()}
        )
        self._step()

    @Slot(bool)
    def setRunning(self, running: bool) -> None:
        """Run or hold the simulation clock."""
        if self._running == running:
            return
        self._running = running
        if running:
            self._timer.start()
        else:
            self._timer.stop()
        self.runControlChanged.emit()

    @Slot()
    def advanceTick(self) -> None:
        """Advance the Train Model one tick on the last sent inputs."""
        self._step()

    @Slot()
    def resetModule(self) -> None:
        """Restore the seeded inputs, a fresh model and zero counters."""
        self._timer.stop()
        self._inputs = [dict(row) for row in INPUT_SPEC]
        self._sent = None
        self._tick = 0
        self._running = False
        self._model.reset()
        self.inputsChanged.emit()
        self.runControlChanged.emit()

    def _step(self) -> None:
        # One tick. Before the first send, nothing has been sent, so
        # the inputs as they stand are sent first.
        if self._sent is None:
            self.sendInputs()
            return
        self._model.step(self._dt, self._sent)
        # Boarding is reported on one tick only.
        self._sent = replace(
            self._sent,
            track=replace(self._sent.track, passengers_boarded=0),
        )
        self._tick += 1
        self.runControlChanged.emit()

    @staticmethod
    def _build_inputs(values: dict[str, Any]) -> TrainModelInputs:
        """Map the harness rows onto the Train Model's input types."""
        station = values["beacon_station"]
        side = values["beacon_platform_side"].upper()
        beacon: Beacon | None = None
        if station:
            if side not in ("L", "R"):
                raise ValueError(
                    f"beacon_platform_side must be L or R, got {side!r}"
                )
            beacon = Beacon(
                station_name=station,
                platform_side="L" if side == "L" else "R",
                underground=values["beacon_underground"],
            )
        return TrainModelInputs(
            controller=ControllerCommands(
                power_cmd_w=values["power_command"],
                service_brake=values["service_brake_command"],
                emergency_brake=values["emergency_brake_command"],
                interior_lights=values["interior_light_command"],
                exterior_lights=values["exterior_light_command"],
                door_left_open=values["left_door_command"],
                door_right_open=values["right_door_command"],
                temp_setpoint_c=float(values["temperature_setpoint"]),
                announcement=values["announcement"],
            ),
            track=TrackInputs(
                track_info=TrackInfo(
                    block_id=values["block"],
                    grade_deg=values["grade"],
                    elevation_m=values["elevation"],
                    speed_limit_mps=values["speed_limit"],
                    polarity=values["polarity"],
                ),
                track_signal=TrackSignal(
                    commanded_speed_mps=values["commanded_speed"],
                    authority_block_id=values["authority_block"],
                ),
                beacon=beacon,
                passengers_boarded=values["passengers_boarded"],
            ),
        )

    @staticmethod
    def _format(kind: str, value: Any) -> Any:
        """Round a numeric output for display in its declared kind."""
        if kind == "int":
            return round(value)
        if kind == "float":
            return round(value, _OUTPUT_DECIMALS)
        return value

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
