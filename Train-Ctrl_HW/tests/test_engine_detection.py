"""Engine failure detection and resolution against a Train Model
style plant.

The rules (Kevin Schillinger, 2026-10-21): never flag a train that is
holding its target; flag on speed falling, not on speed failing to
rise, with power commanded and no brake applied anywhere in the
window; and use a window a few seconds longer than the old 2 s.
Resolution: the driver tries the train once the emergency brake is
released (OPEN_ISSUES.md #23, option a).

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
from pathlib import Path

_HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_HERE))
sys.path.insert(1, str(_HERE.parent))

from train_ctrl import ECHO_TICKS, TICK_S  # noqa: E402
from train_ctrl.constants import (  # noqa: E402
    EBRAKE_DECEL_MPS2,
    ENGINE_DETECT_S,
    ENGINE_TRY_S,
    GRAVITY_MPS2,
    MASS_KG,
    MAX_FORCE_N,
    ROLLING_RESISTANCE_COEFF,
    SERVICE_BAND_MPS,
    SERVICE_DECEL_MPS2,
)
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

    def test_steady_out_of_band_speed_does_not_latch(self) -> None:
        # Below target and not falling (say, power-limited on a
        # climb): not rising is not a failure.
        rig = Rig(Plant(5.0, 0.0), 8.0)
        for _ in range(round(30.0 / TICK_S)):
            rig.tick(5.0)
        self.assertGreater(rig.core.state.power_w, 0.0)
        self.assertEqual(rig.core.failed, [])


class EngineTryTest(unittest.TestCase):
    """The driver tries the train to see a failed engine repaired."""

    def latched_at_a_stand(self, grade: float = 0.0) -> Rig:
        """An engine failure detected, the train stopped on it."""
        rig = Rig(Plant(0.0, grade), 10.0)
        rig.run(60.0)
        rig.plant.engine_failed = True
        self.assertIsNotNone(rig.run_until_failed(ENGINE_DETECT_S + 0.5))
        rig.run(10.0)
        self.assertEqual(rig.plant.v, 0.0)
        self.assertTrue(rig.core.state.emergency_brake)
        return rig

    def test_a_repaired_engine_resolves_when_tried(self) -> None:
        rig = self.latched_at_a_stand()
        rig.plant.engine_failed = False
        rig.run(5.0)
        self.assertEqual(rig.core.failed, ["engine"],
                         "resolved before the driver tried the train")
        self.assertTrue(rig.core.release_emergency())
        rig.run(ENGINE_TRY_S)
        self.assertEqual(rig.core.failed, [])
        rig.run(30.0)
        self.assertGreater(rig.plant.v, 5.0)

    def test_a_dead_engine_stays_latched_and_is_held(self) -> None:
        rig = self.latched_at_a_stand()
        self.assertTrue(rig.core.release_emergency())
        rig.run(ENGINE_TRY_S + 1.0)
        s = rig.core.state
        self.assertEqual(rig.core.failed, ["engine"])
        self.assertEqual((s.power_w, s.target_mps), (0.0, 0.0))
        self.assertTrue(s.service_brake)
        self.assertFalse(s.emergency_brake)

    def test_only_seconds_under_power_count(self) -> None:
        # In Manual the try waits for the driver to set a speed.
        rig = self.latched_at_a_stand()
        rig.core.state.manual = True
        rig.plant.engine_failed = False
        self.assertTrue(rig.core.release_emergency())
        rig.run(20.0)
        self.assertEqual(rig.core.failed, ["engine"])
        rig.core.set_target_mps(5.0)
        rig.run(ENGINE_TRY_S)
        self.assertEqual(rig.core.failed, [])

    def test_a_dead_engine_rolling_back_is_held(self) -> None:
        rig = self.latched_at_a_stand(grade=2.0)
        rig.plant.rolls_back = True
        self.assertTrue(rig.core.release_emergency())
        rig.run(20.0)
        self.assertEqual(rig.core.failed, ["engine"])
        self.assertTrue(rig.core.state.service_brake)
        self.assertGreater(rig.plant.v, -0.5)
        self.assertEqual(rig.plant.v, 0.0)


if __name__ == "__main__":
    unittest.main()
