"""Engine failure detection and resolution against a Train Model
style plant.

The rules (Kevin Schillinger, 2026-10-21): never flag a train that is
holding its target; flag on speed falling, not on speed failing to
rise, with power commanded and no brake applied anywhere in the
window; and use a window a few seconds longer than the old 2 s.
Resolution: a differential test at a stand once the driver releases
the emergency brake (OPEN_ISSUES.md #23).

The plant here is the Train Model's force balance cut down to what
detection sees: traction P / v capped at F_max (zero with the engine
failed), grade, rolling resistance and the two brakes, with the
controller's commands acting on the next tick as they do under the
central harness.

Run from this folder (``Train-Ctrl_HW``)::

    python -m pytest tests
"""

from __future__ import annotations

import math
import random
import sys
import unittest
from unittest import mock
from pathlib import Path

_HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_HERE))
sys.path.insert(1, str(_HERE.parent))

from train_ctrl import ECHO_TICKS, TICK_S  # noqa: E402
from train_ctrl.constants import (  # noqa: E402
    EBRAKE_DECEL_MPS2,
    ENGINE_DETECT_S,
    ENGINE_RETEST_S,
    GRAVITY_MPS2,
    MASS_KG,
    MAX_FORCE_N,
    ROLLING_RESISTANCE_COEFF,
    SERVICE_BAND_MPS,
    SERVICE_DECEL_MPS2,
)
from train_ctrl import control  # noqa: E402
from train_ctrl.control import ControllerCore  # noqa: E402

KP, KI = 400_000.0, 8_000.0
# The car empty with its crew of five, and fully loaded (data sheet).
EMPTY_KG = 40_900.0 + 5 * 77.1
LOADED_KG = 56_700.0


class Plant:
    """Train Model physics, as far as engine detection can see it."""

    def __init__(self, speed_mps: float = 0.0,
                 grade_percent: float = 0.0,
                 mass_kg: float = MASS_KG) -> None:
        self.v = speed_mps
        # Traction is capped at the 2/3-load F_max whatever the load,
        # as on the Train Model.
        self.mass = mass_kg
        self.grade = math.atan(grade_percent / 100.0)
        self.engine_failed = False
        # Whether gravity may roll the train backwards from a stand.
        self.rolls_back = False
        # Brake State as reported: what was applied on the last step.
        self.fb_service = False
        self.fb_emergency = False

    def step(self, power_w: float, service: bool, emergency: bool) -> None:
        """Integrate one tick under the commands just sent."""
        v = self.v
        if self.engine_failed or power_w <= 0.0:
            traction = 0.0
        elif v > 0.0:
            traction = min(MAX_FORCE_N, power_w / v)
        else:
            traction = MAX_FORCE_N
        resist = self.mass * GRAVITY_MPS2 * (
            math.sin(self.grade)
            + ROLLING_RESISTANCE_COEFF * math.cos(self.grade))
        a = (traction - resist) / self.mass
        brake = (EBRAKE_DECEL_MPS2 if emergency
                 else SERVICE_DECEL_MPS2 if service else 0.0)
        if not self.rolls_back:
            self.v = max(0.0, v + (a - brake) * TICK_S)
        elif v == 0.0 and abs(a) <= brake:
            pass                    # the brake holds it at a stand
        else:
            # A brake opposes the motion and never reverses it.
            new_v = v + (a - math.copysign(brake, v or a)) * TICK_S
            self.v = 0.0 if brake and v * new_v < 0.0 else new_v
        self.fb_service, self.fb_emergency = service, emergency


