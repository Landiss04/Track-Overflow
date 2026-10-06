"""Test harness state for the Train Model test UI.

The harness supplies every input the Train Model would otherwise receive
from the Track Model and the Train Controller, and drives the clock, so
the module can be run and graded on its own. It runs in the test UI's
own process and reaches the module only through its boundary, over a
link (``train_model/link.py``): it sends ``TrainModelInputs`` each tick
and reads back only ``TrainModelOutputs``. Failure status is not an
output; the failure flags it shows arrive over the link, test only.

Rows are built from the interface dictionary (v0.2). Array-valued
signals are presented as one row per element: ``Light Command``
(``bool[2]``) becomes the interior and exterior rows, ``Door command``
(``bool[2]``) becomes left and right, and the ``Track Signal`` struct is
flattened into its fields.

Controls read back live state from the outputs, with staged edits marked
pending. Sending applies those edits and advances one tick. Later ticks
reuse the last accepted inputs. A boarding count is consumed once and
must be entered again for a later boarding event.

Time comes from the shared simulation clock (``utils/system_clock.py``).
The module steps once per clock tick, and dt is the clock's fixed tick
length. ``ClockDriver`` ticks the clock in real time while it runs, at
1x or 10x; sending and advancing tick it by hand. Speed changes how
often ticks happen, never dt (D006).

A step is checked before its tick, with the module's own input rules
and for a reachable module, so input the module would reject never
advances the shared clock. Every ``DRIFT_CHECK_TICKS`` clock ticks the
harness compares the clock with the steps the module accepted and
reports any gap as drift.

As the stand-in Track Model, the harness loads the Blue Line by default
(``train_model/track_stub.py``): the track rows follow the train from
block to block, and an edit to one lasts until the next block change.
As the stand-in Train Controller, it limits the train's speed
(``train_model/speed_limiter.py``): the power sent each tick is the
entered power, lowered as needed to hold the speed at or below the
vehicle's maximum speed and the speed limit. The rows keep the entered
commands; only what is sent is limited.

The output table shows the signals the Train Controller and the Track
Model act on; the passthroughs the Train Model window already shows are
left out of it.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from typing import Any, Literal, cast

from PySide6.QtCore import Property, QObject, Signal, Slot

from train_model.interface import (
    Beacon,
    ControllerCommands,
    TrackInfo,
    TrackInputs,
    TrackSignal,
    TrainConfig,
    TrainModelInputs,
    TrainModelOutputs,
)
from train_model.link import LinkError, LocalLink, SocketLink
from train_model.model import InvalidTimeStepError, TrainModel
from train_model.speed_limiter import SpeedLimiter
from train_model.state import FAILURE_MODES
from train_model.track_stub import TrackStub, load_blue_line

# The simulation clock is shared by every module, so it lives in the
# repository-level utils/ package.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from utils.clock_driver import ClockDriver  # noqa: E402
from utils.system_clock import ALLOWED_SPEEDS, SystemClock  # noqa: E402

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
    # A count, edited with PositiveIntField: 0 and up.
    {"name": "passengers_boarded", "kind": "uint", "unit": ""},
    {"name": "temperature_setpoint", "kind": "float", "unit": "°F"},
    {
        "name": "announcement",
        "kind": "string",
        "unit": "",
    },
)

#: Outputs read back from the module, in interface-dictionary order:
#: the signals the Train Controller and the Track Model act on. The
#: passthroughs the Train Model window already shows (commanded speed,
#: authority, beacon) and the block-change flag are left out.
_OUTPUT_SPEC: tuple[tuple[str, str, str], ...] = (
    ("emergency_brake_state", "bool", ""),
    ("left_door_state", "bool", ""),
    ("right_door_state", "bool", ""),
    ("interior_light_state", "bool", ""),
    ("exterior_light_state", "bool", ""),
    ("cabin_temp", "float", "°F"),
    ("position_block", "string", ""),
    ("position_offset", "float", "ft"),
    ("actual_speed", "float", "mph"),
    ("passenger_capacity", "int", ""),
    ("speed_limit", "float", "mph"),
)

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

_DISPLAY_FACTORS = {"mph": 2.236936, "ft": 3.280840, "kW": 0.001}

#: Clock ticks between drift checks.
DRIFT_CHECK_TICKS = 30

# The step was not tried: the Train Model process is not reachable.
_NOT_CONNECTED = "Train Model is not running"

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
    driftChanged = Signal()

    def __init__(
        self,
        link: Link,
        parent: QObject | None = None,
        *,
        track: TrackStub | None | Literal["blue_line"] = "blue_line",
    ) -> None:
        """Stand in for the producers and the clock of one Train Model.

        Args:
            link: The link to the Train Model.
            parent: The Qt parent.
            track: The track to follow: the Blue Line by default, or
                None to enter every track row by hand.
        """
        super().__init__(parent)
        self._link = link
        self._input_error = ""
        self._track = load_blue_line() if track == "blue_line" else track
        # The stand-in Train Controller's speed cap: the vehicle's
        # maximum speed, or the speed limit where that is lower.
        self._limiter = SpeedLimiter()
        self._v_max_mps = TrainConfig().v_max_mps
        self._limiting = False
        # The commands the module last accepted from these producers.
        self._accepted: dict[str, Any] = self._initial_commands()
        self._pending_inputs: dict[str, Any] = {}
        self._live_inputs = self._live_input_values()
        self._emergency_override_pending = False
        # Accepted steps since the last reset. Steps are checked before
        # their tick, so a clock tick without one is drift.
        self._tick = 0
        # Clock ticks the module did not take, as of the last check.
        self._drift_ticks = 0
        # Set while a send ticks the clock, so that tick carries the
        # staged edits; the tick reports whether the module took them.
        self._send_requested = False
        self._send_accepted = False
        self._clock = SystemClock()
        self._clock.add_tick_listener(self._on_clock_tick)
        self._clock.add_state_listener(self.runControlChanged.emit)
        # The driver idles while the clock is held.
        self._driver = ClockDriver(self._clock, parent=self)
        self._driver.start()
        link.outputsChanged.connect(self.outputsChanged)
        link.outputsChanged.connect(self._sync_inputs)
        link.connectedChanged.connect(self._on_connected_changed)

    def _on_connected_changed(self) -> None:
        # Hold a running clock as soon as the Train Model drops, rather
        # than spend a tick on a step that cannot reach it.
        if not self._link.connected and not self._clock.is_paused:
            self.setRunning(False)
            self._set_input_error(_NOT_CONNECTED)
        self.connectedChanged.emit()

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

    @Property("QVariantList", constant=True)  # type: ignore[arg-type]
    def outputDefinitions(self) -> list[dict[str, Any]]:
        """Stable output rows: a tick updates values, not delegates."""
        return [
            {"name": name, "kind": kind, "unit": unit}
            for name, kind, unit in _OUTPUT_SPEC
        ]

    @Property("QVariantMap", notify=outputsChanged)  # type: ignore[arg-type]
    def outputValues(self) -> dict[str, Any]:
        """Displayed output values by row name; None while disconnected."""
        return {row["name"]: row["value"] for row in self._output_rows()}

    @Property("QVariantList", notify=outputsChanged)  # type: ignore[arg-type]
    def outputs(self) -> list[dict[str, Any]]:
        """Read-only output rows; empty values while disconnected."""
        return self._output_rows()

    def _output_rows(self) -> list[dict[str, Any]]:
        outputs = self._link.outputs
        values = _output_values(outputs) if outputs is not None else {}
        return [
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

    def _failure_rows(self) -> list[dict[str, Any]]:
        failures = self._link.failures or {}
        return [
            {"name": name, "active": failures.get(name, False)}
            for name in FAILURE_MODES
        ]

    @Property("QVariantList", notify=outputsChanged)  # type: ignore[arg-type]
    def failures(self) -> list[dict[str, Any]]:
        """The three failure flags, test only: they are not outputs."""
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
        return not self._clock.is_paused

    @Property("QVariantList", constant=True)  # type: ignore[arg-type]
    def speeds(self) -> list[int]:
        """Speed multipliers the clock accepts, slowest first."""
        return list(ALLOWED_SPEEDS)

    @Property(int, notify=runControlChanged)
    def speed(self) -> int:
        """Clock speed multiplier; 1 is real time."""
        return self._clock.speed

    @Property(int, notify=runControlChanged)
    def tick(self) -> int:
        """Ticks elapsed since the last reset."""
        return self._tick

    @Property(float, notify=runControlChanged)
    def dt(self) -> float:
        """Seconds per tick, fixed by the clock at any speed."""
        return self._clock.tick_s

    @Property(str, notify=runControlChanged)
    def elapsed(self) -> str:
        """Elapsed simulated time as ``hh:mm:ss``."""
        total = int(self._tick * self._clock.tick_s + 1e-9)
        return f"{total // 3600:02d}:{total // 60 % 60:02d}:{total % 60:02d}"

    @Property(int, notify=driftChanged)
    def driftTicks(self) -> int:
        """Clock ticks the module has not taken, as of the last check.

        Checked every ``DRIFT_CHECK_TICKS`` clock ticks; zero while the
        module keeps time with the shared clock.
        """
        return self._drift_ticks

    @Property(str, constant=True)
    def trackName(self) -> str:
        """The loaded track, or that the track rows are entered by hand."""
        return self._track.name if self._track is not None else "Manual"

    @Property(float, notify=runControlChanged)
    def speedCap(self) -> float:
        """The speed limiter's cap for the accepted inputs, in mph."""
        cap_mps = self._speed_cap_mps(self._accepted["speed_limit"])
        return cast(float, self._to_display("mph", cap_mps))

    @Property(bool, notify=runControlChanged)
    def limiting(self) -> bool:
        """Whether the last step's power or brake was limited."""
        return self._limiting

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
        if not self._can_step(self._next_values(send=True)):
            return False
        # Tick the clock by hand; that tick carries the staged edits.
        self._send_requested = True
        self._send_accepted = False
        try:
            self._clock.tick()
        finally:
            self._send_requested = False
        return self._send_accepted

    @Slot(bool)
    def setRunning(self, running: bool) -> None:
        """Run or hold the simulation clock."""
        if not running:
            self._clock.pause()
        elif self._can_step(self._next_values(send=False)):
            self._clock.resume()

    @Slot(int)
    def setSpeed(self, speed: int) -> None:
        """Set the clock speed multiplier; one of ``speeds``."""
        self._clock.set_speed(speed)

    @Slot()
    def advanceTick(self) -> None:
        """Advance the Train Model one tick on the last sent inputs."""
        if self._can_step(self._next_values(send=False)):
            self._clock.tick()

    @Slot()
    def resetModule(self) -> None:
        """Restore a fresh module, the initial commands and zero counters."""
        # Resetting also holds the clock; the speed is kept.
        self._clock.reset()
        if self._drift_ticks:
            self._drift_ticks = 0
            self.driftChanged.emit()
        self._set_input_error("")
        self._pending_inputs.clear()
        if self._track is not None:
            self._track.reset()
        self._limiter.reset()
        self._limiting = False
        self._accepted = self._initial_commands()
        self._emergency_override_pending = False
        self._tick = 0
        try:
            self._link.reset()
        except LinkError as exc:
            self._set_input_error(str(exc))
        self._sync_inputs()
        self.inputsChanged.emit()
        self.runControlChanged.emit()

    def _on_clock_tick(self, _sim_time_s: float, tick_s: float) -> None:
        # Every module step happens on a clock tick.
        send = self._carries_drafts(self._send_requested)
        # Consume the request first: a rejection holds the clock, and
        # the driver may run ticks already due before it stops.
        self._send_requested = False
        if send:
            self._send_accepted = self._send(tick_s)
        elif self._submit(tick_s, self._accepted) and not self._pending_inputs:
            # A pending draft keeps the error that explains why it was
            # not sent; otherwise a good tick clears a stale one.
            self._set_input_error("")
        if self._clock.tick_count % DRIFT_CHECK_TICKS == 0:
            self._check_drift()

    def _carries_drafts(self, send: bool) -> bool:
        # A send, and the first tick while edits are pending, submit the
        # drafts. Later ticks reuse only the accepted inputs.
        return send or (self._tick == 0 and bool(self._pending_inputs))

    def _next_values(self, send: bool) -> dict[str, Any]:
        # The inputs the next tick will submit.
        if self._carries_drafts(send):
            return self._accepted | self._pending_inputs
        return self._accepted

    def _can_step(self, values: dict[str, Any]) -> bool:
        """Check a step on ``values`` before its tick; report a rejection.

        Uses the module's own input rules, which need no module state;
        nothing is sent. Input the module would reject, or a module
        that cannot be reached, holds the clock instead of ticking it.
        """
        try:
            if not self._link.connected:
                raise LinkError(_NOT_CONNECTED)
            TrainModel.validate_inputs(
                self._clock.tick_s, self._build_inputs(values)
            )
        except (ValueError, InvalidTimeStepError, LinkError) as exc:
            self.setRunning(False)
            self._set_input_error(str(exc))
            return False
        return True

    def _check_drift(self) -> None:
        # Each accepted step advances the module by one tick, so the
        # module's time is accepted steps x dt. The boundary does not
        # report the module's own time: a step the module took whose
        # reply was lost would also show here as drift.
        drift_ticks = self._clock.tick_count - self._tick
        if drift_ticks != self._drift_ticks:
            self._drift_ticks = drift_ticks
            self.driftChanged.emit()

    def _send(self, dt: float) -> bool:
        # Step on the accepted inputs with the staged edits applied.
        values = self._accepted | self._pending_inputs
        if not self._submit(dt, values, self._emergency_override_pending):
            return False
        self._emergency_override_pending = False
        self._pending_inputs.clear()
        self._set_input_error("")
        self.inputsChanged.emit()
        return True

    def _submit(
        self, dt: float, values: dict[str, Any],
        clear_passenger_brake: bool = False,
    ) -> bool:
        """Step the module once on ``values``; report a rejection."""
        # A rejected step leaves the limiter as it was.
        limiter_state, limiting = self._limiter.state, self._limiting
        try:
            inputs = self._build_inputs(values)
            # The entered values must be valid before the limiter sees them.
            TrainModel.validate_inputs(dt, inputs)
            outputs = self._link.step(
                dt, self._limit(dt, inputs),
                clear_passenger_brake=clear_passenger_brake,
            )
        except (ValueError, InvalidTimeStepError, LinkError) as exc:
            self._limiter.state, self._limiting = limiter_state, limiting
            self.setRunning(False)
            self._set_input_error(str(exc))
            return False
        # A boarding count is consumed by the step that carries it.
        self._accepted = dict(values, passengers_boarded=0)
        if self._track is not None and self._track.follow(
                outputs.track.offset_m):
            self._accepted |= self._track.inputs()
        self._tick += 1
        self._sync_inputs()
        self.runControlChanged.emit()
        return True

    def _initial_commands(self) -> dict[str, Any]:
        # The loaded track supplies the track rows for its first block.
        values = dict(_INITIAL_COMMANDS)
        if self._track is not None:
            values |= self._track.inputs()
        return values

    def _speed_cap_mps(self, speed_limit_mps: float) -> float:
        # A speed limit of 0 means none has been entered.
        if speed_limit_mps > 0.0:
            return min(self._v_max_mps, speed_limit_mps)
        return self._v_max_mps

    def _limit(self, dt: float, inputs: TrainModelInputs) -> TrainModelInputs:
        # Stand in for the Train Controller's speed regulation: lower the
        # entered power, and brake if needed, to hold the speed cap.
        outputs = self._link.outputs
        speed = outputs.controller.actual_speed_mps if outputs else 0.0
        cmd = inputs.controller
        limited = self._limiter.apply(
            dt,
            self._speed_cap_mps(inputs.track.track_info.speed_limit_mps),
            speed,
            cmd.power_cmd_w,
            cmd.service_brake,
        )
        self._limiting = limited.limiting
        return dataclasses.replace(inputs, controller=dataclasses.replace(
            cmd, power_cmd_w=limited.power_w,
            service_brake=limited.service_brake,
        ))

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
        if kind in ("int", "uint"):
            return round(value)
        if kind == "float":
            return round(value, decimals)
        return value

    @staticmethod
    def _coerce(kind: str, value: Any) -> Any:
        """Convert a value from QML into the type the row declares."""
        if kind == "bool":
            return bool(value)
        if kind in ("int", "uint"):
            return int(float(value))
        if kind == "float":
            return float(value)
        return str(value)
