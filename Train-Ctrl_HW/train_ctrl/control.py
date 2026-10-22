<<<<<<< HEAD
"""The PI speed law, the safety path and the toy plant, per train.

No Qt: this runs the same under the console, the bench or the
central harness.
=======
"""The PI speed law and the safety path, per train.

No Qt: this runs the same whether the bench or the central harness
drives it. It knows only what it receives and what it sends
(REQUIREMENTS.md M0); the bench's simulation is train_ctrl.bench_sim.
>>>>>>> origin/Train_Ctrl_integration
"""

from __future__ import annotations

<<<<<<< HEAD
import math
from collections import deque
from typing import Any

from .constants import (
    ANNOUNCE_LOCKOUT_MS,
    BLOCK_LENGTH_M,
    BRAKE_DETECT_S,
    CABIN_DRIFT_FRACTION,
    CABIN_DRIFT_MAX_C,
    DWELL_S,
    EBRAKE_DECEL_MPS2,
    ENGINE_DETECT_S,
    ENGINE_FALL_MPS,
    ENGINE_HOLD_BAND_MPS,
    ENGINE_SMOOTH_S,
    ENGINE_STRAIGHT_FRACTION,
=======
from typing import Any

from .constants import (
    ANNOUNCE_ARRIVED,
    ANNOUNCE_ARRIVING,
    ANNOUNCE_ARRIVING_BLOCKS,
    ANNOUNCE_DEPARTING,
    ANNOUNCE_LOCKOUT_MS,
    ENGINE_DETECT_ACCEL_MPS2,
    ENGINE_DETECT_S,
    ENGINE_RISE_MPS,
>>>>>>> origin/Train_Ctrl_integration
    FAILURES,
    MASS_KG,
    MAX_FORCE_N,
    MAX_POWER_W,
<<<<<<< HEAD
    MAX_SPEED_MPS,
    PICKUP_DETECT_MIN_BLOCKS,
    ROLLING_DECEL_MPS2,
    SERVICE_BAND_MPS,
    SERVICE_DECEL_MPS2,
    SETTLE_MPS,
=======
    NIGHT_END_S,
    NIGHT_START_S,
    PICKUP_DETECT_MIN_BLOCKS,
    SERVICE_BAND_MPS,
>>>>>>> origin/Train_Ctrl_integration
    STANDSTILL_MPS,
    TICK_S,
    V_FLOOR_MPS,
)
from .state import State, TrainModelCommands

class ControllerCore:
<<<<<<< HEAD
    """The PI speed law, the safety path and the toy plant.
=======
    """The PI speed law and the safety path.
>>>>>>> origin/Train_Ctrl_integration

    No Qt, no view: this class is what the hardware demo has to prove
    correct, and it runs unchanged whether or not a console is open.
    """

<<<<<<< HEAD
    def __init__(self, echo_ticks: int = 0) -> None:
        """Start a train's controller, inert until commissioned.

        ``echo_ticks`` is how many steps a command takes to come back
        in a Train Model report: 0 when the reports answer this step,
        as the toy plant and the bench do, and ECHO_TICKS under the
        central harness.
        """
=======
    def __init__(self) -> None:
>>>>>>> origin/Train_Ctrl_integration
        self.state = State()
        self.dt = TICK_S                    # seconds of simulation
        self.integral = 0.0
        # Inert until an engineer commissions the gains.
        self.armed = False