class Rig:
    """One armed controller, driven tick by tick under the harness
    timing: each step reads the plant's report of the last tick, and
    its commands act on the next."""

    def __init__(self, plant: Plant, commanded_mps: float) -> None:
        self.plant = plant
        self.core = ControllerCore(echo_ticks=ECHO_TICKS)
        s = self.core.state
        s.kp, s.ki = KP, KI
        s.commanded_mps = commanded_mps
        s.authority_blocks = 999
        s.actual_mps = plant.v
        self.core.armed = True
        self.speeds: list[float] = []
        # The command the plant acts on next: under the harness a
        # command sent on one tick is acted on the next, and its
        # report arrives the tick after that (ECHO_TICKS).
        self.pending = (0.0, False, False)

    def report(self, speed_mps: float | None = None) -> None:
        s = self.core.state
        s.actual_mps = self.plant.v if speed_mps is None else speed_mps
        s.fb_service_brake = self.plant.fb_service
        s.fb_emergency_brake = self.plant.fb_emergency

    def tick(self, speed_mps: float | None = None) -> None:
        """One harness tick; ``speed_mps`` overrides the report."""
        self.report(speed_mps)
        self.speeds.append(self.core.state.actual_mps)
        self.core.step()
        s = self.core.state
        self.plant.step(*self.pending)
        self.pending = (s.power_w, s.service_brake, s.emergency_brake)

    def run(self, seconds: float) -> None:
        for _ in range(round(seconds / TICK_S)):
            self.tick()

    def run_until_failed(self, seconds: float) -> float | None:
        """Seconds until the engine failure latched, or None."""
        for n in range(1, round(seconds / TICK_S) + 1):
            self.tick()
            if self.core.state.failures["engine"]:
                return n * TICK_S
        return None


# The engine test under way reads the speed's change over single ticks,
# so it needs the Train Model's exact speed reports. Tests that write
# the reported speed themselves exercise the steady fall alone.
steady_fall_only = mock.patch.object(control, "ENGINE_PULSE_S", math.inf)


