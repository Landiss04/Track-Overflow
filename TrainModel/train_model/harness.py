"""Test harness state for the standalone Train Model page.

The harness supplies every input the Train Model would otherwise receive
from the Track Model and the Train Controller, so the module can be run
and graded on its own.

Rows are built from the interface dictionary (v0.2). Array-valued
signals are presented as one row per element: ``Light Command``
(``bool[2]``) becomes the interior and exterior rows, ``Door command``
(``bool[2]``) becomes left and right, and the ``Track Signal`` struct is
flattened into its fields.

Controls read live model state, with explicitly staged edits marked pending.
Sending applies those edits and advances one tick. Later ticks reuse the
model's accepted producer inputs. A boarding count is consumed once and
must be entered again for a later boarding event.
"""

from __future__ import annotations

from typing import Any, cast

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
from train_model.model import InvalidTimeStepError

#: Inputs, in interface-dictionary order. ``kind`` drives which editor
#: the view renders; ``unit`` is empty where the signal is
#: dimensionless. Units are display units; pending and accepted values stay SI.
INPUT_SPEC: tuple[dict[str, Any], ...] = (
    {"name": "power_command", "kind": "float", "unit": "kW"},
    {
        "name": "service_brake_command",
        "kind": "bool",
        "unit": "",
    },
    {
        "name": "emergency_brake_command",
        "kind": "bool",
        "unit": "",
    },
    {
        "name": "interior_light_command",
        "kind": "bool",
        "unit": "",
    },
    {
        "name": "exterior_light_command",
        "kind": "bool",
        "unit": "",
    },
    {"name": "left_door_command", "kind": "bool", "unit": ""},
    {"name": "right_door_command", "kind": "bool", "unit": ""},
    {"name": "commanded_speed", "kind": "float", "unit": "mph"},
    {
        "name": "authority_block",
        "kind": "string",
        "unit": "",
    },
    {
        "name": "beacon_station",
        "kind": "string",
        "unit": "",
    },
    {
        "name": "beacon_platform_side",
        "kind": "string",
        "unit": "",
    },
    {
        "name": "beacon_underground",
        "kind": "bool",
        "unit": "",
    },
    {"name": "block", "kind": "string", "unit": ""},
    {"name": "grade", "kind": "float", "unit": "deg"},
    {"name": "elevation", "kind": "float", "unit": "ft"},
    {"name": "speed_limit", "kind": "float", "unit": "mph"},
    # Track circuit polarity; flipping it is a block change.
    {"name": "polarity", "kind": "bool", "unit": ""},
    # Station in the current block; empty where there is none.
    {"name": "station", "kind": "string", "unit": ""},
    {"name": "passengers_boarded", "kind": "int", "unit": ""},
    {"name": "temperature_setpoint", "kind": "float", "unit": "°F"},
    {
        "name": "announcement",
        "kind": "string",
        "unit": "",
    },
)

#: Outputs read back from the module, in interface-dictionary order.
_OUTPUT_SPEC: tuple[tuple[str, str, str, str], ...] = (
    ("emergency_brake_state", "bool", "", "emergency_brake"),
    ("service_brake_state", "bool", "", "service_brake"),
    ("left_door_state", "bool", "", "left_door"),
    ("right_door_state", "bool", "", "right_door"),
    ("interior_light_state", "bool", "", "interior_light"),
    ("exterior_light_state", "bool", "", "exterior_light"),
    ("cabin_temp", "float", "°F", "cabin_temp"),
    ("commanded_speed", "float", "mph", "commanded_speed"),
    ("authority", "string", "", "authority_block"),
    ("beacon_station", "string", "", "beacon_station"),
    ("beacon_platform_side", "string", "", "beacon_platform_side"),
    ("beacon_underground", "bool", "", "beacon_underground"),
    ("position_block", "string", "", "current_block"),
    ("position_offset", "float", "ft", "position_offset"),
    ("actual_speed", "float", "mph", "actual_speed"),
    ("passengers", "int", "", "passengers"),
    ("passenger_capacity", "int", "", "passenger_capacity"),
    ("block_changed", "bool", "", "block_changed"),
    ("speed_limit", "float", "mph", "speed_limit"),
)

# Float outputs are shown to this many decimal places.
_OUTPUT_DECIMALS = 3

_DEFAULT_DT = 0.100
_DISPLAY_FACTORS = {"mph": 2.236936, "ft": 3.280840, "kW": 0.001}