<<<<<<< HEAD
        # The door and light commands the plant last acted on, so it
        # answers a command once, on its edge, and leaves a state the
        # bench published alone in between.
        self._acted_doors: tuple[bool, bool] | None = (False, False)
        self._acted_lights: tuple[bool, bool] | None = (True, True)
        # Automatic station stop (REQUIREMENTS.md M6): a new beacon
        # station not yet served, and whether the train is held at
        # it, first with the doors open and then while they close;
        # and the steps of the 45 s dwell still to run (truth D007).
        self._station_pending = False
        self._dwelling = False
        self._closing = False
        self._dwell_steps_left = 0
        # Seconds left on an automatic announcement command.
        self._announce_left_s = 0.0
        # The emergency brake as commanded on the last echo_ticks
        # steps, newest last, so its echo in a Train Model report is
        # not taken for a passenger pull (apply_staged).
        self._sent_emergency: deque[bool] = deque(maxlen=echo_ticks)
        # A driver's release waiting for the next step, and the
        # passenger-brake-release that step sends: true for one step.
        self._release_pending = False
        self._release_out = False
=======
        # Station stop (REQUIREMENTS.md M6, M7): a station beacon
        # heard and not yet served, the station it named, whether the
        # train has arrived there, and, in Automatic, whether it is
        # held there with the doors open and then while they close.
        self._station_pending = False
        self._station_name = ""
        self._at_station = False
        self._dwelling = False
        self._closing = False
        # Whether last tick's inputs carried a beacon, so a beacon
        # turning up is told apart from one heard every tick.
        self._beacon_heard = False
        # The authority last acted on, for "arriving soon".
        self._last_authority: int | None = None
        # Seconds left on an announcement command.
        self._announce_left_s = 0.0
        # The last automatic announcement, which the driver may repeat
        # in Manual until the next one is sent (REQUIREMENTS.md M7).
        self.last_announcement = ""
        # Automatic lights (REQUIREMENTS.md M8): night and underground
        # as of the last tick, so only their changes act on the lights.
        self._night: bool | None = None
        self._underground = False
        # The failures that have already latched the emergency brake,
        # so a failure still latched after the driver's release does
        # not engage it again (REQUIREMENTS.md M2, M3).
        self._braked_for: set[str] = set()
>>>>>>> origin/Train_Ctrl_integration
        self._clear_detection()

    def _clear_detection(self) -> None:
        # What detect_failures() carries from one tick to the next.
<<<<<<< HEAD
        self._brake_unanswered_s = 0.0
        # The actual speed on each of the last ENGINE_DETECT_S of
        # steps, oldest first, kept only while every one of them had
        # power commanded and no brake commanded or reported.
        self._engine_window: deque[float] = deque(
            maxlen=round(ENGINE_DETECT_S / self.dt))
=======
        # Whether last tick's commands asked for the service brake with
        # the emergency brake off, so this tick's service brake state
        # answers it (the Train Model reports the service brake off
        # while the emergency brake is engaged, OPEN_ISSUES.md #23).
        self._service_asked = False
        self._engine_stalled_s = 0.0
        self._engine_ref_mps = 0.0
>>>>>>> origin/Train_Ctrl_integration
        self._last_signal: tuple[float, int] | None = None

    @property
    def failed(self) -> list[str]:
        """The detected failures still latched, in FAILURES order."""
        return [name for name in FAILURES if self.state.failures[name]]

    @property
    def received_signal(self) -> tuple[float, int]:
<<<<<<< HEAD
        """The Track Signal as it reaches the controller.

        Commanded speed (m/s) and authority (blocks). The toy plant
        stands in for the Train Model passing it through: with signal
        pickup injected it passes zeros (truth leaves zeros or stale
        values open; zeros is this plant's choice).
        """
        s = self.state
        if s.injected["signal_pickup"]:
            return 0.0, 0
=======
        """The Track Signal as it reached the controller.

        Commanded speed (m/s) and authority (blocks), as received. A
        lost pickup arrives as zeros (Train Model, development).
        """
        s = self.state
>>>>>>> origin/Train_Ctrl_integration
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

<<<<<<< HEAD
    def step(self, plant: bool = True) -> None:
        """Run one control period.
=======
    def step(self) -> None:
        """Run one control period on the inputs last applied.
