"""Unit tests for ``TrainControllerState`` driver actions and the tick.

The state runs on the real Green Line layout: T-214 enters block 62
(section J, 30 km/h) with authority to the end of block 76. GLENBURY
(block 65) and DORMONT (block 73) both have right-side platforms.
"""

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


def _stop_in_block(state: TrainControllerState, block_id: str) -> None:
    """Drive to ``block_id`` and stop there with the emergency brake."""
    while state.current_block.block_id != block_id:
        state.step(1.0)
    state.pullEmergencyBrake()
    _run(state, 6)


class SeedTests(unittest.TestCase):

    def test_seed_is_real_green_line_track(self) -> None:
        snap = TrainControllerState().snapshot
        self.assertEqual(snap["line"], "Green Line")
        self.assertEqual(snap["current_block"], "62")
        self.assertEqual(snap["current_section"], "J")
        self.assertEqual(snap["next_block"], "63")
        self.assertEqual(snap["speed_limit_mph"], 19)
        self.assertEqual(snap["next_station"], "GLENBURY")
        self.assertEqual(snap["station_block"], "65")
        self.assertEqual(snap["platform_side"], "RIGHT")

    def test_authority_is_a_block_id(self) -> None:
        snap = TrainControllerState().snapshot
        self.assertEqual(snap["authority_block"], "76")
        self.assertIsInstance(snap["authority_block"], str)
        self.assertNotIn("authority_ft", snap)


class SpeedTargetTests(unittest.TestCase):

    def setUp(self) -> None:
        self.state = TrainControllerState()

    def test_faster_and_slower_step_one_mph(self) -> None:
        self.state.faster()
        self.assertEqual(self.state.snapshot["target_speed_mph"], 18)
        self.state.slower()
        self.state.slower()
        self.assertEqual(self.state.snapshot["target_speed_mph"], 16)

    def test_faster_clamps_below_block_speed_limit(self) -> None:
        for _ in range(30):
            self.state.faster()
        # Block 62 is 30 km/h = 18.6 mph; the target never rounds up.
        self.assertEqual(self.state.snapshot["target_speed_mph"], 18)

    def test_slower_clamps_at_zero(self) -> None:
        for _ in range(50):
            self.state.slower()
        self.assertEqual(self.state.snapshot["target_speed_mph"], 0)

    def test_use_ctc_target(self) -> None:
        self.state.slower()
        self.state.useCtcTarget()
        snap = self.state.snapshot
        self.assertEqual(snap["target_speed_mph"], 17)
        self.assertEqual(snap["target_set_by"], "CTC")

    def test_automatic_mode_locks_driver_speed(self) -> None:
        self.state.setMode("Automatic")
        self.state.faster()
        snap = self.state.snapshot
        self.assertEqual(snap["target_speed_mph"], 17)
        self.assertEqual(snap["target_set_by"], "CTC")


class BrakeTests(unittest.TestCase):

    def setUp(self) -> None:
        self.state = TrainControllerState()

    def test_service_brake_slows_the_train(self) -> None:
        self.state.setServiceBrake(True)
        _run(self.state, 3)
        self.assertLess(self.state.snapshot["current_speed_mph"], 15)

    def test_emergency_brake_cannot_be_released_while_moving(self) -> None:
        self.state.pullEmergencyBrake()
        self.state.step(1.0)
        self.assertFalse(
            self.state.snapshot["can_release_emergency_brake"])
        self.state.releaseEmergencyBrake()
        self.assertTrue(self.state.snapshot["emergency_brake"])

    def test_driver_releases_emergency_brake_once_stopped(self) -> None:
        self.state.pullEmergencyBrake()
        _run(self.state, 6)
        snap = self.state.snapshot
        self.assertEqual(snap["current_speed_mph"], 0)
        self.assertTrue(snap["can_release_emergency_brake"])

        self.state.releaseEmergencyBrake()
        _run(self.state, 3)
        snap = self.state.snapshot
        self.assertFalse(snap["emergency_brake"])
        self.assertGreater(snap["current_speed_mph"], 0)

    def test_emergency_stops_faster_than_service(self) -> None:
        service = TrainControllerState()
        service.setServiceBrake(True)
        self.state.pullEmergencyBrake()
        _run(service, 2)
        _run(self.state, 2)
        self.assertLess(self.state.current_speed_mps,
                        service.current_speed_mps)


