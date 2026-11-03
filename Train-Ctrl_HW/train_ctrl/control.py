<<<<<<< HEAD
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
=======
"""The PI speed law and the safety path, per train.

No Qt: this runs the same whether the bench or the central harness
drives it. It knows only what it receives and what it sends
(REQUIREMENTS.md M0); the bench's simulation is train_ctrl.bench_sim.
>>>>>>> integrate/quirky-into-development-resolved
"""

from __future__ import annotations

<<<<<<< HEAD
<<<<<<< HEAD
import math
=======
>>>>>>> integrate/quirky-into-development-resolved
from collections import deque
from typing import Any

from .constants import (
    ANNOUNCE_ARRIVED,
    ANNOUNCE_ARRIVING,
    ANNOUNCE_ARRIVING_BLOCKS,
    ANNOUNCE_DEPARTING,
    ANNOUNCE_LOCKOUT_MS,
    BENCH_ECHO_TICKS,
    DWELL_S,
    ENGINE_DETECT_ACCEL_MPS2,
    ENGINE_DETECT_S,
<<<<<<< HEAD
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
=======
    ENGINE_RISE_MPS,
    FAILURES,
    MASS_KG,
    MAX_FORCE_N,
    NIGHT_END_S,
    NIGHT_START_S,
    SERVICE_BAND_MPS,
>>>>>>> integrate/quirky-into-development-resolved
    STANDSTILL_MPS,
    TICK_S,
    V_FLOOR_MPS,
)
from .state import State, TrainModelCommands
from .vital import PowerInputs, VitalVote, compute_power, vote_2oo3


class ControllerCore:
<<<<<<< HEAD
<<<<<<< HEAD
    """The PI speed law, the safety path and the toy plant.
=======
    """The PI speed law and the safety path.
>>>>>>> origin/Train_Ctrl_integration
=======
    """The PI speed law and the safety path.
>>>>>>> integrate/quirky-into-development-resolved

    No Qt, no view: this class is what the hardware demo has to prove
    correct, and it runs unchanged whether or not a console is open.
    """

<<<<<<< HEAD
<<<<<<< HEAD
    def __init__(self, echo_ticks: int = 0) -> None:
        """Start a train's controller, inert until commissioned.
=======
    def __init__(self, echo_ticks: int = BENCH_ECHO_TICKS) -> None:
        """``echo_ticks``: ticks between a command and its report.
