"""The PI speed law and the safety path, per train.

No Qt: this runs the same whether the bench or the central harness
drives it. It knows only what it receives and what it sends
(REQUIREMENTS.md M0); the bench's simulation is train_ctrl.bench_sim.
"""

from __future__ import annotations

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
    ENGINE_RISE_MPS,
    FAILURES,
    MASS_KG,
    MAX_FORCE_N,
    NIGHT_END_S,
    NIGHT_START_S,
    PICKUP_DETECT_MIN_BLOCKS,
    SERVICE_BAND_MPS,
    STANDSTILL_MPS,
    TICK_S,
    V_FLOOR_MPS,
)
from .state import State, TrainModelCommands
from .vital import PowerInputs, VitalVote, compute_power, vote_2oo3


class ControllerCore:
    """The PI speed law and the safety path.

    No Qt, no view: this class is what the hardware demo has to prove
    correct, and it runs unchanged whether or not a console is open.
    """

    def __init__(self, echo_ticks: int = BENCH_ECHO_TICKS) -> None:
        """``echo_ticks``: ticks between a command and its report.

        BENCH_ECHO_TICKS on the bench, ECHO_TICKS under the central
        harness (OPEN_ISSUES.md #42).
        """
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
        self._clear_detection()

    def _clear_detection(self) -> None:
        # What detect_failures() carries from one tick to the next.
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
        self._last_signal: tuple[float, int] | None = None

    @property
    def failed(self) -> list[str]:
        """The detected failures still latched, in FAILURES order."""
        return [name for name in FAILURES if self.state.failures[name]]

    @property
    def received_signal(self) -> tuple[float, int]:
        """The Track Signal as it reached the controller.

        Commanded speed (m/s) and authority (blocks), as received. A
        lost pickup arrives as zeros (Train Model, development).
        """
        s = self.state
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

    def step(self) -> None:
        """Run one control period on the inputs last applied.

        Only the speed law waits for the gains. The brakes and the
        safety path run from the first tick, because a console that
        has not been commissioned yet still has to be able to stop
        the train and still has to report what the brakes are doing.
        """
        s = self.state
        if self._announce_left_s > 0.0:
            self._announce_left_s -= self.dt
            if self._announce_left_s <= 0.0:
                s.announcement = ""
        self.detect_failures()
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

    def apply_staged(self, staged: dict[str, Any]) -> None:
        """Apply a set of Train Model signals read by read_inputs().

        An emergency brake state that turns on while this controller
        is not commanding it is a passenger pull: latch it and cut
        power. Only the turn on counts, so a state still reported on
        after the driver's release (the last command echoed, or a
        passenger latch held) does not latch it again: the driver's
        release overrides it (REQUIREMENTS.md M2). A report of false
        never releases it; only the driver does (D011,
        arbitration/passenger-emergency-brake).
        """
        s = self.state
        staged = dict(staged)
        # The beacon is received only while the train is on a
        # station's block (REQUIREMENTS.md M6).
        self._beacon_now = any(
            key in staged for key in
            ("beacon_station", "beacon_side", "beacon_underground"))
        emergency = staged.pop("emergency_brake_state", None)
        service = staged.pop("service_brake_state", None)
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
            s.fb_emergency_brake = emergency

    def detect_failures(self) -> None:
        """Infer failures from what the Train Model sends back.

        REQ-FUNC-038. The Train Model does not report its failures
        (truth modules/train-model.md), so each one is read off the
        signals it does return, against what this controller last
        commanded:

            brake          the command echo_ticks ago asked for the
                           service brake, not the emergency brake,
                           and this tick's service brake state, its
                           report, still reads off (REQUIREMENTS.md
                           M4)
            engine         the power commanded should have pulled at
                           least ENGINE_DETECT_ACCEL_MPS2, no brake is
                           on, and the actual speed has not risen for
                           ENGINE_DETECT_S
            signal pickup  commanded speed and authority both fell to
                           zero in one update, from at least
                           PICKUP_DETECT_MIN_BLOCKS of authority

        A brake failure resolves when the service brake answers
        again: the command echo_ticks ago asked for it and this tick's
        report reads it applied (REQUIREMENTS.md §4, M3). The others
        latch until cleared on the test bench (clear_failure).
        """
        s = self.state

        if self._service_asked[0]:
            if not s.fb_service_brake:
                s.failures["brake"] = True
            elif s.failures["brake"]:
                s.failures["brake"] = False

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
        injected. The emergency brake stays on until the driver
        releases it (release_emergency).
        """
        self.state.failures[name] = False
        if name == "engine":
            self._engine_stalled_s = 0.0
            self._engine_ref_mps = self.state.actual_mps
        else:
            self._last_signal = None

    def respond_to_failures(self) -> None:
        """Stop the train while any detected failure is latched.

        REQ-FUNC-037.2: the controller stops the train when a failure
        is detected. Every failure removes the target and the power,
        and applies and latches the emergency brake once, on detection:

            engine         no traction is left to drive with
            signal pickup  commanded speed and authority cannot be
                           read from the track circuit, so they fail
                           safe to zero (the signal lights still read)
            brake          only the service brake has failed (truth
                           modules/train-model.md); the emergency
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
        if not self.failed:
            return
        s = self.state
        s.target_mps = 0.0
        s.power_w = 0.0
        self.integral = 0.0
        if new and not s.emergency_brake:
            self.engage_emergency()

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

    def engage_emergency(self) -> None:
        """Engage now, without waiting for the next control tick.

        Guide section 7 calls the emergency brake immediate, so the
        safety path runs on the press rather than up to one control
        period later.
        """
        self.state.emergency_brake = True
        self.enforce_safety()

    def release_emergency(self) -> bool:
        """Release the latched brake, at a stand.

        With no failure latched, in either mode; with one still
        latched, only in Manual, so the driver can try the train
        (REQUIREMENTS.md M2, M3). Not during a vitality breach: only
        once the power command agrees again (M21). Asking a released
        brake to release is not a refusal: it is already where the
        caller wants it.
        """
        s = self.state
        if not s.emergency_brake:
            return True
        if abs(s.actual_mps) >= STANDSTILL_MPS or s.vital_breach:
            return False
        if self.failed and not s.manual:
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
            s.target_mps = max(0.0, min(mps, self.commanded_mps))

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
            # Held, not creeping on what the integrator carried in.
            s.target_mps = 0.0
            self.integral = 0.0

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
        )