class TestHarnessState(QObject):
    """Editable inputs, read-only outputs and run control (page 3b)."""

    inputsChanged = Signal()
    outputsChanged = Signal()
    runControlChanged = Signal()
    inputErrorChanged = Signal()

    def __init__(
        self, model: TrainModelState, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._input_error = ""
        self._pending_inputs: dict[str, Any] = {}
        self._live_inputs = model.live_input_values()
        self._emergency_override_pending = False
        self._running = False
        self._tick = 0
        self._dt = _DEFAULT_DT
        self._timer = QTimer(self)
        self._timer.setInterval(round(self._dt * 1000))
        self._timer.timeout.connect(self._step)
        self._model.snapshotChanged.connect(self.outputsChanged)
        self._model.failuresChanged.connect(self.outputsChanged)
        self._model.snapshotChanged.connect(self._sync_inputs)

    def _sync_inputs(self) -> None:
        live = self._model.live_input_values()
        if live != self._live_inputs:
            self._live_inputs = live
            self.inputsChanged.emit()

    @Property("QVariantList", constant=True)  # type: ignore[arg-type]
    def inputDefinitions(self) -> list[dict[str, Any]]:
        """Stable row identities: ticks must not recreate focused editors."""
        return [
            {key: row[key] for key in ("name", "kind", "unit")}
            for row in INPUT_SPEC
        ]

    @Property("QVariantMap", notify=inputsChanged)  # type: ignore[arg-type]
    def inputValues(self) -> dict[str, Any]:
        """Backend values for Python callers; QML uses displayInputValues."""
        return self._live_inputs | self._pending_inputs

    @Property("QVariantMap", notify=inputsChanged)  # type: ignore[arg-type]
    def displayInputValues(self) -> dict[str, Any]:
        """Convert only at the view boundary; retain SI in pending commands."""
        return self._display_values()

    def _display_values(self) -> dict[str, Any]:
        values = self._live_inputs | self._pending_inputs
        return {
            row["name"]: self._format(
                row["kind"], self._to_display(row["unit"], values[row["name"]]),
                decimals=6,
            )
            for row in INPUT_SPEC
        }

    @Property(str, notify=inputErrorChanged)
    def inputError(self) -> str:
        """Visible rejection reason; drafts remain available for correction."""
        return self._input_error

    def _set_input_error(self, message: str) -> None:
        if message != self._input_error:
            self._input_error = message
            self.inputErrorChanged.emit()

    @Property("QVariantMap", notify=inputsChanged)  # type: ignore[arg-type]
    def pendingInputs(self) -> dict[str, Any]:
        """Which displayed values have not yet been sent."""
        return {name: True for name in self._pending_inputs}

    @Property("QVariantList", notify=inputsChanged)  # type: ignore[arg-type]
    def inputs(self) -> list[dict[str, Any]]:
        """Editable input rows."""
        values = self._display_values()
        return [dict(row, value=values[row["name"]]) for row in INPUT_SPEC]

    @Property("QVariantList", notify=outputsChanged)  # type: ignore[arg-type]
    def outputs(self) -> list[dict[str, Any]]:
        """Read-only output rows resolved from the module snapshot."""
        snapshot = cast(dict[str, Any], self._model.snapshot)
        rows: list[dict[str, Any]] = [
            {
                "name": name,
                "kind": kind,
                "unit": unit,
                "value": self._format(
                    kind, self._to_display(unit, snapshot[field])
                ),
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

    @Property(str, notify=outputsChanged)
    def elapsed(self) -> str:
        """Elapsed simulated time as ``hh:mm:ss``."""
        snapshot = cast(dict[str, Any], self._model.snapshot)
        return str(snapshot["clock"])

    @Slot(str, "QVariant")
    def setDisplayInput(self, name: str, value: Any) -> None:
        """Accept editor units and convert to the backend before staging."""
        for row in INPUT_SPEC:
            if row["name"] == name:
                self.setInput(name, self._from_display(
                    row["unit"], self._coerce(row["kind"], value)
                ))
                return
        raise KeyError(f"unknown input: {name}")

    def setInput(self, name: str, value: Any) -> None:
        """Stage a backend-unit value from Python (not a QML entry point)."""
        for row in INPUT_SPEC:
            if row["name"] != name:
                continue
            coerced = self._coerce(row["kind"], value)
            if name == "emergency_brake_command":
                # Clicking False must work even if the input is already
                # False but the separate passenger latch is active.
                self._emergency_override_pending = True
            if (name in self._pending_inputs
                    and self._pending_inputs[name] == coerced):
                return
            self._pending_inputs[name] = coerced
            self.inputsChanged.emit()
            return
        raise KeyError(f"unknown input: {name}")

    @Slot(result=bool)
    def sendInputs(self) -> bool:
        """Submit a valid tick, or retain state and drafts with an error."""
        values = self._model.command_values() | self._pending_inputs
        try:
            inputs = self._build_inputs(values)
            self._model.step(
                self._dt, inputs,
                override_passenger_brake=self._emergency_override_pending,
            )
        except (ValueError, InvalidTimeStepError) as exc:
            self.setRunning(False)
            self._set_input_error(str(exc))
            return False
        self._emergency_override_pending = False
        self._pending_inputs.clear()
        self._tick += 1
        self._sync_inputs()
        self._set_input_error("")
        self.inputsChanged.emit()
        self.runControlChanged.emit()
        return True

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
        """Restore a fresh model, live inputs and zero counters."""
        self._timer.stop()
        self._set_input_error("")
        self._pending_inputs.clear()
        self._emergency_override_pending = False
        self._tick = 0
        self._running = False
        self._model.reset()
        self.inputsChanged.emit()
        self.runControlChanged.emit()

    def _step(self) -> None:
        # The first tick may submit pending edits. Later ticks use only
        # accepted model inputs; they never overwrite or submit drafts.
        if self._tick == 0 and self._pending_inputs:
            self.sendInputs()
            return
        self._model.step(
            self._dt, self._build_inputs(self._model.command_values())
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
                    station_name=values["station"] or None,
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
    def _to_display(unit: str, value: Any) -> Any:
        """Canonical display factors from truth/conventions/units.md."""
        if unit == "°F":
            return value * 9 / 5 + 32
        factor = _DISPLAY_FACTORS.get(unit)
        return value * factor if factor is not None else value

    @staticmethod
    def _from_display(unit: str, value: Any) -> Any:
        if unit == "°F":
            return (value - 32) * 5 / 9
        factor = _DISPLAY_FACTORS.get(unit)
        return value / factor if factor is not None else value

    @staticmethod
    def _format(
        kind: str, value: Any, decimals: int = _OUTPUT_DECIMALS,
    ) -> Any:
        """Round a numeric output for display in its declared kind."""
        if kind == "int":
            return round(value)
        if kind == "float":
            return round(value, decimals)
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
