"""Train Model implementation.

Point-mass longitudinal dynamics for one fixed consist, per the Train
Model backend design, section 1 and sections 5.1 to 5.95. State is SI
internally. Temperature crosses the boundary in degrees Fahrenheit and
grade in percent; each is converted in exactly one function below.

Sites that take a default for an item the design leaves open are
marked ``OPEN(<section>)``.
"""

from __future__ import annotations

import math
import random

from train_model.interface import (
    ControllerOutputs,
    FailureState,
    TrainConfig,
    TrainModelInputs,
    TrainModelOutputs,
    TrainModelSnapshot,
    TrackOutputs,
)

STUB = False

# OPEN(5.4): first-order lag toward the setpoint, k = 1/300 per second.
CABIN_TEMP_RATE_PER_S = 1.0 / 300.0
# OPEN(5.4): the design gives no initial cabin temperature.
INITIAL_CABIN_TEMP_C = 20.0

_PERCENT = 100.0
_F_PER_C = 9.0 / 5.0
_F_OFFSET = 32.0

# No Track Info has been received before the first step.
_NO_BLOCK_ID = ""


class TrainModelError(Exception):
    """Base class for every Train Model error."""


class InvalidTimeStepError(TrainModelError):
    """Raised when ``step`` is given a time step that is not positive."""


def _f_to_c(temp_f: float) -> float:
    # The one inbound temperature conversion.
    return (temp_f - _F_OFFSET) / _F_PER_C


def _c_to_f(temp_c: float) -> float:
    # The one outbound temperature conversion.
    return temp_c * _F_PER_C + _F_OFFSET


def _grade_angle_rad(grade_percent: float) -> float:
    # The one grade conversion: rise over run in percent to an angle.
    return math.atan(grade_percent / _PERCENT)


def _sign(value: float) -> float:
    # Sign as -1.0, 0.0 or 1.0.
    return (value > 0.0) - (value < 0.0)


def _brakes_engaged(
    service_cmd: bool,
    emergency_cmd: bool,
    passenger_pulled: bool,
    brake_failed: bool,
) -> tuple[bool, bool]:
    """Return which brakes are engaged, as Brake State orders them.

    Brake State reports the brakes' actual state, not the commands. The
    braking force and the reported state both come from this function.

    Args:
        service_cmd: The Train Controller's service brake command.
        emergency_cmd: The Train Controller's emergency brake command.
        passenger_pulled: Whether the passenger emergency brake is pulled.
        brake_failed: Whether Murphy has injected a brake failure.

    Returns:
        ``(emergency, service)``: whether each brake is engaged.
    """
    # OPEN(5.95): brake failure disables service and emergency.
    if brake_failed:
        return False, False
    emergency = emergency_cmd or passenger_pulled
    # OPEN(5.8): the emergency brake supersedes the service brake, so
    # the service brake is not engaged while the emergency brake is.
    service = service_cmd and not emergency
    return emergency, service


