"""Train Model implementation.

Point-mass longitudinal dynamics for one fixed consist, per the Train
Model backend design, section 1 and sections 5.1 to 5.95. State is SI
internally. Temperature crosses the boundary in degrees Celsius and grade
in degrees, the backend units; grade becomes radians where the physics
uses it.

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

# No Track Info has been received before the first step.
_NO_BLOCK_ID = ""


class TrainModelError(Exception):
    """Base class for every Train Model error."""


class InvalidTimeStepError(TrainModelError):
    """Raised for a nonfinite or nonpositive time step."""


class InvalidInputError(TrainModelError, ValueError):
    """Raised for invalid numeric inputs, before state is changed."""


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
    # Brake failure blocks the service brake only; the emergency brake,
    # commanded or pulled by a passenger, still works.
    emergency = emergency_cmd or passenger_pulled
    # OPEN(5.8): the emergency brake supersedes the service brake, so
    # the service brake is not engaged while the emergency brake is.
    service = service_cmd and not emergency and not brake_failed
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
        self._last_inputs: TrainModelInputs | None = None
        self._elapsed_s = 0.0

        self._outputs = self._build_outputs(
            inputs=None, block_changed=False
        )

    # ------------------------------------------------------------------ #
    # Protocol
    # ------------------------------------------------------------------ #

    def step(self, dt: float, inputs: TrainModelInputs) -> TrainModelOutputs:
        """Advance one tick of length ``dt`` seconds.

        Args:
            dt: Fixed sample period in seconds. Must be finite and positive.
            inputs: This tick's controller commands and track inputs.

        Returns:
            The outputs for this tick.

        Raises:
            InvalidTimeStepError: If ``dt`` is nonfinite or not positive.
            InvalidInputError: If numeric inputs are invalid.
        """
        self.validate_inputs(dt, inputs)
        cmd = inputs.controller
        track = inputs.track

        # Door interlock: a door can only open at 0 mph. An open command
        # while moving is refused, and takes effect once the train stops.
        stopped = self._velocity_mps == 0.0
        door_left = cmd.door_left_open and stopped
        door_right = cmd.door_right_open and stopped
        self._update_passengers(
            door_left, door_right, track.passengers_boarded,
            at_station=bool(track.track_info.station_name),
        )
        self._door_left_open = door_left
        self._door_right_open = door_right

        block_changed = self._detect_block_change(track.track_info.polarity)
        if block_changed:
            self._offset_m = 0.0

        grade_rad = math.radians(track.track_info.grade_deg)
        self._integrate(dt, inputs, grade_rad)
        if self._velocity_mps != 0.0:
            # The interlock holds: no door stays open once the train moves.
            self._door_left_open = False
            self._door_right_open = False
        self._update_cabin_temp(dt, cmd.temp_setpoint_c)

        self._last_inputs = inputs
        self._elapsed_s += dt
        self._outputs = self._build_outputs(inputs, block_changed)
        return self._outputs

    @staticmethod
    def validate_inputs(dt: float, inputs: TrainModelInputs) -> None:
        """Validate a step without changing state, including test actions."""
        if not math.isfinite(dt) or dt <= 0.0:
            raise InvalidTimeStepError(
                f"dt must be finite and positive, got {dt}"
            )

        cmd = inputs.controller
        track = inputs.track
        numeric = {
            "power_cmd_w": cmd.power_cmd_w,
            "temp_setpoint_c": cmd.temp_setpoint_c,
            "grade_deg": track.track_info.grade_deg,
            "elevation_m": track.track_info.elevation_m,
            "speed_limit_mps": track.track_info.speed_limit_mps,
            "commanded_speed_mps": track.track_signal.commanded_speed_mps,
            "passengers_boarded": track.passengers_boarded,
        }
        for name, value in numeric.items():
            if not math.isfinite(value):
                raise InvalidInputError(f"{name} must be finite, got {value}")
        if cmd.power_cmd_w < 0.0:
            raise InvalidInputError("power_cmd_w must be nonnegative")
        if not isinstance(track.passengers_boarded, int):
            raise InvalidInputError("passengers_boarded must be an integer")

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
            inputs=self._last_inputs,
            elapsed_s=self._elapsed_s,
        )

    def set_failures(self, failures: FailureState) -> None:
        """Report a fault now; the next step integrates its physical effect."""
        self._failures = failures
        self._refresh_discrete_outputs()

    def pull_passenger_emergency_brake(self) -> None:
        """Pull the passenger emergency brake."""
        self._passenger_ebrake_pulled = True
        self._refresh_discrete_outputs()

    def clear_passenger_brake_for_test(self) -> None:
        """Clear the latch for testing, without defining normal UI release."""
        self._passenger_ebrake_pulled = False
        self._refresh_discrete_outputs()

    def _refresh_discrete_outputs(self) -> None:
        # Report actions immediately, including while paused. Motion is
        # still integrated only by step(); do not advance time here.
        self._outputs = self._build_outputs(
            self._last_inputs, self._outputs.track.block_changed
        )

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
        # Commands are held throughout this tick. Solve traction at the
        # midpoint velocity: F * dx <= P * h, even on launch. Previous
        # ticks' accelerations never enter this tick's force balance.
        cfg = self.config
        cmd = inputs.controller
        m = self._mass_kg()
        f_brake = self._brake_n(cmd.service_brake, cmd.emergency_brake)
        f_grade = m * cfg.g_mps2 * math.sin(grade_rad)
        f_roll = cfg.c_rr * m * cfg.g_mps2 * math.cos(grade_rad)
        hold = f_brake + f_roll
        power = 0.0 if self._failures.engine else min(
            cmd.power_cmd_w, cfg.p_max_w
        )
        remaining = dt
        v = self._velocity_mps
        while remaining > 0.0:
            direction = _sign(v)
            if direction == 0.0:
                drive = self._traction_n(power, 0.0) - f_grade
                if abs(drive) <= hold:
                    break
                direction = _sign(drive)

            resistance = f_grade + direction * hold
            h = remaining
            if direction > 0.0 and power > 0.0:
                # Resolve the P/v transition and its relaxation time.
                # This bounds midpoint steps without a speed governor.
                v_base = power / cfg.f_max_n
                scale = max(v, v_base, math.ulp(0.0))
                h = min(h, m * scale * (scale / power))
                if 0.0 < resistance < cfg.f_max_n:
                    equilibrium = power / resistance
                    if math.isclose(v, equilibrium, rel_tol=1e-12,
                                    abs_tol=math.ulp(equilibrium)):
                        # At floating-point equilibrium, skip vanishing
                        # substeps rather than accumulating roundoff.
                        v = equilibrium
                        self._offset_m += v * remaining
                        break
                # A substep stays in one traction regime: it ends at the
                # base speed v_base = P / F_max rather than straddle it.
                if v < v_base or (
                        v == v_base and resistance > cfg.f_max_n):
                    # Force-limited: F_max is constant, so this is exact.
                    v_next = v + h * (cfg.f_max_n - resistance) / m
                    if v_next > v_base:
                        h = min(h, (v_base - v) * m
                                / (cfg.f_max_n - resistance))
                        v_next = v_base
                else:
                    # Power-limited. Scale the midpoint quadratic by
                    # speed to avoid squaring tiny velocities at very
                    # small powers.
                    b = v / scale - (h / scale) * resistance / (2.0 * m)
                    c = (h / scale) * (power / scale) / (2.0 * m)
                    root = math.hypot(b, 2.0 * math.sqrt(c))
                    u = ((b + root) / 2.0 if b >= 0.0
                         else 2.0 * c / (root - b))
                    v_next = 2.0 * scale * u - v
                    if v_next < v_base < v:
                        # Slowing into the force limit: end where the
                        # same midpoint rule reaches v_base.
                        net = power / ((v + v_base) / 2.0) - resistance
                        if net < 0.0:
                            h = min(h, m * (v_base - v) / net)
                            v_next = v_base
            else:
                # No traction during rollback; all forces are constant.
                v_next = v - h * resistance / m

            if (v > 0.0 and v_next <= 0.0) or (v < 0.0 and v_next >= 0.0):
                # Integrate to the stop, then evaluate static holding or
                # gravity-driven reversal for the remainder of the tick.
                traction = self._traction_n(power, v / 2.0)
                a_stop = (traction - resistance) / m
                h = min(h, -v / a_stop)
                v_next = 0.0
            self._offset_m += h * (v + v_next) / 2.0
            remaining -= h
            v = v_next

        self._velocity_mps = v
        drive = self._traction_n(power, v) - f_grade
        if v == 0.0:
            self._accel_mps2 = (
                0.0 if abs(drive) <= hold
                else (drive - _sign(drive) * hold) / m
            )
        else:
            self._accel_mps2 = (drive - _sign(v) * hold) / m

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
        self, door_left: bool, door_right: bool, boarded: int, *,
        at_station: bool,
    ) -> None:
        # Section 5.2: disembark first, then board, bounded both ways.
        # The door arguments are the interlocked door states, so an
        # opened door already implies the train is stopped.
        cfg = self.config
        opened = (
            (door_left and not self._door_left_open)
            or (door_right and not self._door_right_open)
        )
        # OPEN(5.2): uniform integer 0..onboard, drawn on a door-open
        # rising edge (either side) at v = 0.
        if opened and self._velocity_mps == 0.0:
            self._n_passengers -= self._rng.randint(0, self._n_passengers)
        # Passengers can only board at a station with a door open; a
        # count received at any other time boards nobody.
        if not (at_station and (door_left or door_right)):
            return
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
                cabin_temp_c=self._cabin_temp_c,
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