>>>>>>> origin/Train_Ctrl_integration

        Only the speed law waits for the gains. The brakes and the
        safety path run from the first tick, because a console that
        has not been commissioned yet still has to be able to stop
        the train and still has to report what the brakes are doing.
<<<<<<< HEAD

        ``plant`` runs the toy train after the control law, for the
        standalone console and bench. Driven by the harness it is
        off: the Train Model does the physics (truth D009).
=======
>>>>>>> origin/Train_Ctrl_integration
        """
        s = self.state
        if self._announce_left_s > 0.0:
            self._announce_left_s -= self.dt
            if self._announce_left_s <= 0.0:
                s.announcement = ""
        self.detect_failures()
<<<<<<< HEAD
        if self.armed:
            if not s.manual:
                # Commanded speed is the speed limit, never above the
                # car's 70 km/h (REQUIREMENTS.md M1).
                s.target_mps = self.speed_cap_mps
            self._station_stop()

=======
        self._auto_lights()
        if self.armed:
            # The commanded speed is the only cap, in both modes: the
            # controller cannot know the true limit (REQUIREMENTS.md M1).
            # In Manual it lowers the driver's setpoint when it drops,
            # rather than springing back when it rises again.
            if s.manual:
                s.target_mps = min(s.target_mps, self.commanded_mps)
            else:
                s.target_mps = self.commanded_mps
        self._station_stop()
        if self.armed:
>>>>>>> origin/Train_Ctrl_integration
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
<<<<<<< HEAD
        # What this step sends: the brake as now commanded, and the
        # release once after the driver lets the brake go.
        self._sent_emergency.append(s.emergency_brake)
        self._release_out, self._release_pending = (
            self._release_pending, False)
        if plant:
            self._plant()
=======
        self._service_asked = s.service_brake and not s.emergency_brake
>>>>>>> origin/Train_Ctrl_integration

    def apply_staged(self, staged: dict[str, Any]) -> None:
        """Apply a set of Train Model signals read by read_inputs().

<<<<<<< HEAD
        A reported emergency brake that this controller has not
        commanded within the last echo_ticks steps is a passenger
        pull: latch it and cut power. One it commanded that recently
        is its own command coming back, so a driver's release is not
        undone by the report of the brake from before it. A report of
        false never releases the brake; only the driver does (D011,
=======
        An emergency brake state that turns on while this controller
        is not commanding it is a passenger pull: latch it and cut
        power. Only the turn on counts, so a state still reported on
        after the driver's release (the last command echoed, or a
        passenger latch held) does not latch it again: the driver's
        release overrides it (REQUIREMENTS.md M2). A report of false
        never releases it; only the driver does (D011,
>>>>>>> origin/Train_Ctrl_integration
        arbitration/passenger-emergency-brake).
        """
        s = self.state
        staged = dict(staged)
<<<<<<< HEAD
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
            echo = any(self._sent_emergency)
            if emergency and not s.emergency_brake and not echo:
                self.engage_emergency()
            s.fb_emergency_brake, s.fb_service_brake = emergency, service
=======
        # A beacon is heard only near a station (truth beacon.md).
        # One turning up, or naming a new station, means a station to
        # serve once the train stops there; one heard every tick while
        # the train stands there does not start another.
        heard = any(key in staged for key in
                    ("beacon_station", "beacon_side", "beacon_underground"))
        station = staged.get("beacon_station", s.beacon_station)
        new = not self._beacon_heard or station != s.beacon_station
        if heard and new and station and not self._at_station:
            self._station_pending = True
            self._station_name = station
        self._beacon_heard = heard
        emergency = staged.pop("emergency_brake_state", None)
        service = staged.pop("service_brake_state", None)
        for attr, value in staged.items():
            setattr(s, attr, value)
        if service is not None:
            s.fb_service_brake = service
        if emergency is not None:
            pulled = emergency and not s.fb_emergency_brake
            if pulled and not s.emergency_brake:
                self.engage_emergency()
            s.fb_emergency_brake = emergency
>>>>>>> origin/Train_Ctrl_integration

    def detect_failures(self) -> None:
        """Infer failures from what the Train Model sends back.

        REQ-FUNC-038. The Train Model does not report its failures
        (truth modules/train-model.md), so each one is read off the
        signals it does return, against what this controller last
        commanded:

<<<<<<< HEAD
            brake          the service brake was commanded, the
                           emergency brake was not, and Brake State
                           has not shown the service brake applied
                           for BRAKE_DETECT_S
            engine         over the last ENGINE_DETECT_S, power was
                           commanded above zero on every step, no
                           brake (service or emergency) was commanded
                           or reported applied on any step, and the
                           speed fell steadily by more than
                           ENGINE_FALL_MPS (ENGINE_SMOOTH_S means, each
                           within ENGINE_STRAIGHT_FRACTION of the fall
                           of a straight line); and the train is not
                           now within ENGINE_HOLD_BAND_MPS of its
                           target. Speed that does not rise is not a
                           failure: a train holding its target up a
                           grade needs power and gains no speed.
=======
            brake          last tick commanded the service brake,
                           not the emergency brake, and this tick's
                           service brake state still reads off
                           (REQUIREMENTS.md M4)
            engine         the power commanded should have pulled at
                           least ENGINE_DETECT_ACCEL_MPS2, no brake is
                           on, and the actual speed has not risen for
                           ENGINE_DETECT_S
>>>>>>> origin/Train_Ctrl_integration
            signal pickup  commanded speed and authority both fell to
                           zero in one update, from at least
                           PICKUP_DETECT_MIN_BLOCKS of authority

        A detected failure latches until it is cleared on the test
        bench (clear_failure).
        """
        s = self.state

<<<<<<< HEAD
        if (s.service_brake and not s.emergency_brake
                and not s.fb_service_brake):
            self._brake_unanswered_s += self.dt
            if self._brake_unanswered_s >= BRAKE_DETECT_S:
                s.failures["brake"] = True
        else:
            self._brake_unanswered_s = 0.0

        self._detect_engine()
=======
        if self._service_asked and not s.fb_service_brake:
            s.failures["brake"] = True

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
>>>>>>> origin/Train_Ctrl_integration

        signal = self.received_signal
        last = self._last_signal
        if (last is not None and last[0] > 0.0
                and last[1] >= PICKUP_DETECT_MIN_BLOCKS
                and signal == (0.0, 0)):
            s.failures["signal_pickup"] = True
        self._last_signal = signal

<<<<<<< HEAD
    def _detect_engine(self) -> None:
        # Rules by Kevin Schillinger, 2026-10-21; see detect_failures.
        # Counted in steps of simulated time, never wall clock.
        s = self.state
        v = s.actual_mps
        braked = (s.service_brake or s.emergency_brake
                  or s.fb_service_brake or s.fb_emergency_brake)
        window = self._engine_window
        if s.power_w <= 0.0 or braked:
            # No power asked for, or a brake explains any fall: watch
            # again from the next clean step.
            window.clear()
            return
        window.append(v)
        if len(window) < window.maxlen:
            return
        if abs(v - s.target_mps) <= ENGINE_HOLD_BAND_MPS:
            return                  # holding its target, as told
        # Half-second means, oldest first: down by more than the
        # control band in all, and steadily, every mean close to the
        # straight line from the first to the last.
        k = round(ENGINE_SMOOTH_S / self.dt)
        speeds = list(window)
        means = [sum(speeds[i:i + k]) / k
                 for i in range(0, len(speeds) - k + 1, k)]
        fall = means[0] - means[-1]
        if fall <= ENGINE_FALL_MPS:
            return
        last = len(means) - 1
        if all(abs(m - (means[0] - fall * i / last))
               <= ENGINE_STRAIGHT_FRACTION * fall
               for i, m in enumerate(means)):
            s.failures["engine"] = True

=======
>>>>>>> origin/Train_Ctrl_integration
    def clear_failure(self, name: str) -> None:
        """Let go of one detected failure, once it has been resolved.

        The test bench decides that, by clearing the failure it
        injected. The emergency brake stays on; the driver releases
        it at a stand once no failure is left.
        """
        self.state.failures[name] = False
<<<<<<< HEAD
        if name == "brake":
            self._brake_unanswered_s = 0.0
        elif name == "engine":
            self._engine_window.clear()
=======
        if name == "engine":
            self._engine_stalled_s = 0.0
            self._engine_ref_mps = self.state.actual_mps
>>>>>>> origin/Train_Ctrl_integration
        else:
            self._last_signal = None

    def respond_to_failures(self) -> None:
        """Stop the train while any detected failure is latched.

        REQ-FUNC-037.2: the controller stops the train when a failure
        is detected. Every failure removes the target and the power,