class EngineDetectionTest(unittest.TestCase):

    def test_window_is_longer_than_the_old_two_seconds(self) -> None:
        self.assertGreaterEqual(ENGINE_DETECT_S, 2.0 + 2.0)

    def test_holding_speed_up_a_grade_never_latches(self) -> None:
        # Green 93 (2 %) at 5 m/s, as the round trip runs it, and at
        # its 25 km/h limit; and Green 7 (5 %, the steepest) for a
        # train light enough to climb it: power on, speed steady at
        # its target, from a standing start on the grade.
        for grade, target, mass in ((2.0, 5.0, MASS_KG),
                                    (2.0, 25 / 3.6, MASS_KG),
                                    (5.0, 11.0, EMPTY_KG)):
            with self.subTest(grade=grade, target=target):
                rig = Rig(Plant(0.0, grade, mass), target)
                rig.run(300.0)
                self.assertGreater(rig.core.state.power_w, 0.0)
                self.assertLess(abs(rig.plant.v - target),
                                SERVICE_BAND_MPS)
                self.assertEqual(rig.core.failed, [])
                self.assertFalse(rig.core.state.emergency_brake)

    def test_running_onto_a_grade_never_latches(self) -> None:
        # Holding its target on the flat, the train runs onto the
        # grade. The speed sags, with power on and no brake, until the
        # PI catches it: the round trip's Green 7 at 11 m/s, Green 93
        # at 5 m/s, and Green's limits on those grades.
        for grade, target, mass in ((5.0, 11.0, EMPTY_KG),
                                    (5.0, 45 / 3.6, EMPTY_KG),
                                    (4.0, 45 / 3.6, MASS_KG),
                                    (2.0, 5.0, MASS_KG),
                                    (2.0, 25 / 3.6, LOADED_KG),
                                    (3.0, 45 / 3.6, LOADED_KG),
                                    (2.0, 70 / 3.6, MASS_KG),
                                    (5.0, 70 / 3.6, EMPTY_KG)):
            with self.subTest(grade=grade, target=target, mass=mass):
                rig = Rig(Plant(0.0, 0.0, mass), target)
                rig.run(90.0)
                rig.plant.grade = math.atan(grade / 100.0)
                rig.run(120.0)
                rig.plant.grade = 0.0
                rig.run(60.0)
                self.assertEqual(rig.core.failed, [])

    def test_a_real_engine_failure_on_the_flat_latches(self) -> None:
        # Cruise at 15 m/s, then the engine fails: no traction, and
        # only rolling resistance slows the train, the slowest fall a
        # failed engine can give on the flat.
        for target in (5.0, 15.0, 70 / 3.6):
            with self.subTest(target=target):
                rig = Rig(Plant(0.0, 0.0), target)
                rig.run(120.0)
                self.assertEqual(rig.core.failed, [])
                self.assertLess(abs(rig.plant.v - target),
                                SERVICE_BAND_MPS)
                rig.plant.engine_failed = True
                latched = rig.run_until_failed(ENGINE_DETECT_S + 0.5)
                self.assertIsNotNone(latched,
                                     "the engine failure was not found")
                self.assertTrue(rig.core.state.emergency_brake)
                self.assertEqual(rig.core.state.power_w, 0.0)

    def test_a_real_engine_failure_up_a_grade_latches(self) -> None:
        rig = Rig(Plant(0.0, 2.0), 5.0)
        rig.run(300.0)
        self.assertEqual(rig.core.failed, [])
        rig.plant.engine_failed = True
        self.assertIsNotNone(rig.run_until_failed(ENGINE_DETECT_S + 0.5))

    def test_a_real_engine_failure_while_accelerating_latches(self) -> None:
        rig = Rig(Plant(0.0, 0.0), 15.0)
        rig.run(10.0)
        rig.plant.engine_failed = True
        latched = rig.run_until_failed(ENGINE_DETECT_S + 0.5)
        self.assertIsNotNone(latched, "the engine failure was not found")

    @steady_fall_only
    def test_falling_speed_with_a_brake_in_the_window_does_not_latch(
            self) -> None:
        # Power is commanded throughout (the train is under target),
        # but the Train Model reports a brake applied for a moment in
        # the window, and the speed falls with it. A brake, not the
        # engine, explains the fall.
        rig = Rig(Plant(10.0, 0.0), 12.0)
        v = 10.0
        for n in range(round(3 * ENGINE_DETECT_S / TICK_S)):
            braking = n % round(ENGINE_DETECT_S / TICK_S) == 5
            rig.plant.fb_service = braking
            rig.report(v)
            rig.core.step()
            self.assertGreater(rig.core.state.power_w, 0.0)
            v -= 0.04
        self.assertEqual(rig.core.failed, [])

    def test_slowing_on_the_service_brake_then_pulling_does_not_latch(
            self) -> None:
        # The commanded speed drops: the service brake slows the train
        # to the new target, then power holds it there.
        rig = Rig(Plant(0.0, 0.0), 15.0)
        rig.run(120.0)
        rig.core.state.commanded_mps = 8.0
        rig.run(60.0)
        rig.core.state.commanded_mps = 15.0
        rig.run(60.0)
        self.assertEqual(rig.core.failed, [])

    def test_a_driver_brake_then_release_does_not_latch(self) -> None:
        rig = Rig(Plant(0.0, 0.0), 15.0)
        rig.run(120.0)
        rig.core.state.service_request = True
        rig.run(2.0)
        rig.core.state.service_request = False
        rig.run(60.0)
        self.assertEqual(rig.core.failed, [])

    @steady_fall_only
    def test_tick_noise_around_the_target_does_not_latch(self) -> None:
        # Reported speed jitters tick to tick around a target the
        # controller holds: alternating, and random, inside and a
        # little beyond the control band, with power on throughout.
        target = 10.0
        rng = random.Random(1140)
        patterns = {
            "alternating in band": lambda n: (-1) ** n * 0.04,
            "alternating beyond band": lambda n: (-1) ** n * 0.10,
            "random in band": lambda n: rng.uniform(-0.05, 0.05),
            "random beyond band": lambda n: rng.uniform(-0.08, 0.08),
        }
        for name, noise in patterns.items():
            with self.subTest(name):
                rig = Rig(Plant(target, 0.0), target)
                rig.core.integral = 2.0
                for n in range(round(120.0 / TICK_S)):
                    rig.tick(target + noise(n))
                self.assertEqual(rig.core.failed, [])

    @steady_fall_only
    def test_steady_out_of_band_speed_does_not_latch(self) -> None:
        # Below target and not falling (say, power-limited on a
        # climb): not rising is not a failure.
        rig = Rig(Plant(5.0, 0.0), 8.0)
        for _ in range(round(30.0 / TICK_S)):
            rig.tick(5.0)
        self.assertGreater(rig.core.state.power_w, 0.0)
        self.assertEqual(rig.core.failed, [])

    def test_a_failure_on_a_down_grade_is_found_under_way(self) -> None:
        # Gravity holds the speed, so it never falls; the engine test
        # under way finds it within a few pulses.
        for grade in (-0.5, -2.0, -5.0):
            for target in (5.0, 15.0):
                with self.subTest(grade=grade, target=target):
                    rig = Rig(Plant(0.0, grade), target)
                    rig.plant.rolls_back = True
                    rig.run(120.0)
                    self.assertEqual(rig.core.failed, [])
                    rig.plant.engine_failed = True
                    latched = rig.run_until_failed(4 * control.ENGINE_PULSE_S)
                    self.assertIsNotNone(latched)
                    self.assertTrue(rig.core.state.emergency_brake)

    def test_never_pushes_over_the_target_under_way(self) -> None:
        # The pulse runs only from under the target by the control
        # band, so its tick of full power adds nothing to how far the
        # speed law itself overshoots on a down-grade.
        def overshoot(grade: float) -> float:
            rig = Rig(Plant(0.0, grade), 15.0)
            rig.plant.rolls_back = True
            rig.run(60.0)
            over = 0.0
            for _ in range(round(120.0 / TICK_S)):
                rig.tick()
                over = max(over, rig.plant.v - 15.0)
            self.assertEqual(rig.core.failed, [])
            return over

        for grade in (0.0, -0.5, -2.0, -5.0, 2.0):
            with self.subTest(grade=grade):
                with steady_fall_only:
                    without = overshoot(grade)
                self.assertLess(overshoot(grade), without + 0.01)

    def test_a_pulse_then_a_climb_does_not_latch(self) -> None:
        # The test's tick of full power lifts the speed a little, and
        # the speed law takes it back. Onto a climb just after, that
        # and the sag read as one straight fall unless the steady fall
        # waits for the step to be taken back first.
        for shift in range(0, 60, 3):
            with self.subTest(shift=shift):
                rig = Rig(Plant(0.0, 0.0, LOADED_KG), 19.0)
                rig.plant.rolls_back = True
                rig.run(90.0 + shift * TICK_S)
                rig.plant.grade = math.atan(0.5 / 100.0)
                rig.run(30.0)
                self.assertEqual(rig.core.failed, [])

    def test_a_grade_change_inside_a_pulse_does_not_latch(self) -> None:
        # A working engine at 19 m/s pulls about 0.43 m/s^2, less than
        # the 0.47 m/s^2 a step from flat onto -5 % adds: a step between
        # the pulse's two ticks reads as a dead engine, so a dead verdict
        # under way is tested once more before it latches.
        for offset in range(1, 4):
            with self.subTest(offset=offset):
                rig = Rig(Plant(0.0, 0.0, LOADED_KG), 19.0)
                rig.plant.rolls_back = True
                rig.run(60.0)
                # Downhill now, so pulses run; flat again until one does.
                rig.plant.grade = math.atan(-1.0 / 100.0)
                for _ in range(round(30.0 / TICK_S)):
                    rig.tick()
                    if rig.core._engine_test == "on":
                        break
                self.assertEqual(rig.core._engine_test, "on")
                for _ in range(offset):
                    rig.tick()
                rig.plant.grade = math.atan(-5.0 / 100.0)
                rig.run(10.0)
                self.assertEqual(rig.core.failed, [])

    def test_a_grade_change_inside_a_pulse_does_not_pass_a_dead_engine(
            self) -> None:
        # The other way round: down -5 % onto flat, or flat onto +5 %,
        # between two of the test's ticks, gravity reads 0.49 m/s^2 of
        # pull from a dead engine. Before the under-way test ran none,
        # full, none, a step at two of the positions passed it and the
        # engine was found 5.8-7.0 s later.
        for before, after in ((-5.0, 0.0), (0.0, 5.0)):
            for shift in range(6):
                with self.subTest(before=before, after=after,
                                  shift=shift):
                    rig = Rig(Plant(0.0, before, LOADED_KG), 15.0)
                    rig.plant.rolls_back = True
                    rig.run(40.0)
                    rig.plant.engine_failed = True
                    for _ in range(round(30.0 / TICK_S)):
                        if rig.core._engine_test:
                            break
                        rig.tick()
                    self.assertTrue(rig.core._engine_test)
                    for _ in range(shift):
                        rig.tick()
                    rig.plant.grade = math.atan(after / 100.0)
                    self.assertIsNotNone(rig.run_until_failed(1.5))

    def test_a_stall_right_after_a_start_latches_the_engine(self) -> None:
        # The engine dies just after the departure test passes, before
        # 1 m/s and before a steady-fall window: the train stalls on
        # the climb and rolls back under power. A working engine climbs
        # every grade on the lines, so that rollback names the engine.
        for mass in (EMPTY_KG, LOADED_KG):
            with self.subTest(mass=mass):
                rig = Rig(Plant(0.0, 5.0, mass), 10.0)
                rig.plant.rolls_back = True
                rig.run(1.0)
                self.assertEqual(rig.core.failed, [])
                rig.plant.engine_failed = True
                back = 0.0
                for _ in range(round(10.0 / TICK_S)):
                    rig.tick()
                    back += min(0.0, rig.plant.v) * TICK_S
                self.assertEqual(rig.core.failed, ["engine"])
                self.assertTrue(rig.core.state.emergency_brake)
                self.assertEqual(rig.plant.v, 0.0)
                self.assertLess(-back, 0.05)