>>>>>>> integrate/quirky-into-development-resolved

        BENCH_ECHO_TICKS on the bench, ECHO_TICKS under the central
        harness (OPEN_ISSUES.md #42).
        """
=======
    def __init__(self) -> None:
>>>>>>> origin/Train_Ctrl_integration
        self.state = State()
        self.dt = TICK_S                    # seconds of simulation
        self.echo_ticks = echo_ticks
        self.integral = 0.0
        # The three channels of the vital power command
        # (REQUIREMENTS.md M21): one calculation, made three times a
        # tick from the same inputs.
        self.channels = (compute_power,) * 3
        # The last vote, for the numbers drawer only: it goes when the
        # drawer is removed in the final iteration.
        self.last_vote: VitalVote | None = None
        # Inert until an engineer commissions the gains.
        self.armed = False
<<<<<<< HEAD
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
=======
        # Station boarding (REQUIREMENTS.md M6), in both modes. The
        # stop's phase: "" away from one; "opening" from arrival until
        # Door State reports the doors open; "dwell" while the dwell
        # runs; "boarded" after it, until a new Track Signal;
        # "departing" while the doors close for it. The station is the
        # one the beacon named on arrival.
        self._phase = ""
        self._station_name = ""
        self._dwell_ticks = 0
        # Whether this tick's inputs carried a beacon: it is received
        # only while the train is on a station's block.
        self._beacon_now = False
        # The authority last acted on, for "arriving soon".
        self._last_authority: int | None = None
        # Set at spawn and at each station departure: "arriving soon"
        # is then decided at the departure itself (REQUIREMENTS.md M7).
        self._departure_check = True
        # Seconds left on an announcement command.
        self._announce_left_s = 0.0
>>>>>>> integrate/quirky-into-development-resolved
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
<<<<<<< HEAD
>>>>>>> origin/Train_Ctrl_integration
=======
>>>>>>> integrate/quirky-into-development-resolved
        self._clear_detection()

    def _clear_detection(self) -> None:
        # What detect_failures() carries from one tick to the next.
<<<<<<< HEAD
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
=======
        # The last echo_ticks commands, oldest first: whether each
        # asked for the service brake with the emergency brake off,
        # and whether each engaged the emergency brake. This tick's
        # reports answer the oldest (the Train Model reports the
        # service brake off while the emergency brake is engaged,
        # OPEN_ISSUES.md #23).
        empty = [False] * self.echo_ticks
        self._service_asked = deque(empty, maxlen=self.echo_ticks)
        self._emergency_sent = deque(empty, maxlen=self.echo_ticks)
        self._engine_stalled_s = 0.0
        self._engine_ref_mps = 0.0
>>>>>>> integrate/quirky-into-development-resolved

    @property
    def failed(self) -> list[str]:
        """The detected failures still latched, in FAILURES order."""
        return [name for name in FAILURES if self.state.failures[name]]

    @property
    def received_signal(self) -> tuple[float, int]:
<<<<<<< HEAD
<<<<<<< HEAD
        """The Track Signal as it reaches the controller.
=======
        """The Track Signal as it reached the controller.
>>>>>>> integrate/quirky-into-development-resolved

        Commanded speed (m/s) and authority (blocks), the last values
        received. A lost pickup arrives as null (``signal_lost``), and
        these keep the values before it.
        """
        s = self.state
<<<<<<< HEAD
        if s.injected["signal_pickup"]:
            return 0.0, 0
=======
        """The Track Signal as it reached the controller.

        Commanded speed (m/s) and authority (blocks), as received. A
        lost pickup arrives as zeros (Train Model, development).
        """
        s = self.state
>>>>>>> origin/Train_Ctrl_integration
=======
>>>>>>> integrate/quirky-into-development-resolved
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
<<<<<<< HEAD
    def step(self, plant: bool = True) -> None:
        """Run one control period.
=======
    def step(self) -> None:
        """Run one control period on the inputs last applied.
>>>>>>> origin/Train_Ctrl_integration
=======
    def step(self) -> None:
        """Run one control period on the inputs last applied.
>>>>>>> integrate/quirky-into-development-resolved

        Only the speed law waits for the gains. The brakes and the
        safety path run from the first tick, because a console that
        has not been commissioned yet still has to be able to stop
        the train and still has to report what the brakes are doing.
<<<<<<< HEAD
<<<<<<< HEAD

        ``plant`` runs the toy train after the control law, for the
        standalone console and bench. Driven by the harness it is
        off: the Train Model does the physics (truth D009).
=======
>>>>>>> origin/Train_Ctrl_integration
=======
>>>>>>> integrate/quirky-into-development-resolved
        """
        s = self.state
        if self._announce_left_s > 0.0:
            self._announce_left_s -= self.dt
            if self._announce_left_s <= 0.0:
                s.announcement = ""
        self.detect_failures()
<<<<<<< HEAD
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
=======
        self._auto_lights()
        if self.armed:
            # The commanded speed is the only cap, in both modes: the
            # controller cannot know the true limit (REQUIREMENTS.md
            # M1). In Manual it lowers the driver's setpoint when it
            # drops, rather than springing back when it rises again.
            if s.manual:
                s.target_mps = min(s.target_mps, self.commanded_mps)
            else:
                s.target_mps = self.commanded_mps
        self._station_stop()
        if self.armed:
>>>>>>> integrate/quirky-into-development-resolved
            error = s.target_mps - s.actual_mps
            # A target of zero means stop, so the brake holds to a
            # stand rather than leaving the train creeping inside the
            # band with no resistance to bring it down.
            stopping = s.target_mps <= 0.0 and s.actual_mps > 0.0
            s.service_brake = (
                error < -SERVICE_BAND_MPS or s.service_request or stopping
            )
            self._vital_power()
        else:
            s.power_w = 0.0
            s.service_brake = s.service_request

        self.respond_to_failures()
        self.enforce_safety()
<<<<<<< HEAD
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
=======
        self._service_asked.append(s.service_brake and not s.emergency_brake)
        self._emergency_sent.append(s.emergency_brake)

    def _vital_power(self) -> None:
        # REQUIREMENTS.md M21. The power command is calculated three
        # times from the same inputs and used only if at least two
        # results agree. With no two equal, this tick's command is
        # rejected: 0 W, the integrator as it was, and the emergency
        # brake latched. The breach clears on the next tick that
        # agrees; the driver then releases the brake (M2).
        s = self.state
        inputs = PowerInputs(
            target_mps=s.target_mps, actual_mps=s.actual_mps,
            kp=s.kp, ki=s.ki, dt=self.dt, braking=s.service_brake,
            integral=self.integral)
        a, b, c = (channel(inputs) for channel in self.channels)
        vote = vote_2oo3((a, b, c))
        self.last_vote = vote
        s.vital_breach = vote.agreed is None
        if vote.agreed is None:
            s.power_w = 0.0
            if not s.emergency_brake:
                self.engage_emergency()
            return
        s.power_w = vote.agreed.power_w
        self.integral = vote.agreed.integral
>>>>>>> integrate/quirky-into-development-resolved

    def apply_staged(self, staged: dict[str, Any]) -> None:
        """Apply a set of Train Model signals read by read_inputs().

<<<<<<< HEAD
<<<<<<< HEAD
        A reported emergency brake that this controller has not
        commanded within the last echo_ticks steps is a passenger
        pull: latch it and cut power. One it commanded that recently
        is its own command coming back, so a driver's release is not
        undone by the report of the brake from before it. A report of
        false never releases the brake; only the driver does (D011,
=======
=======
>>>>>>> integrate/quirky-into-development-resolved
        An emergency brake state that turns on while this controller
        is not commanding it is a passenger pull: latch it and cut
        power. Only the turn on counts, so a state still reported on
        after the driver's release (the last command echoed, or a
        passenger latch held) does not latch it again: the driver's
        release overrides it (REQUIREMENTS.md M2). A report of false
        never releases it; only the driver does (D011,
<<<<<<< HEAD
>>>>>>> origin/Train_Ctrl_integration
=======
>>>>>>> integrate/quirky-into-development-resolved
        arbitration/passenger-emergency-brake).
        """
        s = self.state
        staged = dict(staged)
<<<<<<< HEAD
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
=======
        # The beacon is received only while the train is on a
        # station's block (REQUIREMENTS.md M6).
        self._beacon_now = any(
            key in staged for key in
            ("beacon_station", "beacon_side", "beacon_underground"))
        emergency = staged.pop("emergency_brake_state", None)
        service = staged.pop("service_brake_state", None)
>>>>>>> integrate/quirky-into-development-resolved
        for attr, value in staged.items():
            setattr(s, attr, value)
        if service is not None:
            s.fb_service_brake = service
        if emergency is not None:
            # A turn on within echo_ticks of this controller's own
            # emergency brake command is that command coming back.
            pulled = emergency and not s.fb_emergency_brake
            if (pulled and not s.emergency_brake
                    and not any(self._emergency_sent)):
                self.engage_emergency()
<<<<<<< HEAD
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
=======
            s.fb_emergency_brake = emergency
>>>>>>> integrate/quirky-into-development-resolved

    def detect_failures(self) -> None:
        """Infer failures from what the Train Model sends back.

        REQ-FUNC-038. The Train Model does not report its failures
        (truth modules/train-model.md), so each one is read off the
        signals it does return, against what this controller last
        commanded:

<<<<<<< HEAD
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
=======
            brake          the command echo_ticks ago asked for the
                           service brake, not the emergency brake,
                           and this tick's service brake state, its
                           report, still reads off (REQUIREMENTS.md
                           M4)
>>>>>>> integrate/quirky-into-development-resolved
            engine         the power commanded should have pulled at
                           least ENGINE_DETECT_ACCEL_MPS2, no brake is
                           on, and the actual speed has not risen for
                           ENGINE_DETECT_S
<<<<<<< HEAD
>>>>>>> origin/Train_Ctrl_integration
            signal pickup  commanded speed and authority both fell to
                           zero in one update, from at least
                           PICKUP_DETECT_MIN_BLOCKS of authority
=======
            signal pickup  commanded speed or authority arrived null:
                           the Train Model could not read the Track
                           Signal (Kevin Schillinger 2026-10-28). A
                           valid 0 is never taken for one
>>>>>>> integrate/quirky-into-development-resolved

        A brake failure resolves when the service brake answers
        again: the command echo_ticks ago asked for it and this tick's
        report reads it applied (REQUIREMENTS.md §4, M3). The others
        latch until cleared on the test bench (clear_failure).
        """
        s = self.state

<<<<<<< HEAD
<<<<<<< HEAD
        if (s.service_brake and not s.emergency_brake
                and not s.fb_service_brake):
            self._brake_unanswered_s += self.dt
            if self._brake_unanswered_s >= BRAKE_DETECT_S:
=======
        if self._service_asked[0]:
            if not s.fb_service_brake:
>>>>>>> integrate/quirky-into-development-resolved
                s.failures["brake"] = True
            elif s.failures["brake"]:
                s.failures["brake"] = False

<<<<<<< HEAD
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
=======
>>>>>>> integrate/quirky-into-development-resolved
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

        if s.signal_lost:
            s.failures["signal_pickup"] = True

=======
>>>>>>> origin/Train_Ctrl_integration
    def clear_failure(self, name: str) -> None:
        """Let go of one detected failure, once it has been resolved.

        The test bench decides that, by clearing the failure it
        injected. The emergency brake stays on until the driver
        releases it (release_emergency).
        """
        self.state.failures[name] = False
<<<<<<< HEAD
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
=======
        if name == "engine":
            self._engine_stalled_s = 0.0
            self._engine_ref_mps = self.state.actual_mps
>>>>>>> integrate/quirky-into-development-resolved

    def respond_to_failures(self) -> None:
        """Stop the train while any detected failure is latched.

        REQ-FUNC-037.2: the controller stops the train when a failure
        is detected. Every failure removes the target and the power,
<<<<<<< HEAD
<<<<<<< HEAD
        and applies and latches the emergency brake:
=======
        and applies and latches the emergency brake once, on detection:
>>>>>>> origin/Train_Ctrl_integration
=======
        and applies and latches the emergency brake once, on detection:
>>>>>>> integrate/quirky-into-development-resolved

            engine         no traction is left to drive with
            signal pickup  commanded speed and authority cannot be
                           read from the track circuit, so they fail
                           safe to zero (the signal lights still read)
            brake          only the service brake has failed (truth
                           modules/train-model.md); the emergency
<<<<<<< HEAD
<<<<<<< HEAD
                           brake still works, so it stops the train
=======
                           brake still works, so it stops the train.
                           The service brake is still commanded when
                           asked for (REQUIREMENTS.md M4)
>>>>>>> integrate/quirky-into-development-resolved

        Once the train stands, the driver may release the emergency
        brake in Manual to try the train (release_emergency); the
        failure, still latched, does not engage it again
        (REQUIREMENTS.md M2, M3).
        """
<<<<<<< HEAD
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
=======
        new = set(self.failed) - self._braked_for
        self._braked_for = set(self.failed)
>>>>>>> integrate/quirky-into-development-resolved
        if not self.failed:
            return
        s = self.state
        s.target_mps = 0.0
        s.power_w = 0.0
        self.integral = 0.0
<<<<<<< HEAD
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
=======
        if new and not s.emergency_brake:
            self.engage_emergency()
>>>>>>> integrate/quirky-into-development-resolved

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
<<<<<<< HEAD
        # A failed service brake is not commanded, whatever asked for
        # it, in either mode; the emergency brake stands in for it.
        if s.failures["brake"]:
            s.service_brake = False

=======
>>>>>>> origin/Train_Ctrl_integration
=======
>>>>>>> integrate/quirky-into-development-resolved
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
=======
        """Release the latched brake, at a stand.

        With no failure latched, in either mode; with one still
        latched, only in Manual, so the driver can try the train
        (REQUIREMENTS.md M2, M3). Not during a vitality breach: only
        once the power command agrees again (M21). Asking a released
        brake to release is not a refusal: it is already where the
        caller wants it.
>>>>>>> integrate/quirky-into-development-resolved
        """
        s = self.state
        if not s.emergency_brake:
            return True
<<<<<<< HEAD
<<<<<<< HEAD
        if self.failed or abs(s.actual_mps) >= STANDSTILL_MPS:
=======
        if abs(s.actual_mps) >= STANDSTILL_MPS or s.vital_breach:
            return False
        if self.failed and not s.manual:
>>>>>>> integrate/quirky-into-development-resolved
            return False
        s.emergency_brake = False
        return True

    def set_target_mps(self, mps: float) -> None:
        """Set the driver's target (m/s), capped at the commanded speed.

        The only cap (REQUIREMENTS.md M1); step() keeps it under the
        commanded speed as that changes.
        """
        s = self.state
        if s.manual and self.authority_blocks > 0 and not self.failed:
<<<<<<< HEAD
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
=======
            s.target_mps = max(0.0, min(mps, self.commanded_mps))
>>>>>>> integrate/quirky-into-development-resolved

    def platform_on(self, side: str) -> bool:
        """Whether the last beacon put a platform on this side."""
        return ("L" if side == "left" else "R") in self.state.beacon_side

    @property
    def at_stand(self) -> bool:
        """Whether the Train Model reports the train stopped."""
        return abs(self.state.actual_mps) < STANDSTILL_MPS

    @property
    def dwell_left(self) -> float:
        """The share of the station dwell still to run, 1 to 0.

        0 outside the dwell (REQUIREMENTS.md M6).
        """
        if self._phase != "dwell":
            return 0.0
        return self._dwell_ticks / round(DWELL_S / self.dt)

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

<<<<<<< HEAD
    def _station_stop(self) -> None:
        # REQUIREMENTS.md M6, M7, in both modes. Arrival is a beacon
        # received with no authority, no commanded speed and the train
        # at a stand: the platform side opens, and the dwell runs from
        # Door State reporting it open. At the end of the dwell the
        # doors close; a new Track Signal then closes any the driver
        # reopened, and the train leaves once Door State reports them
        # closed. No traction while a stop holds it or a door is open.
        s = self.state
        authority = self.authority_blocks
        resumed = self.commanded_mps > 0.0 and authority > 0
        reported_shut = not (s.fb_doors_left or s.fb_doors_right)
        if (not self._phase and self._beacon_now and authority == 0
                and self.commanded_mps == 0.0 and self.at_stand):
            self._phase = "opening"
            self._station_name = s.beacon_station
            self._announce(ANNOUNCE_ARRIVED.format(
                train_id=s.train_id, station=self._station_name))
            for side in ("left", "right"):
                if self.platform_on(side):
                    self.command_door(side, True)
<<<<<<< HEAD
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
=======
        if self._phase == "opening" and not reported_shut:
            self._phase = "dwell"
            self._dwell_ticks = round(DWELL_S / self.dt)
        if self._phase == "dwell":
            self._dwell_ticks -= 1
            if self._dwell_ticks <= 0:
                self._phase = "boarded"
                self._close_doors()
        if self._phase == "boarded" and resumed:
            self._phase = "departing"
            self._close_doors()
        if self._phase == "departing" and reported_shut:
            self._phase = ""
            self._announce(ANNOUNCE_DEPARTING.format(
                train_id=s.train_id, station=self._station_name))
            self._departure_check = True
        self._arriving_soon(authority, resumed and reported_shut)
        if not self.at_stand:
            # Doors stay closed while the train moves.
            self._close_doors()
        if (self._phase or not reported_shut
                or s.doors_left or s.doors_right):
>>>>>>> integrate/quirky-into-development-resolved
            # Held, not creeping on what the integrator carried in.
            s.target_mps = 0.0
            self.integral = 0.0

<<<<<<< HEAD
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
=======
    def _arriving_soon(self, authority: int, departing: bool) -> None:
        # REQUIREMENTS.md M7. Never at a station. At a departure (from
        # the yard, or from a station once "departing" has played),
        # 3 blocks or fewer is announced at once; otherwise it is
        # announced when the authority reaches 3.
        s = self.state
        if self._departure_check:
            if (departing and self.armed and not self._phase
                    and not s.announcement):
                self._departure_check = False
                if authority <= ANNOUNCE_ARRIVING_BLOCKS:
                    self._announce(
                        ANNOUNCE_ARRIVING.format(train_id=s.train_id))
        elif (not self._phase and authority == ANNOUNCE_ARRIVING_BLOCKS
                and self._last_authority not in (None, authority)):
            self._announce(ANNOUNCE_ARRIVING.format(train_id=s.train_id))
        self._last_authority = authority

    def _close_doors(self) -> None:
        self.command_door("left", False)
        self.command_door("right", False)

    def may_open(self, side: str) -> bool:
        """Whether the driver may open one side's doors now.

        At a stand, and not while boarding runs: at a station after
        the dwell, only the platform side the beacon gave; elsewhere,
        either side (REQUIREMENTS.md M6).
        """
        if not self.at_stand or self._phase in (
                "opening", "dwell", "departing"):
>>>>>>> integrate/quirky-into-development-resolved
            return False
        return self._phase != "boarded" or self.platform_on(side)

    @property
    def may_close(self) -> bool:
        """Whether the driver may close doors now.

        Not while boarding runs: the controller closes them at the end
        of the dwell and for a new Track Signal (REQUIREMENTS.md M6).
        """
        return self._phase not in ("opening", "dwell", "departing")

    def driver_door(self, side: str, open_: bool) -> bool:
        """Open or close one side's doors for the driver.

        Follows may_open() and may_close. Returns whether it was sent.
        """
        if not (self.may_open(side) if open_ else self.may_close):
            return False
        self.command_door(side, open_)
        return True

    def command_door(self, side: str, open_: bool) -> None:
        """Command one side's doors, as the controller decides."""
        s = self.state
        if side == "left":
            s.doors_left = open_
        else:
            s.doors_right = open_
<<<<<<< HEAD
<<<<<<< HEAD
        self._acted_doors = None
        return True
=======
>>>>>>> integrate/quirky-into-development-resolved

    def command_lights(self, interior: bool, exterior: bool) -> None:
        """Command the lights."""
        s = self.state
        s.interior_lights, s.exterior_lights = interior, exterior
<<<<<<< HEAD
        self._acted_lights = None
=======
        return True

    def command_lights(self, interior: bool, exterior: bool) -> None:
        """Command the lights."""
        s = self.state
        s.interior_lights, s.exterior_lights = interior, exterior
=======
>>>>>>> integrate/quirky-into-development-resolved

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
<<<<<<< HEAD
>>>>>>> origin/Train_Ctrl_integration
=======
>>>>>>> integrate/quirky-into-development-resolved

    def commands(self) -> TrainModelCommands:
        """Return this tick's commands to the Train Model, in SI."""
        s = self.state
        return TrainModelCommands(
            power_w=s.power_w,
            service_brake=s.service_brake,
            emergency_brake=s.emergency_brake,
            power_verified=not s.vital_breach,
            door_command=(s.doors_left, s.doors_right),
            light_command=(s.interior_lights, s.exterior_lights),
            temperature_setpoint_c=s.target_temp_c,
            announcement=s.announcement,
<<<<<<< HEAD
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
=======
        )
>>>>>>> integrate/quirky-into-development-resolved
