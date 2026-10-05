"""Test harness state for the Train Model test UI.

The harness supplies every input the Train Model would otherwise receive
from the Track Model and the Train Controller, and drives the clock, so
the module can be run and graded on its own. It runs in the test UI's
own process and reaches the module only through its boundary, over a
link (``train_model/link.py``): it sends ``TrainModelInputs`` each tick
and reads back only ``TrainModelOutputs``.

Rows are built from the interface dictionary (v0.2). Array-valued
signals are presented as one row per element: ``Light Command``
(``bool[2]``) becomes the interior and exterior rows, ``Door command``
(``bool[2]``) becomes left and right, and the ``Track Signal`` struct is
flattened into its fields.

Controls read back live state from the outputs, with staged edits marked
pending. Sending applies those edits and advances one tick. Later ticks
reuse the last accepted inputs. A boarding count is consumed once and
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
    TrainModelOutputs,
)
from train_model.link import LinkError, LocalLink, SocketLink
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
    {"name": "authority", "kind": "int", "unit": "blocks"},
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
#: Only cross-module outputs: what the Track Model and the Train
#: Controller would receive.
_OUTPUT_SPEC: tuple[tuple[str, str, str], ...] = (
    ("emergency_brake_state", "bool", ""),
    ("service_brake_state", "bool", ""),
    ("left_door_state", "bool", ""),
    ("right_door_state", "bool", ""),
    ("interior_light_state", "bool", ""),
    ("exterior_light_state", "bool", ""),
    ("cabin_temp", "float", "°F"),
    ("commanded_speed", "float", "mph"),
    ("authority", "int", "blocks"),
    ("beacon_station", "string", ""),
    ("beacon_platform_side", "string", ""),
    ("beacon_underground", "bool", ""),
    ("position_block", "string", ""),
    ("position_offset", "float", "ft"),
    ("actual_speed", "float", "mph"),
    ("passenger_capacity", "int", ""),
    ("block_changed", "bool", ""),
    ("speed_limit", "float", "mph"),
)

#: Failure Status element for each failure mode.
_FAILURE_FIELDS: dict[str, str] = {
    "engine_failure": "engine",
    "signal_pickup_failure": "signal_pickup",
    "brake_failure": "brake",
}

# Shown where the module reports no block.
_NONE_SHOWN = "—"

#: What the stand-in producers send before anything has been entered.
_INITIAL_COMMANDS: dict[str, Any] = {
    "power_command": 0.0, "service_brake_command": False,
    "emergency_brake_command": False,
    "interior_light_command": False,
    "exterior_light_command": False,
    "left_door_command": False, "right_door_command": False,
    "commanded_speed": 0.0, "authority": 0,
    "beacon_station": "", "beacon_platform_side": "L",
    "beacon_underground": False, "block": "", "grade": 0.0,
    "elevation": 0.0, "speed_limit": 0.0, "polarity": False,
    "station": "", "passengers_boarded": 0,
    "temperature_setpoint": 20.0, "announcement": "",
}

# Float outputs are shown to this many decimal places.
_OUTPUT_DECIMALS = 3

_DEFAULT_DT = 0.100
_DISPLAY_FACTORS = {"mph": 2.236936, "ft": 3.280840, "kW": 0.001}

#: Either link: in this process (tests) or in the Train Model process.
Link = LocalLink | SocketLink


def _output_values(outputs: TrainModelOutputs) -> dict[str, Any]:
    """Output rows' backend values, keyed by row name."""
    ctl, trk, beacon = outputs.controller, outputs.track, (
        outputs.controller.beacon
    )
    return {
        "emergency_brake_state": ctl.emergency_brake_active,
        "service_brake_state": ctl.service_brake_active,
        "left_door_state": ctl.door_left_open,
        "right_door_state": ctl.door_right_open,
        "interior_light_state": ctl.interior_lights_on,
        "exterior_light_state": ctl.exterior_lights_on,
        "cabin_temp": ctl.cabin_temp_c,
        "commanded_speed": ctl.commanded_speed_mps,
        "authority": ctl.authority_blocks,
        "beacon_station": beacon.station_name if beacon else "",
        "beacon_platform_side": beacon.platform_side if beacon else "",
        "beacon_underground": beacon.underground if beacon else False,
        "position_block": trk.block_id or _NONE_SHOWN,
        "position_offset": trk.offset_m,
        "actual_speed": ctl.actual_speed_mps,
        "passenger_capacity": trk.passenger_capacity,
        "block_changed": trk.block_changed,
        "speed_limit": ctl.speed_limit_mps,
    }


def _live_values(outputs: TrainModelOutputs) -> dict[str, Any]:
    """Input rows that read back what the train is actually doing."""
    ctl = outputs.controller
    return {
        "service_brake_command": ctl.service_brake_active,
        "emergency_brake_command": ctl.emergency_brake_active,
        "interior_light_command": ctl.interior_lights_on,
        "exterior_light_command": ctl.exterior_lights_on,
        "left_door_command": ctl.door_left_open,
        "right_door_command": ctl.door_right_open,
        "commanded_speed": ctl.commanded_speed_mps,
        "authority": ctl.authority_blocks,
    }