class EngineTestTest(unittest.TestCase):
    """The engine test at a stand: one tick of power, one of none."""

    #: Long enough for the test to finish (0.4 s under the harness).
    TEST_S = 3.0

    def latched_at_a_stand(self, grade: float = 0.0,
                           mass_kg: float = MASS_KG) -> Rig:
        """An engine failure found on the flat, the train stopped on
        it, then standing on ``grade`` with gravity free to roll it
        once released."""
        rig = Rig(Plant(0.0, 0.0, mass_kg), 10.0)
        rig.run(60.0)
        rig.plant.engine_failed = True
        self.assertIsNotNone(rig.run_until_failed(ENGINE_DETECT_S + 0.5))
        rig.run(10.0)
        self.assertEqual(rig.plant.v, 0.0)
        self.assertTrue(rig.core.state.emergency_brake)
        rig.plant.grade = math.atan(grade / 100.0)
        rig.plant.rolls_back = True
        return rig

    def test_a_repaired_engine_clears_on_any_grade_and_load(self) -> None:
        # Including a full train on 5 %, which cannot climb it: the
        # engine still pulls.
        for grade in (0.0, 2.0, 5.0, -5.0):
            for mass in (EMPTY_KG, LOADED_KG):
                with self.subTest(grade=grade, mass=mass):
                    rig = self.latched_at_a_stand(grade, mass)
                    rig.plant.engine_failed = False
                    rig.run(5.0)
                    self.assertEqual(rig.core.failed, ["engine"],
                                     "cleared before the release")
                    self.assertTrue(rig.core.release_emergency())
                    rig.run(self.TEST_S)
                    self.assertEqual(rig.core.failed, [])

    def test_a_dead_engine_stays_latched_on_any_grade(self) -> None:
        # Including a downhill, where the speed rises without power.
        for grade in (0.0, 2.0, 5.0, -5.0):
            with self.subTest(grade=grade):
                rig = self.latched_at_a_stand(grade, LOADED_KG)
                self.assertTrue(rig.core.release_emergency())
                rig.run(self.TEST_S + 5.0)
                s = rig.core.state
                self.assertEqual(rig.core.failed, ["engine"])
                self.assertEqual(s.power_w, 0.0)
                self.assertTrue(s.service_brake)
                self.assertFalse(s.emergency_brake)
                self.assertEqual(rig.plant.v, 0.0)

    def test_a_repair_while_held_is_found_by_the_retest(self) -> None:
        # The first test finds the engine dead; it is repaired while
        # the train is held, and a retest finds it without the driver.
        rig = self.latched_at_a_stand(2.0, LOADED_KG)
        self.assertTrue(rig.core.release_emergency())
        rig.run(self.TEST_S)
        self.assertEqual(rig.core.failed, ["engine"])
        rig.plant.engine_failed = False
        rig.run(ENGINE_RETEST_S + self.TEST_S)
        self.assertEqual(rig.core.failed, [])

    def test_a_dead_engine_is_retested_and_stays_latched(self) -> None:
        rig = self.latched_at_a_stand(0.0, LOADED_KG)
        self.assertTrue(rig.core.release_emergency())
        rig.run(4 * (ENGINE_RETEST_S + self.TEST_S))
        self.assertEqual(rig.core.failed, ["engine"])
        self.assertTrue(rig.core.state.service_brake)

    def test_a_dead_engine_at_a_stand_is_found_on_starting(self) -> None:
        # Fails while standing on the flat: its speed never falls, so
        # only the start check finds it, once power is asked for.
        rig = Rig(Plant(0.0, 0.0, LOADED_KG), 0.0)
        rig.run(5.0)
        rig.plant.engine_failed = True
        rig.run(5.0)
        self.assertEqual(rig.core.failed, [])
        rig.core.state.commanded_mps = 10.0
        rig.run(self.TEST_S)
        self.assertEqual(rig.core.failed, ["engine"])
        self.assertTrue(rig.core.state.emergency_brake)

    def roll(self, rig: Rig, seconds: float) -> tuple[float, int]:
        """Run; return the distance rolled and the ticks commanded
        with neither power nor a brake."""
        metres, free = 0.0, 0
        for _ in range(round(seconds / TICK_S)):
            rig.tick()
            s = rig.core.state
            free += not (s.power_w > 0.0 or s.service_brake
                         or s.emergency_brake)
            metres += abs(rig.plant.v) * TICK_S
        return metres, free

    def test_a_dead_engine_on_a_down_grade_is_found_on_starting(
            self) -> None:
        # Gravity rolls it forward as a working engine would, so only
        # the test can tell; it rolls under 3 cm before the brake.
        for grade in (-0.5, -1.0, -5.0):
            with self.subTest(grade=grade):
                rig = Rig(Plant(0.0, grade, LOADED_KG), 0.0)
                rig.plant.rolls_back = True
                rig.run(5.0)
                self.assertEqual(rig.plant.v, 0.0)
                rig.plant.engine_failed = True
                rig.core.state.commanded_mps = 10.0
                metres, free = self.roll(rig, self.TEST_S)
                self.assertEqual(rig.core.failed, ["engine"])
                self.assertTrue(rig.core.state.emergency_brake)
                self.assertEqual(rig.plant.v, 0.0)
                self.assertLess(metres, 0.03)
                self.assertEqual(free, 1)

    def test_one_tick_free_and_a_dead_engine_barely_moves(self) -> None:
        # Each test leaves the train with neither power nor a brake for
        # exactly one tick; a dead engine moves under 2 cm on any
        # grade, a working one is cleared.
        for grade in (-5.0, -0.5, 0.0, 0.5, 5.0):
            for dead in (True, False):
                with self.subTest(grade=grade, dead=dead):
                    rig = self.latched_at_a_stand(grade, LOADED_KG)
                    rig.plant.engine_failed = dead
                    self.assertTrue(rig.core.release_emergency())
                    metres, free = self.roll(rig, self.TEST_S)
                    self.assertEqual(free, 1)
                    if dead:
                        self.assertEqual(rig.core.failed, ["engine"])
                        self.assertLess(metres, 0.02)
                    else:
                        self.assertEqual(rig.core.failed, [])

    def test_a_slow_healthy_start_is_tested_once(self) -> None:
        # Heavy on 5 %: barely climbing. The departure is tested once,
        # and passes; the tests under way while it crawls pass too.
        # 111 passengers and the crew, as the Train Model has them.
        rig = Rig(Plant(0.0, 5.0, 40_900.0 + 116 * 77.1), 0.0)
        rig.plant.rolls_back = True
        tests, running = 0, False
        rig.core.state.commanded_mps = 10.0
        for _ in range(round(60.0 / TICK_S)):
            rig.tick()
            now = bool(rig.core._engine_test)
            tests += now and not running and rig.core.at_stand
            running = now
        self.assertEqual(rig.core.failed, [])
        self.assertLessEqual(tests, 1)

    def test_it_runs_in_manual_without_a_speed_set(self) -> None:
        rig = self.latched_at_a_stand()
        rig.core.state.manual = True
        rig.plant.engine_failed = False
        self.assertTrue(rig.core.release_emergency())
        rig.run(self.TEST_S)
        self.assertEqual(rig.core.failed, [])

    def test_the_emergency_brake_abandons_it(self) -> None:
        rig = self.latched_at_a_stand()
        rig.plant.engine_failed = False
        self.assertTrue(rig.core.release_emergency())
        rig.run(0.1)
        rig.core.engage_emergency()
        rig.run(self.TEST_S)
        self.assertEqual(rig.core.failed, ["engine"])
        # The next release tries again.
        rig.run(5.0)
        self.assertTrue(rig.core.release_emergency())
        rig.run(self.TEST_S)
        self.assertEqual(rig.core.failed, [])

    def test_no_power_without_authority(self) -> None:
        rig = self.latched_at_a_stand()
        rig.plant.engine_failed = False
        rig.core.state.authority_blocks = 0
        self.assertTrue(rig.core.release_emergency())
        for _ in range(round(self.TEST_S / TICK_S)):
            rig.tick()
            self.assertEqual(rig.core.state.power_w, 0.0)
        self.assertEqual(rig.core.failed, ["engine"])


class StopHoldTest(unittest.TestCase):
    """A target of 0 holds the train on the service brake, with no
    power: the integrator from the run does not creep it against the
    brake."""

    def test_a_zero_target_holds_without_power(self) -> None:
        for grade in (0.0, 5.0):
            with self.subTest(grade=grade):
                # Empty: a heavier train cannot climb 5 % at all.
                rig = Rig(Plant(0.0, grade, EMPTY_KG), 10.0)
                rig.plant.rolls_back = True
                rig.run(60.0)
                rig.core.state.commanded_mps = 0.0
                rig.run(20.0)
                for _ in range(round(30.0 / TICK_S)):
                    rig.tick()
                    self.assertEqual(rig.core.state.power_w, 0.0)
                    self.assertTrue(rig.core.state.service_brake)
                self.assertEqual(rig.plant.v, 0.0)
                # And drives off again when the target returns.
                rig.core.state.commanded_mps = 10.0
                rig.run(30.0)
                self.assertGreater(rig.plant.v, 1.0)


if __name__ == "__main__":
    unittest.main()