class TickTests(unittest.TestCase):

    def setUp(self) -> None:
        self.state = TrainControllerState()

    def test_speed_eases_toward_target(self) -> None:
        _run(self.state, 5)
        self.assertEqual(self.state.snapshot["current_speed_mph"], 17)

    def test_distances_count_down(self) -> None:
        before_ft = self.state.snapshot["station_distance_ft"]
        _run(self.state, 5)
        self.assertLess(self.state.snapshot["station_distance_ft"],
                        before_ft)

    def test_train_advances_through_blocks(self) -> None:
        _run(self.state, 10)
        snap = self.state.snapshot
        self.assertEqual(snap["current_block"], "63")
        self.assertEqual(snap["blocks"][-1]["block_id"], "63")
        self.assertEqual(snap["blocks"][-1]["occupancy"], "occupied")

    def test_speed_limit_follows_the_occupied_block(self) -> None:
        _run(self.state, 10)
        # Block 63 is 70 km/h = 43.5 mph.
        self.assertEqual(self.state.snapshot["speed_limit_mph"], 43)

    def test_train_stops_at_end_of_authority_block(self) -> None:
        _run(self.state, 600)
        snap = self.state.snapshot
        self.assertEqual(snap["current_speed_mph"], 0)
        self.assertEqual(snap["current_block"], "76")
        self.assertLess(self.state.authority_left_m, 15)

    def test_authority_block_is_flagged_on_the_strip(self) -> None:
        _run(self.state, 600)
        tiles = self.state.snapshot["blocks"]
        self.assertEqual(
            [tile["block_id"] for tile in tiles if tile["is_authority"]],
            ["76"],
        )

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
        self.state.toggleRightDoor()
        self.assertFalse(self.state.snapshot["right_door"])

    def test_doors_stay_shut_away_from_a_platform(self) -> None:
        self.state.pullEmergencyBrake()
        _run(self.state, 6)
        self.state.toggleRightDoor()
        self.assertFalse(self.state.snapshot["right_door"])

    def test_platform_side_door_opens_at_station(self) -> None:
        _stop_in_block(self.state, "65")
        self.state.toggleLeftDoor()
        self.state.toggleRightDoor()
        snap = self.state.snapshot
        self.assertFalse(snap["left_door"])
        self.assertTrue(snap["right_door"])

    def test_open_doors_hold_the_train(self) -> None:
        _stop_in_block(self.state, "65")
        self.state.toggleRightDoor()
        self.state.releaseEmergencyBrake()
        _run(self.state, 5)
        self.assertEqual(self.state.snapshot["current_speed_mph"], 0)