<<<<<<< HEAD
        and applies and latches the emergency brake:
=======
        and applies and latches the emergency brake once, on detection:
>>>>>>> origin/Train_Ctrl_integration

            engine         no traction is left to drive with
            signal pickup  commanded speed and authority cannot be
                           read from the track circuit, so they fail
                           safe to zero (the signal lights still read)
            brake          only the service brake has failed (truth
                           modules/train-model.md); the emergency
<<<<<<< HEAD
                           brake still works, so it stops the train

        The emergency brake cannot be released until the failure
        clears (release_emergency refuses while any is latched).
        """
=======
                           brake still works, so it stops the train.
                           The service brake is still commanded when
                           asked for (REQUIREMENTS.md M4)

        Once the train stands, the driver may release the emergency
        brake in Manual to try the train (release_emergency); the
        failure, still latched, does not engage it again
        (REQUIREMENTS.md M2, M3).
        """
        new = set(self.failed) - self._braked_for
        self._braked_for = set(self.failed)
>>>>>>> origin/Train_Ctrl_integration
        if not self.failed:
            return
        s = self.state
        s.target_mps = 0.0
        s.power_w = 0.0
        self.integral = 0.0
<<<<<<< HEAD
        if not s.emergency_brake:
            self.engage_emergency()
        s.service_brake = False
        if s.failures["brake"]:
            # The driver's request was for the brake that failed.
            s.service_request = False
=======
        if new and not s.emergency_brake:
            self.engage_emergency()
>>>>>>> origin/Train_Ctrl_integration

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

<<<<<<< HEAD
        # A failed service brake is not commanded, whatever asked for
        # it, in either mode; the emergency brake stands in for it.
        if s.failures["brake"]:
            s.service_brake = False

=======
>>>>>>> origin/Train_Ctrl_integration
    def engage_emergency(self) -> None:
        """Engage now, without waiting for the next control tick.

        Guide section 7 calls the emergency brake immediate, so the
        safety path runs on the press rather than up to one control
        period later.
        """
        self.state.emergency_brake = True
        self.enforce_safety()

    def release_emergency(self) -> bool:
<<<<<<< HEAD
        """Release the latched brake, at a stand with no failure.

        Asking a released brake to release is not a refusal: it is
        already where the caller wants it. A release also releases a
        passenger pull, since only the driver releases the emergency
        brake (REQUIREMENTS.md M2): the next step sends the one-shot
        passenger-brake-release, and the Train Model clears the pull
        (truth arbitration/passenger-emergency-brake).
=======
        """Release the latched brake, at a stand.

        With no failure latched, in either mode; with one still
        latched, only in Manual, so the driver can try the train
        (REQUIREMENTS.md M2, M3). Asking a released brake to release
        is not a refusal: it is already where the caller wants it.