class TestHarnessState(QObject):
    """Stand-in producers and clock for the Train Model (page 3b)."""

    inputsChanged = Signal()
    outputsChanged = Signal()
    runControlChanged = Signal()
    inputErrorChanged = Signal()
    connectedChanged = Signal()

    def __init__(self, link: Link, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._link = link
        self._input_error = ""
        # The commands the module last accepted from these producers.
        self._accepted: dict[str, Any] = dict(_INITIAL_COMMANDS)
        self._pending_inputs: dict[str, Any] = {}
        self._live_inputs = self._live_input_values()
        self._emergency_override_pending = False
        self._running = False
        self._tick = 0
        self._dt = _DEFAULT_DT
        self._timer = QTimer(self)
        self._timer.setInterval(round(self._dt * 1000))
        self._timer.timeout.connect(self._step)
        link.outputsChanged.connect(self.outputsChanged)
        link.outputsChanged.connect(self._sync_inputs)
        link.connectedChanged.connect(self.connectedChanged)

    def _live_input_values(self) -> dict[str, Any]:
        # Live controls reflect actual state, not hidden stored commands.
        values = dict(self._accepted)
        outputs = self._link.outputs
        if outputs is not None:
            values |= _live_values(outputs)
        return values

    def _sync_inputs(self) -> None:
        live = self._live_input_values()
        if live != self._live_inputs:
            self._live_inputs = live
            self.inputsChanged.emit()

    @Property(bool, notify=connectedChanged)
    def connected(self) -> bool:
        """Whether the Train Model can be reached."""
        return self._link.connected

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
        """Read-only output rows; empty values while disconnected."""
        outputs = self._link.outputs
        values = _output_values(outputs) if outputs is not None else {}
        rows: list[dict[str, Any]] = [
            {
                "name": name,
                "kind": kind,
                "unit": unit,
                "value": (
                    self._format(kind, self._to_display(unit, values[name]))
                    if name in values else None
                ),
            }
            for name, kind, unit in _OUTPUT_SPEC
        ]
        rows.extend(
            {
                "name": row["name"],
                "kind": "bool",
                "unit": "",
                "value": row["active"] if outputs is not None else None,
            }
            for row in self._failure_rows()
        )
        return rows

    def _failure_rows(self) -> list[dict[str, Any]]:
        outputs = self._link.outputs
        failures = outputs.controller.failures if outputs else None
        return [
            {
                "name": name,
                "active": bool(failures and getattr(failures, field)),
            }
            for name, field in _FAILURE_FIELDS.items()
        ]

    @Property("QVariantList", notify=outputsChanged)  # type: ignore[arg-type]
    def failures(self) -> list[dict[str, Any]]:
        """The three Failure Status flags, as the module reports them."""
        return self._failure_rows()

    @Property(int, notify=outputsChanged)
    def activeFailureCount(self) -> int:
        """How many failure modes the module reports as set."""
        return sum(1 for row in self._failure_rows() if row["active"])

    @Property(bool, notify=outputsChanged)
    def emergencyBrakeActive(self) -> bool:
        """Whether the module reports its emergency brake engaged."""
        outputs = self._link.outputs
        return bool(outputs and outputs.controller.emergency_brake_active)

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
        total = int(self._tick * self._dt + 1e-9)
        return f"{total // 3600:02d}:{total // 60 % 60:02d}:{total % 60:02d}"

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

    @Slot(str, bool)
    def setFailure(self, name: str, active: bool) -> None:
        """Test only: ask the module to set or clear one failure mode."""
        try:
            self._link.set_failure(name, active)
        except LinkError as exc:
            self._set_input_error(str(exc))

    @Slot(result=bool)
    def sendInputs(self) -> bool:
        """Submit a valid tick, or retain state and drafts with an error."""
        values = self._accepted | self._pending_inputs
        if not self._submit(values, self._emergency_override_pending):
            return False
        self._emergency_override_pending = False
        self._pending_inputs.clear()
        self._set_input_error("")
        self.inputsChanged.emit()
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
        """Restore a fresh module, the initial commands and zero counters."""
        self._timer.stop()
        self._set_input_error("")
        self._pending_inputs.clear()
        self._accepted = dict(_INITIAL_COMMANDS)
        self._emergency_override_pending = False
        self._tick = 0
        self._running = False
        try:
            self._link.reset()
        except LinkError as exc:
            self._set_input_error(str(exc))
        self._sync_inputs()
        self.inputsChanged.emit()
        self.runControlChanged.emit()

    def _step(self) -> None:
        # The first tick may submit pending edits. Later ticks use only
        # accepted inputs; they never overwrite or submit drafts.
        if self._tick == 0 and self._pending_inputs:
            self.sendInputs()
            return
        if self._submit(self._accepted) and not self._pending_inputs:
            # A pending draft keeps the error that explains why it was
            # not sent; otherwise a good tick clears a stale one.
            self._set_input_error("")

    def _submit(
        self, values: dict[str, Any], clear_passenger_brake: bool = False,
    ) -> bool:
        """Step the module once on ``values``; report a rejection."""
        try:
            self._link.step(
                self._dt, self._build_inputs(values),
                clear_passenger_brake=clear_passenger_brake,
            )
        except (ValueError, InvalidTimeStepError, LinkError) as exc:
            self.setRunning(False)
            self._set_input_error(str(exc))
            return False
        # A boarding count is consumed by the step that carries it.
        self._accepted = dict(values, passengers_boarded=0)
        self._tick += 1
        self._sync_inputs()
        self.runControlChanged.emit()
        return True

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
                    authority_blocks=values["authority"],
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