class TrainModel:
    """Train Model. Constructed as ``TrainModel(config)``."""

    def __init__(self, config: TrainConfig) -> None:
        """Start at rest with crew only, no failures, and no inputs."""
        self.config = config
        self._rng = random.Random(config.seed)

        self._velocity_mps = 0.0
        self._accel_mps2 = 0.0
        self._offset_m = 0.0
        self._n_passengers = 0
        self._cabin_temp_c = INITIAL_CABIN_TEMP_C
        self._failures = FailureState()
        self._passenger_ebrake_pulled = False
        self._last_polarity: bool | None = None
        self._door_left_open = False
        self._door_right_open = False

        self._outputs = self._build_outputs(
            inputs=None, block_changed=False
        )

    # ------------------------------------------------------------------ #
    # Protocol
    # ------------------------------------------------------------------ #

    def step(self, dt: float, inputs: TrainModelInputs) -> TrainModelOutputs:
        """Advance one tick of length ``dt`` seconds.

        Args:
            dt: Fixed sample period in seconds. Must be positive.
            inputs: This tick's controller commands and track inputs.

        Returns:
            The outputs for this tick.

        Raises:
            InvalidTimeStepError: If ``dt`` is not positive.
        """
        if dt <= 0.0:
            raise InvalidTimeStepError(f"dt must be positive, got {dt}")

        cmd = inputs.controller
        track = inputs.track

        self._update_passengers(
            cmd.door_left_open, cmd.door_right_open,
            track.passengers_boarded,
        )
        # OPEN(5.6): no door interlock; the doors obey the commands.
        self._door_left_open = cmd.door_left_open
        self._door_right_open = cmd.door_right_open

        block_changed = self._detect_block_change(track.track_info.polarity)
        if block_changed:
            self._offset_m = 0.0

        grade_rad = _grade_angle_rad(track.track_info.grade_percent)
        self._integrate(dt, inputs, grade_rad)
        self._update_cabin_temp(dt, _f_to_c(cmd.temp_setpoint_f))

        self._outputs = self._build_outputs(inputs, block_changed)
        return self._outputs

    def snapshot(self) -> TrainModelSnapshot:
        """Return the current state for display. No side effects."""
        return TrainModelSnapshot(
            mass_kg=self._mass_kg(),
            acceleration_mps2=self._accel_mps2,
            velocity_mps=self._velocity_mps,
            n_crew=self.config.n_crew,
            n_passengers=self._n_passengers,
            passenger_ebrake_pulled=self._passenger_ebrake_pulled,
            outputs=self._outputs,
        )

    def set_failures(self, failures: FailureState) -> None:
        """Apply Murphy's fault injection from the next tick on."""
        self._failures = failures

    def pull_passenger_emergency_brake(self) -> None:
        """Pull the passenger emergency brake."""
        # OPEN(5.8): the pull latches; release is not implemented.
        self._passenger_ebrake_pulled = True

    # ------------------------------------------------------------------ #
    # Physics
    # ------------------------------------------------------------------ #

    def _mass_kg(self) -> float:
        # Operating mass; crew counts toward it.
        cfg = self.config
        occupants = cfg.n_crew + self._n_passengers
        return cfg.m_empty_kg + occupants * cfg.passenger_mass_kg

    def _traction_n(self, power_cmd_w: float, velocity_mps: float) -> float:
        # Section 1: P/v saturated at F_max; motors drive forward only.
        cfg = self.config
        if self._failures.engine:
            return 0.0
        # OPEN(1): no speed governing here; power is capped at P_max.
        p_eff_w = min(power_cmd_w, cfg.p_max_w)
        if velocity_mps > 0.0:
            return min(p_eff_w / velocity_mps, cfg.f_max_n)
        if velocity_mps < 0.0:
            return 0.0
        # At v = 0, P/v saturates to F_max for any positive power.
        return cfg.f_max_n if p_eff_w > 0.0 else 0.0

    def _brake_n(self, service: bool, emergency: bool) -> float:
        # OPEN(1): brake forces come from m_ref, so the deceleration they
        # produce scales with operating mass; no cap.
        cfg = self.config
        emergency_on, service_on = _brakes_engaged(
            service, emergency,
            self._passenger_ebrake_pulled, self._failures.brake,
        )
        if emergency_on:
            return cfg.f_emergency_n
        if service_on:
            return cfg.f_service_n
        return 0.0

    def _integrate(
        self, dt: float, inputs: TrainModelInputs, grade_rad: float
    ) -> None:
        # Section 1: forces, then trapezoidal a -> v and v -> x.
        cfg = self.config
        cmd = inputs.controller
        m = self._mass_kg()
        v_prev = self._velocity_mps
        a_prev = self._accel_mps2

        f_trac = self._traction_n(cmd.power_cmd_w, v_prev)
        f_brake = self._brake_n(cmd.service_brake, cmd.emergency_brake)
        f_grade = m * cfg.g_mps2 * math.sin(grade_rad)
        f_roll = cfg.c_rr * m * cfg.g_mps2 * math.cos(grade_rad)

        if v_prev != 0.0:
            a_n = (
                f_trac - f_grade - _sign(v_prev) * (f_brake + f_roll)
            ) / m
            v_n = v_prev + (dt / 2.0) * (a_n + a_prev)
            dx = (dt / 2.0) * (v_n + v_prev)
            if _sign(v_n) != _sign(v_prev):
                # Brakes and rolling resistance stop the train, never
                # reverse it; the next tick takes the at-rest case.
                v_n = 0.0
                a_n = 0.0
        else:
            f_drive = f_trac - f_grade
            f_hold = f_brake + f_roll
            if abs(f_drive) <= f_hold:
                a_n = 0.0
            else:
                a_n = (f_drive - _sign(f_drive) * f_hold) / m
            v_n = v_prev + (dt / 2.0) * (a_n + a_prev)
            dx = (dt / 2.0) * (v_n + v_prev)

        self._accel_mps2 = a_n
        self._velocity_mps = v_n
        # OPEN(5.3): offset is distance since the last block change,
        # for the front of the train; it goes negative in rollback.
        self._offset_m += dx

    # ------------------------------------------------------------------ #
    # Blocks, passengers, cabin
    # ------------------------------------------------------------------ #

    def _detect_block_change(self, polarity: bool) -> bool:
        # OPEN(5.3): a block change is the tick polarity differs from
        # the previous tick. The first tick has no previous polarity.
        changed = (
            self._last_polarity is not None
            and polarity != self._last_polarity
        )
        self._last_polarity = polarity
        return changed

    def _update_passengers(
        self, door_left: bool, door_right: bool, boarded: int
    ) -> None:
        # Section 5.2: disembark first, then board, bounded both ways.
        cfg = self.config
        opened = (
            (door_left and not self._door_left_open)
            or (door_right and not self._door_right_open)
        )
        # OPEN(5.2): uniform integer 0..onboard, drawn on a door-open
        # rising edge (either side) at v = 0.
        if opened and self._velocity_mps == 0.0:
            self._n_passengers -= self._rng.randint(0, self._n_passengers)
        room = cfg.capacity - self._n_passengers
        self._n_passengers += max(0, min(boarded, room))

    def _update_cabin_temp(self, dt: float, setpoint_c: float) -> None:
        # OPEN(5.4): exact discrete step of dT/dt = k (T_set - T).
        decay = math.exp(-CABIN_TEMP_RATE_PER_S * dt)
        self._cabin_temp_c = (
            setpoint_c + (self._cabin_temp_c - setpoint_c) * decay
        )

    # ------------------------------------------------------------------ #
    # Outputs
    # ------------------------------------------------------------------ #

    def _build_outputs(
        self, inputs: TrainModelInputs | None, block_changed: bool
    ) -> TrainModelOutputs:
        # Assemble outputs from state; before any step, no inputs exist.
        failures = self._failures
        service_cmd = False
        emergency_cmd = False
        commanded_speed_mps = 0.0
        authority_block_id: str | None = None
        speed_limit_mps = 0.0
        block_id = _NO_BLOCK_ID
        interior = False
        exterior = False
        beacon = None
        if inputs is not None:
            cmd = inputs.controller
            track = inputs.track
            service_cmd = cmd.service_brake
            emergency_cmd = cmd.emergency_brake
            block_id = track.track_info.block_id
            speed_limit_mps = track.track_info.speed_limit_mps
            interior = cmd.interior_lights
            exterior = cmd.exterior_lights
            # OPEN(5.7): pass through this tick's beacon; None otherwise.
            beacon = track.beacon
            # OPEN(5.3): under signal pickup failure, commanded speed
            # is 0.0 and there is no authority.
            if not failures.signal_pickup:
                commanded_speed_mps = track.track_signal.commanded_speed_mps
                authority_block_id = track.track_signal.authority_block_id
        ebrake, service = _brakes_engaged(
            service_cmd, emergency_cmd,
            self._passenger_ebrake_pulled, failures.brake,
        )

        return TrainModelOutputs(
            controller=ControllerOutputs(
                actual_speed_mps=self._velocity_mps,
                emergency_brake_active=ebrake,
                service_brake_active=service,
                door_left_open=self._door_left_open,
                door_right_open=self._door_right_open,
                interior_lights_on=interior,
                exterior_lights_on=exterior,
                cabin_temp_f=_c_to_f(self._cabin_temp_c),
                commanded_speed_mps=commanded_speed_mps,
                authority_block_id=authority_block_id,
                speed_limit_mps=speed_limit_mps,
                beacon=beacon,
                failures=failures,
            ),
            track=TrackOutputs(
                block_id=block_id,
                offset_m=self._offset_m,
                actual_speed_mps=self._velocity_mps,
                block_changed=block_changed,
                passenger_capacity=self.config.capacity - self._n_passengers,
            ),
        )