>>>>>>> origin/Train_Ctrl_integration
        """
        s = self.state
        if not s.emergency_brake:
            return True
<<<<<<< HEAD
        if self.failed or abs(s.actual_mps) >= STANDSTILL_MPS:
            return False
        s.emergency_brake = False
        self._release_pending = True
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
=======
        if abs(s.actual_mps) >= STANDSTILL_MPS:
            return False
        if self.failed and not s.manual:
            return False
        s.emergency_brake = False
        return True

    def set_target_mps(self, mps: float) -> None:
        """Set the driver's target in m/s, capped at the commanded speed.

        The only cap (REQUIREMENTS.md M1); step() keeps it under the
        commanded speed as that changes.
        """
        s = self.state
        if s.manual and self.authority_blocks > 0 and not self.failed:
            s.target_mps = max(0.0, min(mps, self.commanded_mps))
>>>>>>> origin/Train_Ctrl_integration

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

<<<<<<< HEAD
    def _station_stop(self) -> None:
        # Automatic only (REQUIREMENTS.md M6). Stopped at a new
        # station: open the platform side and hold for the dwell. The
        # CTC Office schedules the dwell and the controller enforces
        # it (truth D007): it leaves once 45 s have passed with the
        # doors open and the Track Signal has resumed, whichever comes
        # last, closing the doors first and departing only once Door
        # State reports them closed. The dwell is counted in steps of
        # the fixed 0.1 s, so it never runs short on rounding.
        s = self.state
        if s.manual:
            self._dwelling = self._closing = False
            return
        if self._station_pending and self.at_stand:
            self._station_pending = False
            self._dwelling = True
            self._dwell_steps_left = round(DWELL_S / self.dt)
            for side in ("left", "right"):
                if self.platform_on(side):
                    self.command_door(side, True)
        elif self._dwelling and self._dwell_steps_left > 0:
            self._dwell_steps_left -= 1
        resumed = self.commanded_mps > 0.0 and self.authority_blocks > 0
        if self._dwelling and resumed and self._dwell_steps_left == 0:
=======
    def _announce(self, text: str) -> None:
        # The controller sends the command; the Train Model plays it
        # (REQUIREMENTS.md M7). Held for the lockout, on system time.
        self.state.announcement = text
        self.last_announcement = text
        self._announce_left_s = ANNOUNCE_LOCKOUT_MS / 1000

    @property
    def can_repeat(self) -> bool:
        """Whether the driver may repeat the last announcement now.

        In Manual, once one has been sent, and not while one plays.
        """
        s = self.state
        return s.manual and bool(self.last_announcement) \
            and not s.announcement

    def repeat_announcement(self) -> bool:
        """Send the last automatic announcement again, held as before.

        Returns whether it was sent (REQUIREMENTS.md M7).
        """
        if not self.can_repeat:
            return False
        self._announce(self.last_announcement)
        return True

    def _station_stop(self) -> None:
        # REQUIREMENTS.md M6, M7. Announcements in both modes:
        # arriving soon when the authority comes down to
        # ANNOUNCE_ARRIVING_BLOCKS; arrived once a station beacon has
        # been heard and the train stands with no authority left;
        # departing once the doors report closed and the Track Signal
        # resumes. Automatic also opens the platform side on arrival
        # and holds: the dwell is the Train Model's, so the controller
        # holds until the Track Signal resumes, then closes the doors
        # and departs only once Door State reports them closed.
        s = self.state
        authority = self.authority_blocks
        if (authority == ANNOUNCE_ARRIVING_BLOCKS
                and self._last_authority not in (None, authority)):
            self._announce(ANNOUNCE_ARRIVING.format(train_id=s.train_id))
        self._last_authority = authority
        if s.manual:
            self._dwelling = self._closing = False
        if self._station_pending and authority == 0 and self.at_stand:
            self._station_pending = False
            self._at_station = True
            self._announce(ANNOUNCE_ARRIVED.format(
                train_id=s.train_id, station=self._station_name))
            if not s.manual:
                self._dwelling = True
                for side in ("left", "right"):
                    if self.platform_on(side):
                        self.command_door(side, True)
        resumed = self.commanded_mps > 0.0 and authority > 0
        if self._dwelling and resumed:
>>>>>>> origin/Train_Ctrl_integration
            self._dwelling = False
            self._closing = True
            for side in ("left", "right"):
                self.command_door(side, False)
<<<<<<< HEAD
        if (self._closing and not s.fb_doors_left
                and not s.fb_doors_right):
            self._closing = False
=======
        doors_shut = not s.fb_doors_left and not s.fb_doors_right
        if self._closing and doors_shut:
            self._closing = False
        if (self._at_station and not self.station_hold and doors_shut
                and resumed):
            self._at_station = False
            self._announce(ANNOUNCE_DEPARTING.format(
                train_id=s.train_id, station=self._station_name))
>>>>>>> origin/Train_Ctrl_integration
        if self.station_hold:
            # Held, not creeping on what the integrator carried in.
            s.target_mps = 0.0
            self.integral = 0.0

<<<<<<< HEAD
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
=======
    def may_open(self, side: str) -> bool:
        """Whether one side's doors may be commanded open now.

        At a stand, either side; at a station (arrived, until it
        departs), only the platform side the beacon gave. The door
        interlock is the controller's (REQUIREMENTS.md M6).
        """
        if not self.at_stand:
            return False
        return not self._at_station or self.platform_on(side)

    def command_door(self, side: str, open_: bool) -> bool:
        """Command one side's doors.

        Opening follows may_open(). Closing is always allowed, so a
        door is never stuck open. Returns whether it was sent.
        """
        s = self.state
        if open_ and not self.may_open(side):
>>>>>>> origin/Train_Ctrl_integration
            return False
        if side == "left":
            s.doors_left = open_
        else:
            s.doors_right = open_
<<<<<<< HEAD
        self._acted_doors = None
        return True

    def command_lights(self, interior: bool, exterior: bool) -> None:
        """Command the lights, and have the plant answer it."""
        s = self.state
        s.interior_lights, s.exterior_lights = interior, exterior
        self._acted_lights = None
=======
        return True

    def command_lights(self, interior: bool, exterior: bool) -> None:
        """Command the lights."""
        s = self.state
        s.interior_lights, s.exterior_lights = interior, exterior

    @property
    def night(self) -> bool:
        """Whether the system time is between 18:00 and 06:00."""
        time_of_day = self.state.time_s % 86400
        return time_of_day >= NIGHT_START_S or time_of_day < NIGHT_END_S

    def _auto_lights(self) -> None:
        # REQUIREMENTS.md M8, in both modes. Underground is what the
        # last beacon said. Lights on when a beacon says underground
        # or at 18:00; off when a later beacon says not underground,
        # unless it is night, and at 06:00, unless underground. Only
        # those changes act, so the driver's own choice stands until
        # the next one. The first tick is the train spawned at the
        # yard: its lights are set on between 18:00 and 06:00, off
        # otherwise.
        s = self.state
        night, underground = self.night, s.beacon_underground
        if self._night is None:
            self.command_lights(night, night)
        else:
            if ((night and not self._night)
                    or (underground and not self._underground)):
                self.command_lights(True, True)
            elif ((self._night and not night and not underground)
                    or (self._underground and not underground
                        and not night)):
                self.command_lights(False, False)
        self._night, self._underground = night, underground
>>>>>>> origin/Train_Ctrl_integration

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
<<<<<<< HEAD
            passenger_brake_release=self._release_out,
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
        # brake still works. Under an engine or a brake failure, and
        # only then for now, rolling resistance (same source) also
        # acts on the train, so a dead engine slows it as it would on
        # the Train Model and can be detected by the fall.
        # Signal pickup is applied in received_signal.
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
        elif not service_works or s.injected["engine"]:
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
=======
        )
>>>>>>> origin/Train_Ctrl_integration
