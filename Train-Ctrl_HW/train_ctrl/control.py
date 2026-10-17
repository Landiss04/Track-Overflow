"""The PI speed law, the safety path and the toy plant, per train.

No Qt: this runs the same under the console, the bench or the
central harness.
"""

from __future__ import annotations

import math
from typing import Any

from .constants import (
    ANNOUNCE_LOCKOUT_MS,
    BLOCK_LENGTH_M,
    BRAKE_DETECT_S,
    CABIN_DRIFT_FRACTION,
    CABIN_DRIFT_MAX_C,
    EBRAKE_DECEL_MPS2,
    ENGINE_DETECT_ACCEL_MPS2,
    ENGINE_DETECT_S,
    ENGINE_RISE_MPS,
    FAILURES,
    MASS_KG,
    MAX_FORCE_N,
    MAX_POWER_W,
    MAX_SPEED_MPS,
    PICKUP_DETECT_MIN_BLOCKS,
    ROLLING_DECEL_MPS2,
    SERVICE_BAND_MPS,
    SERVICE_DECEL_MPS2,
    SETTLE_MPS,
    STANDSTILL_MPS,
    TICK_S,
    V_FLOOR_MPS,
)
from .state import State, TrainModelCommands

class ControllerCore:
    """The PI speed law, the safety path and the toy plant.

    No Qt, no view: this class is what the hardware demo has to prove
    correct, and it runs unchanged whether or not a console is open.
    """

    def __init__(self) -> None:
        self.state = State()
        self.dt = TICK_S                    # seconds of simulation
        self.integral = 0.0
        # Inert until an engineer commissions the gains.
        self.armed = False
        # The door and light commands the plant last acted on, so it
        # answers a command once, on its edge, and leaves a state the
        # bench published alone in between.
        self._acted_doors: tuple[bool, bool] | None = (False, False)
        self._acted_lights: tuple[bool, bool] | None = (True, True)
        # Automatic station stop (REQUIREMENTS.md M6): a new beacon
        # station not yet served, and whether the train is held at
        # it, first with the doors open and then while they close.
        self._station_pending = False
        self._dwelling = False
        self._closing = False
        # Seconds left on an automatic announcement command.
        self._announce_left_s = 0.0
        self._clear_detection()

    def _clear_detection(self) -> None:
        # What detect_failures() carries from one tick to the next.
        self._brake_unanswered_s = 0.0
        self._engine_stalled_s = 0.0
        self._engine_ref_mps = 0.0
        self._last_signal: tuple[float, int] | None = None

    @property
    def failed(self) -> list[str]:
        """The detected failures still latched, in FAILURES order."""
        return [name for name in FAILURES if self.state.failures[name]]

    @property
    def received_signal(self) -> tuple[float, int]:
        """The Track Signal as it reaches the controller.

        Commanded speed (m/s) and authority (blocks). The toy plant
        stands in for the Train Model passing it through: with signal
        pickup injected it passes zeros (truth leaves zeros or stale
        values open; zeros is this plant's choice).
        """
        s = self.state
        if s.injected["signal_pickup"]:
            return 0.0, 0
        return s.commanded_mps, s.authority_blocks

    @property
    def commanded_mps(self) -> float:
        """The commanded speed the controller may act on."""
        if self.state.failures["signal_pickup"]:
            return 0.0
        return self.received_signal[0]

    @property
    def authority_blocks(self) -> int:
        """The authority the controller may act on.

        With a signal pickup failure detected the Track Signal cannot
        be trusted, so it fails safe to none.
        """
        if self.state.failures["signal_pickup"]:
            return 0
        return self.received_signal[1]

    def step(self, plant: bool = True) -> None:
        """Run one control period.

        Only the speed law waits for the gains. The brakes and the
        safety path run from the first tick, because a console that
        has not been commissioned yet still has to be able to stop
        the train and still has to report what the brakes are doing.

        ``plant`` runs the toy train after the control law, for the
        standalone console and bench. Driven by the harness it is
        off: the Train Model does the physics (truth D009).
        """
        s = self.state
        if self._announce_left_s > 0.0:
            self._announce_left_s -= self.dt
            if self._announce_left_s <= 0.0:
                s.announcement = ""
        self.detect_failures()
        if self.armed:
            if not s.manual:
                # Commanded speed is the speed limit, never above the
                # car's 70 km/h (REQUIREMENTS.md M1).
                s.target_mps = self.speed_cap_mps
            self._station_stop()

            error = s.target_mps - s.actual_mps
            # A target of zero means stop, so the brake holds to a
            # stand rather than leaving the train creeping inside the
            # band with no resistance to bring it down.
            stopping = s.target_mps <= 0.0 and s.actual_mps > 0.0
            s.service_brake = (
                error < -SERVICE_BAND_MPS or s.service_request or stopping
            )
            if s.service_brake:
                # Traction is cut whenever a brake is applied, and
                # the integrator holds rather than winding up against
                # the brake (arbitration/traction-cut-under-braking).
                s.power_w = 0.0
            else:
                self.integral += error * self.dt
                power = s.kp * error + s.ki * self.integral
                if power > MAX_POWER_W:
                    power = MAX_POWER_W
                    self.integral -= error * self.dt
                elif power < 0.0:
                    power = 0.0
                    self.integral -= error * self.dt
                s.power_w = power
        else:
            s.power_w = 0.0
            s.service_brake = s.service_request

        self.respond_to_failures()
        self.enforce_safety()
        if plant:
            self._plant()

    def apply_staged(self, staged: dict[str, Any]) -> None:
        """Apply a set of Train Model signals read by read_inputs().

        A reported emergency brake that this controller did not
        command is a passenger pull: latch it and cut power. A report
        of false never releases it; only the driver does (D011,
        arbitration/passenger-emergency-brake).
        """
        s = self.state
        staged = dict(staged)
        station = staged.get("beacon_station", s.beacon_station)
        if station and station != s.beacon_station:
            # A new station ahead, served once the train stops. In
            # Automatic it is announced now, on the approach: the
            # controller sends the command and the Train Model plays
            # it (REQUIREMENTS.md M7).
            self._station_pending = True
            if not s.manual:
                s.announcement = station
                self._announce_left_s = ANNOUNCE_LOCKOUT_MS / 1000
        brakes = staged.pop("brake_state", None)
        for attr, value in staged.items():
            setattr(s, attr, value)
        if brakes is not None:
            emergency, service = brakes
            if emergency and not s.emergency_brake:
                self.engage_emergency()
            s.fb_emergency_brake, s.fb_service_brake = emergency, service

    def detect_failures(self) -> None:
        """Infer failures from what the Train Model sends back.

        REQ-FUNC-038. The Train Model does not report its failures
        (truth modules/train-model.md), so each one is read off the
        signals it does return, against what this controller last
        commanded:

            brake          the service brake was commanded, the
                           emergency brake was not, and Brake State
                           has not shown the service brake applied
                           for BRAKE_DETECT_S
            engine         the power commanded should have pulled at
                           least ENGINE_DETECT_ACCEL_MPS2, no brake is
                           on, and the actual speed has not risen for
                           ENGINE_DETECT_S
            signal pickup  commanded speed and authority both fell to
                           zero in one update, from at least
                           PICKUP_DETECT_MIN_BLOCKS of authority

        A detected failure latches until it is cleared on the test
        bench (clear_failure).
        """
        s = self.state

        if (s.service_brake and not s.emergency_brake
                and not s.fb_service_brake):
            self._brake_unanswered_s += self.dt
            if self._brake_unanswered_s >= BRAKE_DETECT_S:
                s.failures["brake"] = True
        else:
            self._brake_unanswered_s = 0.0

        v = s.actual_mps
        force = min(MAX_FORCE_N, s.power_w / max(abs(v), V_FLOOR_MPS))
        pulling = (force / MASS_KG >= ENGINE_DETECT_ACCEL_MPS2
                   and not s.service_brake and not s.emergency_brake)
        if not pulling or v > self._engine_ref_mps + ENGINE_RISE_MPS:
            # Not asked to pull, or the speed is answering: start
            # watching again from here.
            self._engine_stalled_s = 0.0
            self._engine_ref_mps = v
        else:
            self._engine_stalled_s += self.dt
            if self._engine_stalled_s >= ENGINE_DETECT_S:
                s.failures["engine"] = True

        signal = self.received_signal
        last = self._last_signal
        if (last is not None and last[0] > 0.0
                and last[1] >= PICKUP_DETECT_MIN_BLOCKS
                and signal == (0.0, 0)):
            s.failures["signal_pickup"] = True
        self._last_signal = signal

    def clear_failure(self, name: str) -> None:
        """Let go of one detected failure, once it has been resolved.

        The test bench decides that, by clearing the failure it
        injected. The emergency brake stays on; the driver releases
        it at a stand once no failure is left.
        """
        self.state.failures[name] = False
        if name == "brake":
            self._brake_unanswered_s = 0.0
        elif name == "engine":
            self._engine_stalled_s = 0.0
            self._engine_ref_mps = self.state.actual_mps
        else:
            self._last_signal = None

    def respond_to_failures(self) -> None:
        """Stop the train while any detected failure is latched.

        REQ-FUNC-037.2: the controller stops the train when a failure
        is detected. Every failure removes the target and the power,
        and applies and latches the emergency brake:

            engine         no traction is left to drive with
            signal pickup  commanded speed and authority cannot be
                           read from the track circuit, so they fail
                           safe to zero (the signal lights still read)
            brake          only the service brake has failed (truth
                           modules/train-model.md); the emergency
                           brake still works, so it stops the train

        The emergency brake cannot be released until the failure
        clears (release_emergency refuses while any is latched).
        """
        if not self.failed:
            return
        s = self.state
        s.target_mps = 0.0
        s.power_w = 0.0
        self.integral = 0.0
        if not s.emergency_brake:
            self.engage_emergency()
        s.service_brake = False
        if s.failures["brake"]:
            # The driver's request was for the brake that failed.
            s.service_request = False

    def enforce_safety(self) -> None:
        """Override the PI law with the safety rules.

        Gains change how the train drives; they can never change
        whether it stops.
        """
        s = self.state

        # No authority is not an emergency. The train may not move,
        # and it comes to a stand on the service brake the way a
        # driver would stop it, in either mode.
        if self.authority_blocks <= 0:
            s.target_mps = 0.0
            s.power_w = 0.0
            self.integral = 0.0
            if s.actual_mps > 0.0:
                s.service_brake = True

        # The emergency brake comes from the driver, from a Train
        # Model report of a passenger pull, or from a detected
        # failure (respond_to_failures).
        if s.emergency_brake:
            s.power_w = 0.0
            self.integral = 0.0

        # A failed service brake is not commanded, whatever asked for
        # it, in either mode; the emergency brake stands in for it.
        if s.failures["brake"]:
            s.service_brake = False

    def engage_emergency(self) -> None:
        """Engage now, without waiting for the next control tick.

        Guide section 7 calls the emergency brake immediate, so the
        safety path runs on the press rather than up to one control
        period later.
        """
        self.state.emergency_brake = True
        self.enforce_safety()

    def release_emergency(self) -> bool:
        """Release the latched brake, at a stand with no failure.

        Asking a released brake to release is not a refusal: it is
        already where the caller wants it.
        """
        s = self.state
        if not s.emergency_brake:
            return True
        if self.failed or abs(s.actual_mps) >= STANDSTILL_MPS:
            return False
        s.emergency_brake = False
        return True

    @property
    def speed_cap_mps(self) -> float:
        """The fastest the train may be asked to go, in m/s.

        The commanded speed, never above the car's 70 km/h
        (REQUIREMENTS.md M1). The Train Model has no governor (truth
        D009), so the cap is the controller's.
        """
        return min(self.commanded_mps, MAX_SPEED_MPS)

    def set_target_mps(self, mps: float) -> None:
        """Set the driver's target in m/s, capped at speed_cap_mps.

        Capped only when set: the target then follows the driver
        (REQUIREMENTS.md M1).
        """
        s = self.state
        if s.manual and self.authority_blocks > 0 and not self.failed:
            s.target_mps = max(0.0, min(mps, self.speed_cap_mps))

    def platform_on(self, side: str) -> bool:
        """Whether the last beacon put a platform on this side."""
        return ("L" if side == "left" else "R") in self.state.beacon_side

    @property
    def at_stand(self) -> bool:
        """Whether the Train Model reports the train stopped."""
        return abs(self.state.actual_mps) < STANDSTILL_MPS

    @property
    def station_hold(self) -> bool:
        """Whether an Automatic station stop is holding the train."""
        return self._dwelling or self._closing

    def _station_stop(self) -> None:
        # Automatic only (REQUIREMENTS.md M6). Stopped at a new
        # station: open the platform side and hold. The dwell is the
        # Train Model's; the controller holds until the Track Signal
        # resumes, then closes the doors and departs only once Door
        # State reports them closed.
        s = self.state
        if s.manual:
            self._dwelling = self._closing = False
            return
        if self._station_pending and self.at_stand:
            self._station_pending = False
            self._dwelling = True
            for side in ("left", "right"):
                if self.platform_on(side):
                    self.command_door(side, True)
        resumed = self.commanded_mps > 0.0 and self.authority_blocks > 0
        if self._dwelling and resumed:
            self._dwelling = False
            self._closing = True
            for side in ("left", "right"):
                self.command_door(side, False)
        if (self._closing and not s.fb_doors_left
                and not s.fb_doors_right):
            self._closing = False
        if self.station_hold:
            # Held, not creeping on what the integrator carried in.
            s.target_mps = 0.0
            self.integral = 0.0

    def command_door(self, side: str, open_: bool) -> bool:
        """Command one side's doors, and have the plant answer it.

        Only the platform side opens, and only at a stand (the door
        interlock is the controller's, REQUIREMENTS.md M6). Closing is
        always allowed, so a door left open when the platform side
        changes is never stuck open. Returns whether it was sent.

        The plant answers a command on its edge. Pressing a tile
        again with the same command, because the reported state still
        disagrees (the door interlock held it, say), has to be
        answered too, or the tile could never change anything.
        """
        s = self.state
        if open_ and not (self.platform_on(side) and self.at_stand):
            return False
        if side == "left":
            s.doors_left = open_
        else:
            s.doors_right = open_
        self._acted_doors = None
        return True

    def command_lights(self, interior: bool, exterior: bool) -> None:
        """Command the lights, and have the plant answer it."""
        s = self.state
        s.interior_lights, s.exterior_lights = interior, exterior
        self._acted_lights = None

    def commands(self) -> TrainModelCommands:
        """Return this tick's commands to the Train Model, in SI."""
        s = self.state
        return TrainModelCommands(
            power_w=s.power_w,
            service_brake=s.service_brake,
            emergency_brake=s.emergency_brake,
            door_command=(s.doors_left, s.doors_right),
            light_command=(s.interior_lights, s.exterior_lights),
            temperature_setpoint_c=s.target_temp_c,
            announcement=s.announcement,
        )

    def _plant(self) -> None:
        # Toy physics standing in for the Train Model until it is
        # wired in:
        #
        #     F = P / v     a = F / M     v = v + a dt
        #
        # No resistance term in normal running: the model is the block
        # diagram and nothing else. A train with no power applied
        # coasts forever, so the only ways down are the two brakes,
        # and the speed law holds its target from below rather than
        # settling onto it from both sides. The injected failures act
        # here the way truth modules/train-model.md says the Train
        # Model applies them: an engine failure zeroes traction, and a
        # brake failure blocks the service brake only; the emergency
        # brake still works. Under a brake failure, and only then for
        # now, rolling resistance (same source) also acts on the
        # train. Signal pickup is applied in received_signal.
        s = self.state
        service_works = not s.injected["brake"]
        power = 0.0 if s.injected["engine"] else s.power_w
        v = s.actual_mps
        force = min(MAX_FORCE_N, power / max(abs(v), V_FLOOR_MPS))
        a = force / MASS_KG
        decel = 0.0
        if s.emergency_brake:
            decel = EBRAKE_DECEL_MPS2
        elif service_works and s.service_brake:
            decel = SERVICE_DECEL_MPS2
        if decel:
            # A brake opposes the motion and never reverses it.
            a = -math.copysign(decel, v) if v else 0.0
        elif not service_works:
            # Resistance opposes the motion, holds the train at rest,
            # and never reverses it.
            a = (a - math.copysign(ROLLING_DECEL_MPS2, v) if v
                 else max(0.0, a - ROLLING_DECEL_MPS2))
        new_v = v + a * self.dt
        if v * new_v < 0.0:
            new_v = 0.0             # stopped, never reversed
        s.accel_mps2 = a
        s.actual_mps = new_v
        if abs(s.actual_mps) < SETTLE_MPS and s.target_mps < SETTLE_MPS:
            s.actual_mps = 0.0          # settle cleanly at a stand

        # Standing in for the Track Model's block count, so the
        # console shows the train making progress: each fixed-length
        # block travelled spends one block of authority. Delete this
        # with the plant once the Track Model sends real counts.
        s.block_progress_m += abs(s.actual_mps) * self.dt
        while s.block_progress_m >= BLOCK_LENGTH_M:
            s.block_progress_m -= BLOCK_LENGTH_M
            s.authority_blocks = max(0, s.authority_blocks - 1)

        # Brake State, as this plant reports it: what is engaged, so
        # a failed service brake reads false whatever was commanded.
        # That is the plant's own stand-in; what the real Train Model
        # reports is for it to settle.
        s.fb_emergency_brake = s.emergency_brake
        s.fb_service_brake = s.service_brake and service_works

        # Door and light commands are answered on their edge. A door
        # only opens at a stand (the door interlock, truth
        # door-command.md); a command to open while moving is ignored.
        doors = (s.doors_left, s.doors_right)
        if doors != self._acted_doors:
            at_stand = abs(s.actual_mps) < STANDSTILL_MPS
            s.fb_doors_left = s.doors_left and at_stand
            s.fb_doors_right = s.doors_right and at_stand
            self._acted_doors = doors
        lights = (s.interior_lights, s.exterior_lights)
        if lights != self._acted_lights:
            s.fb_interior_lights, s.fb_exterior_lights = lights
            self._acted_lights = lights

        drift = s.target_temp_c - s.cabin_temp_c
        s.cabin_temp_c += max(
            -CABIN_DRIFT_MAX_C,
            min(CABIN_DRIFT_MAX_C, drift * CABIN_DRIFT_FRACTION),
        )