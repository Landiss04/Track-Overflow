"""Unit tests for ``TrainControllerState`` driver actions and the tick."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QCoreApplication  # noqa: E402

from train_controller.train_controller_state import (  # noqa: E402
    TrainControllerState,
)

_APP = QCoreApplication.instance() or QCoreApplication([])


def _run(state: TrainControllerState, seconds: int) -> None:
    for _ in range(seconds):
        state.step(1.0)


class SpeedTargetTests(unittest.TestCase):

    def setUp(self) -> None:
        self.state = TrainControllerState()

    def test_seed_matches_wireframe(self) -> None:
        snap = self.state.snapshot
        self.assertEqual(snap["current_speed_mph"], 32)
        self.assertEqual(snap["speed_limit_mph"], 45)
        self.assertEqual(snap["target_speed_mph"], 35)
        self.assertEqual(snap["authority_ft"], 10032)
        self.assertEqual(snap["current_block"], "GREEN I")
        self.assertEqual(snap["next_block"], "GREEN J")

    def test_faster_and_slower_step_one_mph(self) -> None:
        self.state.faster()
        self.assertEqual(self.state.snapshot["target_speed_mph"], 36)
        self.state.slower()
        self.state.slower()
        self.assertEqual(self.state.snapshot["target_speed_mph"], 34)

    def test_faster_clamps_at_speed_limit(self) -> None:
        for _ in range(30):
            self.state.faster()
        self.assertEqual(self.state.snapshot["target_speed_mph"], 45)

    def test_slower_clamps_at_zero(self) -> None:
        for _ in range(50):
            self.state.slower()
        self.assertEqual(self.state.snapshot["target_speed_mph"], 0)

    def test_use_ctc_target(self) -> None:
        self.state.faster()
        self.state.useCtcTarget()
        snap = self.state.snapshot
        self.assertEqual(snap["target_speed_mph"], 35)
        self.assertEqual(snap["target_set_by"], "CTC")

    def test_automatic_mode_locks_driver_speed(self) -> None:
        self.state.setMode("Automatic")
        self.state.faster()
        snap = self.state.snapshot
        self.assertEqual(snap["target_speed_mph"], 35)
        self.assertEqual(snap["target_set_by"], "CTC")


class BrakeTests(unittest.TestCase):

    def setUp(self) -> None:
        self.state = TrainControllerState()

    def test_service_brake_slows_the_train(self) -> None:
        self.state.setServiceBrake(True)
        _run(self.state, 3)
        self.assertLess(self.state.snapshot["current_speed_mph"], 32)

    def test_emergency_brake_latches_until_office_release(self) -> None:
        self.state.pullEmergencyBrake()
        _run(self.state, 10)
        snap = self.state.snapshot
        self.assertTrue(snap["emergency_brake"])
        self.assertEqual(snap["current_speed_mph"], 0)

        self.state.simulateOfficeRelease()
        _run(self.state, 3)
        self.assertFalse(self.state.snapshot["emergency_brake"])
        self.assertGreater(self.state.snapshot["current_speed_mph"], 0)

    def test_emergency_stops_faster_than_service(self) -> None:
        service = TrainControllerState()
        service.setServiceBrake(True)
        self.state.pullEmergencyBrake()
        _run(service, 3)
        _run(self.state, 3)
        self.assertLess(self.state.current_speed_mps,
                        service.current_speed_mps)


class TickTests(unittest.TestCase):

    def setUp(self) -> None:
        self.state = TrainControllerState()

    def test_speed_eases_toward_target(self) -> None:
        _run(self.state, 10)
        self.assertEqual(self.state.snapshot["current_speed_mph"], 35)

    def test_distances_count_down(self) -> None:
        _run(self.state, 5)
        snap = self.state.snapshot
        self.assertLess(snap["authority_ft"], 10032)
        self.assertLess(snap["station_distance_ft"], 4224)

    def test_train_advances_through_blocks(self) -> None:
        _run(self.state, 30)
        snap = self.state.snapshot
        self.assertEqual(snap["current_block"], "GREEN J")
        self.assertEqual(snap["blocks"][-1]["block_id"], "GREEN J")
        self.assertEqual(snap["blocks"][-1]["state"], "current")

    def test_train_stops_at_end_of_authority(self) -> None:
        _run(self.state, 600)
        snap = self.state.snapshot
        self.assertEqual(snap["current_speed_mph"], 0)
        self.assertLess(snap["authority_ft"], 50)

    def test_clock_advances(self) -> None:
        _run(self.state, 25)
        self.assertEqual(self.state.snapshot["clock"], "21:27:00")

    def test_cabin_temperature_drifts_to_setpoint(self) -> None:
        _run(self.state, 60)
        self.assertEqual(self.state.snapshot["cabin_temp_f"], 68)


class DoorTests(unittest.TestCase):

    def setUp(self) -> None:
        self.state = TrainControllerState()

    def test_doors_stay_shut_while_moving(self) -> None:
        self.state.toggleLeftDoor()
        self.assertFalse(self.state.snapshot["left_door"])

    def test_platform_side_door_opens_when_stopped(self) -> None:
        self.state.pullEmergencyBrake()
        _run(self.state, 10)
        self.state.toggleLeftDoor()
        self.state.toggleRightDoor()
        snap = self.state.snapshot
        self.assertTrue(snap["left_door"])
        self.assertFalse(snap["right_door"])

    def test_open_doors_hold_the_train(self) -> None:
        self.state.pullEmergencyBrake()
        _run(self.state, 10)
        self.state.toggleLeftDoor()
        self.state.simulateOfficeRelease()
        _run(self.state, 5)
        self.assertEqual(self.state.snapshot["current_speed_mph"], 0)


class ComfortTests(unittest.TestCase):

    def setUp(self) -> None:
        self.state = TrainControllerState()

    def test_temperature_setpoint_clamps(self) -> None:
        for _ in range(30):
            self.state.warmer()
        self.assertEqual(self.state.snapshot["temp_setpoint_f"], 80)
        for _ in range(30):
            self.state.cooler()
        self.assertEqual(self.state.snapshot["temp_setpoint_f"], 60)

    def test_lights_toggle(self) -> None:
        self.state.setCabinLight(False)
        self.state.setHeadlight(False)
        snap = self.state.snapshot
        self.assertFalse(snap["cabin_light"])
        self.assertFalse(snap["headlight"])

    def test_announcement_expires(self) -> None:
        self.state.announceAgain()
        self.assertIn("[STATION]", self.state.snapshot["announcement"])
        _run(self.state, 6)
        self.assertEqual(self.state.snapshot["announcement"], "")


class GainTests(unittest.TestCase):

    def setUp(self) -> None:
        self.state = TrainControllerState()

    def test_driver_cannot_change_gains(self) -> None:
        self.state.adjustKp(1)
        self.state.applyGains()
        self.assertEqual(self.state.snapshot["kp"], 12.4)

    def test_engineer_adjusts_and_applies(self) -> None:
        self.state.setUser("Engineer")
        self.state.setGainStep(0.1)
        self.state.adjustKp(1)
        self.state.adjustKi(-1)
        snap = self.state.snapshot
        self.assertAlmostEqual(snap["kp"], 12.5)
        self.assertAlmostEqual(snap["ki"], 0.75)
        self.assertEqual(snap["kp_in_use"], 12.4)

        self.state.applyGains()
        snap = self.state.snapshot
        self.assertAlmostEqual(snap["kp_in_use"], 12.5)
        self.assertAlmostEqual(snap["ki_in_use"], 0.75)

    def test_gains_never_go_negative(self) -> None:
        self.state.setUser("Engineer")
        self.state.setGainStep(1.0)
        self.state.adjustKi(-1)
        self.assertEqual(self.state.snapshot["ki"], 0.0)


if __name__ == "__main__":
    unittest.main()
