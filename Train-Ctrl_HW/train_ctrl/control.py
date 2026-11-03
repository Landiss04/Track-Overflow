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
    ENGINE_DETECT_S,
    ENGINE_FALL_MPS,
    ENGINE_HOLD_BAND_MPS,
    ENGINE_PULSE_S,
    ENGINE_SMOOTH_S,
    ENGINE_STRAIGHT_FRACTION,
    ENGINE_RETEST_S,
    ENGINE_TEST_MIN_MPS2,
    ENGINE_TEST_POWER_W,
    ENGINE_UNDER_WAY_MPS,
    FAILURES,
    NIGHT_END_S,
    NIGHT_START_S,
    SERVICE_BAND_MPS,
    STANDSTILL_MPS,
    TICK_S,
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
        # Why the controller engaged the emergency brake again after the
        # driver's release, for the console: "rollback" or "runaway"
        # (respond_to_failures); "" otherwise.
        self.stop_reason = ""
        self._clear_detection()

    def _clear_detection(self) -> None:
        # What detect_failures() carries from one tick to the next.
        # The last echo_ticks commands, oldest first: whether each
        # asked for the service brake, and whether each engaged the
        # emergency brake. This tick's reports answer the oldest. The
        # Train Model reports the service brake whether or not the
        # emergency brake is on (claude/quirky-fermi-sickg4 57e8847),
        # so the driver can try it under the emergency brake.
        empty = [False] * self.echo_ticks
        self._service_asked = deque(empty, maxlen=self.echo_ticks)
        self._emergency_sent = deque(empty, maxlen=self.echo_ticks)
        # The actual speed on each of the last ENGINE_DETECT_S of
        # ticks, oldest first, kept only while every one of them had
        # power commanded and no brake commanded or reported.
        self._engine_window: deque[float] = deque(
            maxlen=round(ENGINE_DETECT_S / self.dt))
        # The engine test (_test_engine): its phase ("" when none
        # runs, else "on", "off" or "verdict"), the ticks it has run,
        # and the speeds it reads.
        self._engine_test = ""
        self._engine_test_ticks = 0
        self._engine_test_speeds: list[float] = []
        # Whether this test repeats one that found the engine dead
        # under way (_test_engine).
        self._engine_recheck = False
        # Seconds held at a stand since the last test, towards the
        # next one (ENGINE_RETEST_S).
        self._engine_held_s = 0.0
        # Whether this departure's test has passed, and the seconds
        # since the last test began and the speed it began at
        # (_check_start).
        self._start_passed = False
        self._since_test_s = 0.0
        self._test_ref_mps = 0.0
        # After a test passes, seconds the steady fall still waits for
        # the speed law to take back the test's step (_detect_engine).
        self._settle_s = 0.0

    @property
    def failed(self) -> list[str]:
        """The detected failures still latched, in FAILURES order."""
        return [name for name in FAILURES if self.state.failures[name]]

    @property
    def received_signal(self) -> tuple[float, int]:
        """The Track Signal as it reached the controller.

        Commanded speed (m/s) and authority (blocks), the last values
        received. A lost pickup arrives as null (``signal_lost``), and
        these keep the values before it.
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
            # A target of zero means stop and stay stopped: the brake
            # holds the train, at a stand too, and the integrator is
            # cleared, so nothing it carried from the run creeps the
            # train against the brake. Not at a stand under a brake
            # failure: that brake cannot hold it, and the driver's
            # press is what tries it (REQUIREMENTS.md M4).
            stopping = s.target_mps <= 0.0 and (
                s.actual_mps > 0.0 or not s.failures["brake"])
            if stopping:
                self.integral = 0.0
            s.service_brake = (
                error < -SERVICE_BAND_MPS or s.service_request or stopping
            )
            self._vital_power()
        else:
            s.power_w = 0.0
            s.service_brake = s.service_request

        self._check_start()
        self.respond_to_failures()
        self.enforce_safety()
        self._service_asked.append(s.service_brake)
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
            engine         a steady fall: over the last
                           ENGINE_DETECT_S, power was commanded and no
                           brake commanded or reported on every tick,
                           and the speed fell by more than
                           ENGINE_FALL_MPS (ENGINE_SMOOTH_S means, each
                           within ENGINE_STRAIGHT_FRACTION of the fall
                           of a straight line), with the train not
                           within ENGINE_HOLD_BAND_MPS of its target.
                           That only starts the engine test, which
                           decides (_test_engine); with the test barred
                           (_may_test_engine), the fall alone latches it
            signal pickup  commanded speed or authority arrived null:
                           the Train Model could not read the Track
                           Signal (Kevin Schillinger 2026-10-28). A
                           valid 0 is never taken for one

        A brake failure resolves when the service brake answers
        again: the command echo_ticks ago asked for it and this tick's
        report reads it applied. A press the brake did not answer is
        dropped, so the driver presses again to try it once more. A
        signal pickup failure resolves when commanded speed and
        authority both arrive non-null again (REQUIREMENTS.md §4, M3).
        An engine failure resolves when the engine test at a stand
        shows the engine pulling (_test_engine).
        """
        s = self.state

        if self._service_asked[0]:
            if not s.fb_service_brake:
                s.failures["brake"] = True
                s.service_request = False
            elif s.failures["brake"]:
                s.failures["brake"] = False

        if s.failures["engine"] or self._engine_test:
            self._test_engine()
        else:
            self._detect_engine()

        s.failures["signal_pickup"] = s.signal_lost

    def _detect_engine(self) -> None:
        # Rules by Kevin Schillinger, 2026-10-21; see detect_failures.
        # Counted in ticks of simulated time, never wall clock.
        s = self.state
        v = s.actual_mps
        braked = (s.service_brake or s.emergency_brake
                  or s.fb_service_brake or s.fb_emergency_brake)
        window = self._engine_window
        if s.power_w <= 0.0 or braked:
            # No power asked for, or a brake explains any fall: watch
            # again from the next clean tick.
            window.clear()
            return
        if self._settle_s > 0.0:
            # The test's tick of full power lifted the speed; the speed
            # law takes that back as a fall. Watch again once it is
            # back where the test began, or ENGINE_DETECT_S at most.
            if v <= self._test_ref_mps:
                self._settle_s = 0.0
            else:
                self._settle_s -= self.dt
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
            # A healthy train sagging onto a grade can fall this way
            # too, so the fall only asks the question; the test answers.
            if self._may_test_engine():
                self._start_engine_test()
                self._test_engine()
            else:
                s.failures["engine"] = True

    def _test_engine(self) -> None:
        # REQUIREMENTS.md §4, OPEN_ISSUES.md #23. Started by the
        # driver's release of the emergency brake (release_emergency),
        # by every departure from a stand (_check_start), and every
        # ENGINE_RETEST_S while held at a stand on a latched failure.
        # The service brake comes off on the tick full power goes on,
        # so nothing is ever left holding the train between them. One
        # tick of full power, one of none, then the brake (latched) or
        # the speed law (a departure) while the reports come back. The
        # speed's change on each tick answers the command echo_ticks
        # before it; grade, load and rolling resistance act the same
        # on both ticks, so the difference is the engine's pull. A dead
        # engine moves only as gravity rolls it for those two ticks:
        # under 1 cm at 5 % on the Train Model.
        s = self.state
        if not self._engine_test:
            held = (not s.emergency_brake and self.at_stand
                    and self._may_test_engine())
            self._engine_held_s = self._engine_held_s + self.dt if held \
                else 0.0
            if self._engine_held_s < ENGINE_RETEST_S:
                return
            self._start_engine_test()
        if s.emergency_brake or not self._may_test_engine():
            self._engine_test = ""      # abandoned; the next one retries
            return
        n, e = self._engine_test_ticks, self.echo_ticks
        self._engine_test_ticks += 1
        self._engine_test = ("on", "off")[n] if n < 2 else "verdict"
        if n in (e, e + 1) and (s.fb_service_brake or s.fb_emergency_brake):
            # A brake was on under one of the two commands (a passenger
            # pull): no verdict.
            self._engine_test = ""
            return
        if n < e - 1:
            return
        speeds = self._engine_test_speeds
        speeds.append(s.actual_mps)
        if n < e + 1:
            return
        on, off = speeds[1] - speeds[0], speeds[2] - speeds[1]
        self._engine_test = ""
        if (on - off) / self.dt < ENGINE_TEST_MIN_MPS2 and not (
                self.at_stand or s.failures["engine"]
                or self._engine_recheck):
            # Dead, under way: a grade change between the two ticks
            # (gravity on one, not the other) reads the same. Test once
            # more, a few metres on; blocks are longer than two tests'
            # run (35 m against 15 m at 19 m/s), so one sees one grade.
            self._start_engine_test()
            self._engine_recheck = True
            self._test_engine()
            return
        self._engine_recheck = False
        if (on - off) / self.dt >= ENGINE_TEST_MIN_MPS2:
            # Answered: the steady fall asks again only on a fresh
            # window, not on every tick of the one that asked.
            s.failures["engine"] = False
            self._engine_window.clear()
            self._start_passed = True
            self._settle_s = ENGINE_DETECT_S
        else:
            s.failures["engine"] = True

    def _check_start(self) -> None:
        # REQUIREMENTS.md §4. Every departure from a stand is tested,
        # from the tick the speed law first asks for power at a stand
        # with no brake: that tick sends the test's power instead. A
        # dead engine on a down-grade rolls forward under gravity as a
        # working one would, so how the speed moves cannot tell them
        # apart; the test can. Once one passes, not again until the
        # power stops. Under way, the same test runs every
        # ENGINE_PULSE_S on a tick the speed law asks for power with no
        # brake and the train at least SERVICE_BAND_MPS under its
        # target, so the pulse's power cannot carry it over, and the
        # speed not down since the last test: on a down-grade gravity
        # holds the speed, so the steady fall (_detect_engine) never
        # sees a dead engine there. While the speed falls, the steady
        # fall is left to judge it, undisturbed by the pulse's step.
        s = self.state
        if s.failures["engine"] or self._engine_test:
            return
        self._since_test_s += self.dt
        if not (s.power_w > 0.0
                and not (s.service_brake or s.emergency_brake)):
            self._start_passed = False
            return
        if s.actual_mps >= ENGINE_UNDER_WAY_MPS:
            # Under way forwards: coming to a stand again under power,
            # a stall on a climb, is tested again before it rolls back.
            self._start_passed = False
        if self.at_stand:
            due = not self._start_passed
        else:
            due = (self._since_test_s >= ENGINE_PULSE_S
                   and s.target_mps - s.actual_mps >= SERVICE_BAND_MPS
                   and s.actual_mps >= self._test_ref_mps - ENGINE_FALL_MPS)
        if due and self._may_test_engine():
            self._start_engine_test()
            self._test_engine()

    def _start_engine_test(self) -> None:
        self._engine_test, self._engine_test_ticks = "on", 0
        self._engine_recheck = False
        self._engine_test_speeds = []
        self._engine_held_s = 0.0
        self._since_test_s = 0.0
        self._test_ref_mps = self.state.actual_mps

    def _may_test_engine(self) -> bool:
        # Power is sent only with no failure but the engine's, some
        # authority, the doors closed, and the power command agreed.
        s = self.state
        return (set(self.failed) <= {"engine"} and self.authority_blocks > 0
                and not (s.doors_left or s.doors_right
                         or s.fb_doors_left or s.fb_doors_right)
                and not s.vital_breach)

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
        brake in either mode to try the train (release_emergency); the
        failure, still latched, does not engage it again
        (REQUIREMENTS.md M2, M3). With only an engine failure latched,
        the release starts the engine test (_test_engine), which
        commands its own power and no brake for two ticks; outside
        those, an engine failure with the emergency brake released
        holds the train on the service brake.
        """
        new = set(self.failed) - self._braked_for
        self._braked_for = set(self.failed)
        s = self.state
        if self._engine_test and not self._may_test_engine():
            # Another failure found this tick: it is handled below,
            # not overridden by the test's commands.
            self._engine_test = ""
        if self._engine_test in ("on", "off"):
            # The test's own commands: full power, then none, and no
            # brake. A fixed command, not the speed law's, so it is
            # not voted (M21). A departure or a pulse under way keeps
            # the driver's target and the speed law's integrator.
            if self.failed:
                s.target_mps = 0.0
                self.integral = 0.0
            s.service_brake = False
            s.power_w = (ENGINE_TEST_POWER_W if self._engine_test == "on"
                         else 0.0)
            return
        if not self.failed:
            return
        s.target_mps = 0.0
        s.power_w = 0.0
        self.integral = 0.0
        if "engine" in self.failed and not s.emergency_brake:
            # Released, with no test running (it ended, or another
            # failure is latched too): nothing pulls, so the service
            # brake holds the train rather than let it roll back on a
            # grade (OPEN_ISSUES.md #23).
            s.service_brake = True
        if new and not s.emergency_brake:
            self.engage_emergency()
        elif (s.failures["brake"] and not s.emergency_brake
                and abs(s.actual_mps) >= STANDSTILL_MPS):
            # Released with the service brake failed: nothing else can
            # stop the train if it starts to move, back on an up-grade
            # or forward on a down-grade, so engage the emergency brake
            # again (REQUIREMENTS.md M3).
            self.stop_reason = ("rollback" if s.actual_mps < 0.0
                                else "runaway")
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

        # Rolling back with no brake asked for. Nothing else stops it,
        # so the emergency brake does, as for a brake failure (M3). Not
        # during an engine test, whose own two ticks may roll it back a
        # little before its verdict. Under power, a working engine
        # climbs every grade on the lines, so the engine has failed: a
        # stall right after a start, before the steady fall can see it.
        # shortcut: holds only while every grade on the lines (steepest
        # 5 %) is climbable at full load: the traction cap (MAX_FORCE_N,
        # 35.5 kN) holds a full train on the data sheet's 60 per mille;
        # recheck it if the track or the traction changes.
        if (not (s.emergency_brake or s.service_brake or self._engine_test)
                and s.actual_mps <= -STANDSTILL_MPS):
            if s.power_w > 0.0:
                s.failures["engine"] = True
            else:
                self.stop_reason = "rollback"
            s.emergency_brake = True

        # The emergency brake comes from the driver, from a Train
        # Model report of a passenger pull, from a detected failure
        # (respond_to_failures), or from a rollback.
        if s.emergency_brake:
            s.power_w = 0.0
            self.integral = 0.0

    def engage_emergency(self) -> None:
        """Engage now, without waiting for the next control tick.

        Guide section 7 calls the emergency brake immediate, so the
        safety path runs on the press rather than up to one control
        period later. It abandons any test of the engine; the next
        release starts a new one (_test_engine).
        """
        self.state.emergency_brake = True
        self._engine_test = ""
        self.enforce_safety()

    def release_emergency(self) -> bool:
        """Release the latched brake, at a stand.

        In either mode, with or without a failure still latched, so
        the driver can try the train (REQUIREMENTS.md M2, M3; with
        only an engine failure latched it starts a test,
        _test_engine). Not during a vitality breach: only once the
        power command agrees again (M21). Asking a released brake to
        release is not a refusal: it is already where the caller wants
        it.
        """
        s = self.state
        if not s.emergency_brake:
            return True
        if abs(s.actual_mps) >= STANDSTILL_MPS or s.vital_breach:
            return False
        s.emergency_brake = False
        self.stop_reason = ""
        if self.failed == ["engine"] and self._may_test_engine():
            self._start_engine_test()
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
