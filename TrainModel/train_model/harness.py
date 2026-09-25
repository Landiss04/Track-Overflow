"""Stub state for the Train Model test UI (page 3b).

Backs the standalone test harness: the editable input signals, the read-only
output signals, the three failure-mode toggles, and run control. Values are
seeded to the mockup (``refrence-docs/test_ui.png``). Inputs are typed and
editable; the QML layer enforces the declared type and coerces before calling
the setter. There is no module under test here — slots only mutate this stub.
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot


@dataclass(frozen=True, slots=True)
class InputSeeds:
    """The mockup input values every RESET MODULE returns to."""

    commanded_speed: float = 35.0
    authority: int = 4
    beacon_data: str = "DORMONT|L|0"
    power_command: float = 118000.0
    service_brake_cmd: bool = False
    emergency_brake_cmd: bool = False
    left_door_cmd: bool = False
    right_door_cmd: bool = False
    interior_light_cmd: bool = True
    exterior_light_cmd: bool = True
    cabin_temp_setpoint: int = 68
    announcement: str = "NEXT STOP DORMONT"
    passengers_boarding: int = 12
    block_grade: float = 1.2
    block_elevation: float = 0.0
    posted_speed_limit: int = 40


@dataclass(frozen=True, slots=True)
class FailureSeeds:
    """The mockup failure-mode values every RESET MODULE returns to."""

    engine_failure: bool = False
    brake_failure: bool = False
    signal_pickup_failure: bool = True


@dataclass(frozen=True, slots=True)
class InputDescriptor:
    """View metadata for one row of the INPUTS table.

    ``type`` is the declared signal type (float/int/string/bool); ``unit``
    is the suffix shown beside the field and empty for bools and strings.
    """

    name: str
    type: str
    unit: str = ""


# Row order and units as drawn in the mockup (badge says 15, table has 16 —
# see README "Design discrepancies", item 13).
INPUT_DESCRIPTORS: tuple[InputDescriptor, ...] = (
    InputDescriptor("commanded_speed", "float", "MPH"),
    InputDescriptor("authority", "int", "BLOCKS"),
    InputDescriptor("beacon_data", "string"),
    InputDescriptor("power_command", "float", "W"),
    InputDescriptor("service_brake_cmd", "bool"),
    InputDescriptor("emergency_brake_cmd", "bool"),
    InputDescriptor("left_door_cmd", "bool"),
    InputDescriptor("right_door_cmd", "bool"),
    InputDescriptor("interior_light_cmd", "bool"),
    InputDescriptor("exterior_light_cmd", "bool"),
    InputDescriptor("cabin_temp_setpoint", "int", "°F"),
    InputDescriptor("announcement", "string"),
    InputDescriptor("passengers_boarding", "int", "COUNT"),
    InputDescriptor("block_grade", "float", "%"),
    InputDescriptor("block_elevation", "float", "FT"),
    InputDescriptor("posted_speed_limit", "int", "MPH"),
)


class TestHarnessState(QObject):
    """Backs the page-3b view with typed, bindable signal values."""

    # -- Change signals -------------------------------------------------
    commanded_speed_changed = pyqtSignal()
    authority_changed = pyqtSignal()
    beacon_data_changed = pyqtSignal()
    power_command_changed = pyqtSignal()
    service_brake_cmd_changed = pyqtSignal()
    emergency_brake_cmd_changed = pyqtSignal()
    left_door_cmd_changed = pyqtSignal()
    right_door_cmd_changed = pyqtSignal()
    interior_light_cmd_changed = pyqtSignal()
    exterior_light_cmd_changed = pyqtSignal()
    cabin_temp_setpoint_changed = pyqtSignal()
    announcement_changed = pyqtSignal()
    passengers_boarding_changed = pyqtSignal()
    block_grade_changed = pyqtSignal()
    block_elevation_changed = pyqtSignal()
    posted_speed_limit_changed = pyqtSignal()

    # Aggregate signal: emitted whenever any input value changes (via
    # set_input or reset_module) so the QML input table can refresh every
    # field with one connection instead of sixteen.
    inputs_changed = pyqtSignal()

    outputs_changed = pyqtSignal()

    engine_failure_changed = pyqtSignal()
    brake_failure_changed = pyqtSignal()
    signal_pickup_failure_changed = pyqtSignal()

    run_state_changed = pyqtSignal()
    tick_changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()

        # Inputs.
        self._commanded_speed = 35.0
        self._authority = 4
        self._beacon_data = "DORMONT|L|0"
        self._power_command = 118000.0
        self._service_brake_cmd = False
        self._emergency_brake_cmd = False
        self._left_door_cmd = False
        self._right_door_cmd = False
        self._interior_light_cmd = True
        self._exterior_light_cmd = True
        self._cabin_temp_setpoint = 68
        self._announcement = "NEXT STOP DORMONT"
        self._passengers_boarding = 12
        self._block_grade = 1.2
        self._block_elevation = 0.0
        self._posted_speed_limit = 40

        # Seeds for reset_module, kept separate from the live values so a
        # reset always returns to the mockup state regardless of edits.
        self._input_seeds = InputSeeds()

        # Outputs (display strings; units are a flagged discrepancy).
        self._outputs: list[dict[str, str]] = [
            {"signal": "actual_speed", "type": "float", "value": "32.4 MPH"},
            {"signal": "commanded_speed", "type": "float", "value": "35.0 MPH"},
            {"signal": "authority", "type": "int", "value": "4 BLOCKS"},
            {"signal": "beacon_data", "type": "string", "value": "DORMONT|L|0"},
            {"signal": "engine_failure", "type": "bool", "value": "FALSE"},
            {"signal": "brake_failure", "type": "bool", "value": "FALSE"},
            {"signal": "signal_pickup_failure", "type": "bool", "value": "TRUE"},
            {"signal": "passenger_ebrake", "type": "bool", "value": "FALSE"},
            {"signal": "distance_travelled", "type": "float", "value": "4.8 FT"},
            {"signal": "train_id", "type": "string", "value": "T-114"},
            {"signal": "passengers_disembarking", "type": "int", "value": "7 COUNT"},
        ]
        self._outputs_seed = [dict(row) for row in self._outputs]

        # Failure modes (module state, not inputs).
        self._engine_failure = False
        self._brake_failure = False
        self._signal_pickup_failure = True
        self._failure_seeds = FailureSeeds()

        # Name -> declared type, used to coerce set_input values.
        self._input_kinds: dict[str, str] = {
            descriptor.name: descriptor.type for descriptor in INPUT_DESCRIPTORS
        }

        # Run control.
        self._run_state = "HOLD"
        self._tick = 1284
        self._dt = "0.100 S"
        self._elapsed = "00:02:08"
        self._last_action = ""

    # -- Inputs ---------------------------------------------------------
    def _get_commanded_speed(self) -> float:
        return self._commanded_speed

    def _set_commanded_speed(self, value: float) -> None:
        self._commanded_speed = value
        self.commanded_speed_changed.emit()

    commanded_speed = pyqtProperty(
        float,
        _get_commanded_speed,
        _set_commanded_speed,
        notify=commanded_speed_changed,
    )

    def _get_authority(self) -> int:
        return self._authority

    def _set_authority(self, value: int) -> None:
        self._authority = value
        self.authority_changed.emit()

    authority = pyqtProperty(
        int, _get_authority, _set_authority, notify=authority_changed
    )

    def _get_beacon_data(self) -> str:
        return self._beacon_data

    def _set_beacon_data(self, value: str) -> None:
        self._beacon_data = value
        self.beacon_data_changed.emit()

    beacon_data = pyqtProperty(
        str, _get_beacon_data, _set_beacon_data, notify=beacon_data_changed
    )

    def _get_power_command(self) -> float:
        return self._power_command

    def _set_power_command(self, value: float) -> None:
        self._power_command = value
        self.power_command_changed.emit()

    power_command = pyqtProperty(
        float,
        _get_power_command,
        _set_power_command,
        notify=power_command_changed,
    )

    def _get_service_brake_cmd(self) -> bool:
        return self._service_brake_cmd

    def _set_service_brake_cmd(self, value: bool) -> None:
        self._service_brake_cmd = value
        self.service_brake_cmd_changed.emit()

    service_brake_cmd = pyqtProperty(
        bool,
        _get_service_brake_cmd,
        _set_service_brake_cmd,
        notify=service_brake_cmd_changed,
    )

    def _get_emergency_brake_cmd(self) -> bool:
        return self._emergency_brake_cmd

    def _set_emergency_brake_cmd(self, value: bool) -> None:
        self._emergency_brake_cmd = value
        self.emergency_brake_cmd_changed.emit()

    emergency_brake_cmd = pyqtProperty(
        bool,
        _get_emergency_brake_cmd,
        _set_emergency_brake_cmd,
        notify=emergency_brake_cmd_changed,
    )

    def _get_left_door_cmd(self) -> bool:
        return self._left_door_cmd

    def _set_left_door_cmd(self, value: bool) -> None:
        self._left_door_cmd = value
        self.left_door_cmd_changed.emit()

    left_door_cmd = pyqtProperty(
        bool, _get_left_door_cmd, _set_left_door_cmd, notify=left_door_cmd_changed
    )

    def _get_right_door_cmd(self) -> bool:
        return self._right_door_cmd

    def _set_right_door_cmd(self, value: bool) -> None:
        self._right_door_cmd = value
        self.right_door_cmd_changed.emit()

    right_door_cmd = pyqtProperty(
        bool,
        _get_right_door_cmd,
        _set_right_door_cmd,
        notify=right_door_cmd_changed,
    )

    def _get_interior_light_cmd(self) -> bool:
        return self._interior_light_cmd

    def _set_interior_light_cmd(self, value: bool) -> None:
        self._interior_light_cmd = value
        self.interior_light_cmd_changed.emit()

    interior_light_cmd = pyqtProperty(
        bool,
        _get_interior_light_cmd,
        _set_interior_light_cmd,
        notify=interior_light_cmd_changed,
    )

    def _get_exterior_light_cmd(self) -> bool:
        return self._exterior_light_cmd

    def _set_exterior_light_cmd(self, value: bool) -> None:
        self._exterior_light_cmd = value
        self.exterior_light_cmd_changed.emit()

    exterior_light_cmd = pyqtProperty(
        bool,
        _get_exterior_light_cmd,
        _set_exterior_light_cmd,
        notify=exterior_light_cmd_changed,
    )

    def _get_cabin_temp_setpoint(self) -> int:
        return self._cabin_temp_setpoint

    def _set_cabin_temp_setpoint(self, value: int) -> None:
        self._cabin_temp_setpoint = value
        self.cabin_temp_setpoint_changed.emit()

    cabin_temp_setpoint = pyqtProperty(
        int,
        _get_cabin_temp_setpoint,
        _set_cabin_temp_setpoint,
        notify=cabin_temp_setpoint_changed,
    )

    def _get_announcement(self) -> str:
        return self._announcement

    def _set_announcement(self, value: str) -> None:
        self._announcement = value
        self.announcement_changed.emit()

    announcement = pyqtProperty(
        str, _get_announcement, _set_announcement, notify=announcement_changed
    )

    def _get_passengers_boarding(self) -> int:
        return self._passengers_boarding

    def _set_passengers_boarding(self, value: int) -> None:
        self._passengers_boarding = value
        self.passengers_boarding_changed.emit()

    passengers_boarding = pyqtProperty(
        int,
        _get_passengers_boarding,
        _set_passengers_boarding,
        notify=passengers_boarding_changed,
    )

    def _get_block_grade(self) -> float:
        return self._block_grade

    def _set_block_grade(self, value: float) -> None:
        self._block_grade = value
        self.block_grade_changed.emit()

    block_grade = pyqtProperty(
        float, _get_block_grade, _set_block_grade, notify=block_grade_changed
    )

    def _get_block_elevation(self) -> float:
        return self._block_elevation

    def _set_block_elevation(self, value: float) -> None:
        self._block_elevation = value
        self.block_elevation_changed.emit()

    block_elevation = pyqtProperty(
        float,
        _get_block_elevation,
        _set_block_elevation,
        notify=block_elevation_changed,
    )

    def _get_posted_speed_limit(self) -> int:
        return self._posted_speed_limit

    def _set_posted_speed_limit(self, value: int) -> None:
        self._posted_speed_limit = value
        self.posted_speed_limit_changed.emit()

    posted_speed_limit = pyqtProperty(
        int,
        _get_posted_speed_limit,
        _set_posted_speed_limit,
        notify=posted_speed_limit_changed,
    )

    def _get_input_descriptors(self) -> list[dict[str, str]]:
        return [
            {"name": d.name, "type": d.type, "unit": d.unit}
            for d in INPUT_DESCRIPTORS
        ]

    input_descriptors = pyqtProperty(
        "QVariantList", _get_input_descriptors, constant=True
    )

    # -- Outputs --------------------------------------------------------
    def _get_outputs(self) -> list[dict[str, str]]:
        return self._outputs

    outputs = pyqtProperty(
        "QVariantList", _get_outputs, notify=outputs_changed
    )

    # -- Failure modes --------------------------------------------------
    def _get_engine_failure(self) -> bool:
        return self._engine_failure

    def _set_engine_failure(self, value: bool) -> None:
        self._engine_failure = value
        self.engine_failure_changed.emit()

    engine_failure = pyqtProperty(
        bool, _get_engine_failure, _set_engine_failure,
        notify=engine_failure_changed,
    )

    def _get_brake_failure(self) -> bool:
        return self._brake_failure

    def _set_brake_failure(self, value: bool) -> None:
        self._brake_failure = value
        self.brake_failure_changed.emit()

    brake_failure = pyqtProperty(
        bool, _get_brake_failure, _set_brake_failure,
        notify=brake_failure_changed,
    )

    def _get_signal_pickup_failure(self) -> bool:
        return self._signal_pickup_failure

    def _set_signal_pickup_failure(self, value: bool) -> None:
        self._signal_pickup_failure = value
        self.signal_pickup_failure_changed.emit()

    signal_pickup_failure = pyqtProperty(
        bool,
        _get_signal_pickup_failure,
        _set_signal_pickup_failure,
        notify=signal_pickup_failure_changed,
    )

    # -- Run control ----------------------------------------------------
    def _get_run_state(self) -> str:
        return self._run_state

    def _set_run_state(self, value: str) -> None:
        self._run_state = value
        self.run_state_changed.emit()

    run_state = pyqtProperty(
        str, _get_run_state, _set_run_state, notify=run_state_changed
    )

    def _get_tick(self) -> int:
        return self._tick

    tick = pyqtProperty(int, _get_tick, notify=tick_changed)

    def _get_dt(self) -> str:
        return self._dt

    dt = pyqtProperty(str, _get_dt, constant=True)

    def _get_elapsed(self) -> str:
        return self._elapsed

    elapsed = pyqtProperty(str, _get_elapsed, constant=True)

    # -- Slots (stub behaviour only) ------------------------------------
    @pyqtSlot(str, object)
    def set_input(self, name: str, value: object) -> None:
        """Assign *value* to the named input signal, coerced to its type.

        The QML input table edits rows generically, so it routes every edit
        through here instead of naming sixteen properties.
        """
        kind = self._input_kinds.get(name)
        if kind is None:
            raise ValueError(f"Unknown input signal {name!r}")
        if isinstance(value, bool):
            coerced: bool | int | float | str = value
        elif isinstance(value, (int, float)):
            number = float(value)
            if kind == "bool":
                coerced = number != 0.0
            elif kind == "int":
                coerced = int(number)
            else:
                coerced = number
        elif isinstance(value, str):
            text = value.strip()
            if kind in ("int", "float"):
                number = float(text)
                coerced = int(number) if kind == "int" else number
            elif kind == "bool":
                lowered = text.lower()
                if lowered not in ("true", "false"):
                    raise ValueError(f"{name!r} expects TRUE or FALSE")
                coerced = lowered == "true"
            else:
                coerced = text
        else:
            raise TypeError(
                f"{name!r} got {type(value).__name__}, expected a scalar"
            )
        setattr(self, name, coerced)
        self.inputs_changed.emit()

    @pyqtSlot(str, result=str)
    def input_text(self, name: str) -> str:
        """Return the display text for an input value, mockup-formatted."""
        if name not in self._input_kinds:
            raise ValueError(f"Unknown input signal {name!r}")
        value = getattr(self, name)
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, float):
            # Whole numbers of 1000+ print without a decimal (118000 W);
            # everything else keeps one decimal (35.0, 1.2, 0.0).
            if value == int(value) and abs(value) >= 1000:
                return str(int(value))
            return f"{value:.1f}"
        return str(value)

    @pyqtSlot()
    def advance_tick(self) -> None:
        """Advance the stub tick counter by one."""
        self._tick += 1
        self.tick_changed.emit()

    @pyqtSlot(str)
    def set_run_state(self, state: str) -> None:
        """Set the RUN/HOLD run-control state."""
        self.run_state = state

    @pyqtSlot()
    def send_inputs(self) -> None:
        """Stub boundary: push the current inputs to the module under test.

        No module is wired in yet, so this only records that a send was
        requested; it does not change any signal value.
        """
        self._last_action = "SENT"

    @pyqtSlot()
    def reset_module(self) -> None:
        """Restore every input, output, and failure toggle to its seed."""
        seeds = self._input_seeds
        self.commanded_speed = seeds.commanded_speed
        self.authority = seeds.authority
        self.beacon_data = seeds.beacon_data
        self.power_command = seeds.power_command
        self.service_brake_cmd = seeds.service_brake_cmd
        self.emergency_brake_cmd = seeds.emergency_brake_cmd
        self.left_door_cmd = seeds.left_door_cmd
        self.right_door_cmd = seeds.right_door_cmd
        self.interior_light_cmd = seeds.interior_light_cmd
        self.exterior_light_cmd = seeds.exterior_light_cmd
        self.cabin_temp_setpoint = seeds.cabin_temp_setpoint
        self.announcement = seeds.announcement
        self.passengers_boarding = seeds.passengers_boarding
        self.block_grade = seeds.block_grade
        self.block_elevation = seeds.block_elevation
        self.posted_speed_limit = seeds.posted_speed_limit

        failures = self._failure_seeds
        self.engine_failure = failures.engine_failure
        self.brake_failure = failures.brake_failure
        self.signal_pickup_failure = failures.signal_pickup_failure

        self._outputs = [dict(row) for row in self._outputs_seed]
        self.outputs_changed.emit()

        self.run_state = "HOLD"
        self._tick = 1284
        self.tick_changed.emit()

        # One aggregate emit covers every input field in the QML table.
        self.inputs_changed.emit()