class AutomaticStationStopTests(unittest.TestCase):

    def setUp(self) -> None:
        self.state = TrainControllerState()
        self.state.setMode("Automatic")

    def _run_until_dwell(self) -> int:
        for second in range(300):
            self.state.step(1.0)
            if self.state.is_dwelling:
                return second
        self.fail("train never started a station dwell")

    def test_stops_at_station_and_opens_platform_doors(self) -> None:
        self._run_until_dwell()
        snap = self.state.snapshot
        self.assertEqual(snap["current_block"], "65")
        self.assertEqual(snap["current_speed_mph"], 0)
        self.assertTrue(snap["right_door"])
        self.assertFalse(snap["left_door"])
        self.assertEqual(snap["dwell_left_s"], 45)

    def test_dwell_is_45_s_including_door_close(self) -> None:
        self._run_until_dwell()
        _run(self.state, 39)
        self.assertTrue(self.state.right_door_open)
        _run(self.state, 2)
        self.assertFalse(self.state.right_door_open)
        self.assertEqual(self.state.current_speed_mps, 0)
        _run(self.state, 4)
        self.assertFalse(self.state.is_dwelling)
        _run(self.state, 2)
        self.assertGreater(self.state.current_speed_mps, 0)

    def test_departs_and_stops_at_next_station(self) -> None:
        self._run_until_dwell()
        _run(self.state, 46)
        self._run_until_dwell()
        self.assertEqual(self.state.snapshot["current_block"], "73")

    def test_driver_cannot_operate_doors_in_automatic(self) -> None:
        self._run_until_dwell()
        self.state.toggleRightDoor()
        self.assertTrue(self.state.right_door_open)
        snap = self.state.snapshot
        self.assertFalse(snap["can_open_left"])
        self.assertFalse(snap["can_open_right"])

    def test_switching_to_manual_ends_the_dwell(self) -> None:
        self._run_until_dwell()
        self.state.setMode("Manual")
        self.assertFalse(self.state.is_dwelling)
        self.state.toggleRightDoor()
        self.assertFalse(self.state.right_door_open)

    def test_manual_mode_does_not_stop_at_stations(self) -> None:
        manual = TrainControllerState()
        _run(manual, 60)
        self.assertFalse(manual.is_dwelling)
        self.assertGreater(manual.current_speed_mps, 0)


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

    def test_announcement_names_station_and_side(self) -> None:
        self.state.announceAgain()
        self.assertEqual(
            self.state.snapshot["announcement"],
            "Next stop GLENBURY. Doors open on the right.",
        )
        _run(self.state, 6)
        self.assertEqual(self.state.snapshot["announcement"], "")


class SignalAspectTests(unittest.TestCase):

    def setUp(self) -> None:
        self.state = TrainControllerState()

    def test_seed_aspect_is_a_placeholder(self) -> None:
        snap = self.state.snapshot
        self.assertEqual(snap["signal_aspect"], "GREEN")
        self.assertEqual(snap["signal_aspect_source"], "placeholder")

    def test_track_model_aspect_replaces_placeholder(self) -> None:
        self.state.receive_signal_aspect("SUPER GREEN")
        snap = self.state.snapshot
        self.assertEqual(snap["signal_aspect"], "SUPER GREEN")
        self.assertEqual(snap["signal_aspect_source"], "track_model")

    def test_unknown_aspect_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.state.receive_signal_aspect("BLUE")

    def test_aspect_is_display_only(self) -> None:
        green = TrainControllerState()
        self.state.receive_signal_aspect("RED")
        _run(green, 20)
        _run(self.state, 20)
        self.assertEqual(self.state.current_speed_mps,
                         green.current_speed_mps)
        self.assertEqual(self.state.distance_travelled_m,
                         green.distance_travelled_m)

    def test_driver_ui_cannot_set_the_aspect(self) -> None:
        meta = self.state.metaObject()
        self.assertEqual(
            meta.indexOfMethod("receive_signal_aspect(QString)"), -1)


class GainTests(unittest.TestCase):

    def setUp(self) -> None:
        self.state = TrainControllerState()

    def test_driver_cannot_change_gains(self) -> None:
        self.state.adjustKp(1)
        self.state.setKi(5.0)
        self.state.applyGains()
        snap = self.state.snapshot
        self.assertEqual(snap["kp"], 12.4)
        self.assertEqual(snap["ki"], 0.85)

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

    def test_engineer_types_a_gain(self) -> None:
        self.state.setUser("Engineer")
        self.state.setKp(9.87654)
        self.assertEqual(self.state.snapshot["kp"], 9.877)

    def test_gains_never_go_negative(self) -> None:
        self.state.setUser("Engineer")
        self.state.setGainStep(1.0)
        self.state.adjustKi(-1)
        self.state.setKp(-3.0)
        snap = self.state.snapshot
        self.assertEqual(snap["ki"], 0.0)
        self.assertEqual(snap["kp"], 0.0)


if __name__ == "__main__":
    unittest.main()
