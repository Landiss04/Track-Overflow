"""The Train Model and Train Controller in a loop, through the edges.

The harness's tick, in one process and without sockets: on each tick
both module processes step on the outputs every module gave on the
tick before, mapped by ``SystemEdges``, just as the harness does it
across processes. This runs each module's own code, so it checks the
loop itself: one train released by the CTC Office, driven by its
controller over a fixed track feed, stopping at a station behind the
door interlock, and the emergency brake released by the driver, with
and without a passenger pull.

Run from the repository root with
``python -m unittest discover -s common/harness/tests``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
for _folder in (_REPO, _REPO / "TrainModel", _REPO / "Train-Ctrl_HW"):
    if str(_folder) not in sys.path:
        sys.path.insert(0, str(_folder))

from PySide6.QtCore import QCoreApplication  # noqa: E402

from common.harness.edges import SystemEdges  # noqa: E402
from common.harness.modules import (  # noqa: E402
    CTC_OFFICE,
    TRAIN_CONTROLLER_SW,
    TRAIN_MODEL,
)
from common.harness.track_feed import (  # noqa: E402
    FeedBeacon,
    FeedSegment,
    FixedTrackFeed,
)
from train_ctrl import ECHO_TICKS, TrainControllerFleet  # noqa: E402
from train_ctrl.module_process import TrainControllerProcess  # noqa: E402
from train_model.fleet import TrainModelFleet  # noqa: E402
from train_model.module_process import TrainModelProcess  # noqa: E402

_APP = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])

DT_S = 0.1
START_S = 18_000.0
KP, KI = 400_000.0, 8_000.0
STANDSTILL_MPS = 0.1
LIMIT_MPS = 19.4

#: Out of block 63, a stop at GLENBURY with the platform on the right,
#: and on again: authority counts down to the stop.
STATION_STOP = (
    FeedSegment(0.0, "63", 10.0, 3, LIMIT_MPS),
    FeedSegment(15.0, "64", 10.0, 2, LIMIT_MPS),
    FeedSegment(22.0, "65", 10.0, 1, LIMIT_MPS, station_name="GLENBURY",
                beacon=FeedBeacon("GLENBURY", "R")),
    FeedSegment(25.0, "65", 0.0, 0, LIMIT_MPS, station_name="GLENBURY",
                aspect_ahead="RED"),
    FeedSegment(45.0, "65", 10.0, 3, LIMIT_MPS, station_name="GLENBURY"),
)

#: Running on, with no stop.
OPEN_LINE = (FeedSegment(0.0, "63", 10.0, 5, LIMIT_MPS),)


class _Loop:
    """The harness's tick for the two wired modules, in one process."""

    def __init__(self, script: tuple[FeedSegment, ...]) -> None:
        self.edges = SystemEdges(FixedTrackFeed(script))
        self.model_fleet = TrainModelFleet()
        self.model = TrainModelProcess(
            self.model_fleet, "unused", parent=self.model_fleet
        )
        self.controller_fleet = TrainControllerFleet(echo_ticks=ECHO_TICKS)
        self.controller = TrainControllerProcess(
            self.controller_fleet, TRAIN_CONTROLLER_SW, "unused",
            engineer_gains=(KP, KI),
        )
        self.outputs: dict[str, Any] = {}
        self.tick = 0
        # The CTC Office released G1 on the tick before the first.
        self.edges.tick_completed(0, START_S, {CTC_OFFICE: {
            "new_trains": [{"train_id": "G1", "line": "Green"}],
        }})

    def step(self) -> None:
        """One tick: both modules step on the last tick's outputs."""
        self.tick += 1
        sim_time_s = START_S + self.tick * DT_S
        fresh = {}
        for name, process in (
            (TRAIN_MODEL, self.model),
            (TRAIN_CONTROLLER_SW, self.controller),
        ):
            inputs = self.edges.inputs_for(
                name, self.tick, sim_time_s, self.outputs
            )
            fresh[name] = process.step(self.tick, DT_S, sim_time_s, inputs)
        self.outputs.update(fresh)
        self.edges.tick_completed(self.tick, sim_time_s, fresh)

    def run_until(self, condition, limit_s: float = 120.0) -> bool:
        """Step until ``condition()`` holds, for at most ``limit_s``."""
        for _ in range(round(limit_s / DT_S)):
            self.step()
            if condition():
                return True
        return False

    @property
    def report(self) -> dict[str, Any]:
        """G1's Train Model ``controller`` outputs, as last reported."""
        return self.outputs[TRAIN_MODEL]["trains"]["G1"]["controller"]

    @property
    def commands(self) -> dict[str, Any]:
        """G1's Train Controller commands, as last sent."""
        return self.outputs[TRAIN_CONTROLLER_SW]["trains"]["G1"]

    @property
    def speed_mps(self) -> float:
        """G1's speed, as the Train Model last reported it."""
        return self.report["actual_speed_mps"]


class StationStopTest(unittest.TestCase):
    """The train stops at the station behind the door interlock."""

    @classmethod
    def setUpClass(cls) -> None:
        loop = _Loop(STATION_STOP)
        cls.trace = []
        for _ in range(round(60.0 / DT_S)):
            loop.step()
            if TRAIN_CONTROLLER_SW in loop.outputs and loop.outputs[
                TRAIN_CONTROLLER_SW
            ]["trains"]:
                cls.trace.append((loop.tick, dict(loop.report),
                                  dict(loop.commands)))

    def test_the_controller_joins_a_tick_after_the_model(self) -> None:
        self.assertEqual(self.trace[0][0], 2)

    def test_the_train_reaches_its_commanded_speed(self) -> None:
        top = max(report["actual_speed_mps"] for _, report, _ in self.trace)
        self.assertAlmostEqual(top, 10.0, delta=0.2)

    def test_doors_open_only_at_a_stand_on_the_platform_side(self) -> None:
        opened = [
            (tick, report) for tick, report, _ in self.trace
            if report["door_left_open"] or report["door_right_open"]
        ]
        self.assertTrue(opened, "the doors never opened at the station")
        for _, report in opened:
            self.assertFalse(report["door_left_open"])
            self.assertLess(abs(report["actual_speed_mps"]), STANDSTILL_MPS)

    def test_no_power_while_a_door_is_open(self) -> None:
        for _, report, commands in self.trace:
            if report["door_left_open"] or report["door_right_open"]:
                self.assertEqual(commands["power_w"], 0.0)

    def test_doors_close_before_the_train_moves_off(self) -> None:
        first_open = next(
            tick for tick, report, _ in self.trace
            if report["door_right_open"]
        )
        departing = [
            (tick, report) for tick, report, _ in self.trace
            if tick > first_open and report["actual_speed_mps"] > 0.0
        ]
        self.assertTrue(departing, "the train never moved off")
        self.assertFalse(departing[0][1]["door_right_open"])
        self.assertGreater(self.trace[-1][1]["actual_speed_mps"], 1.0)


class EmergencyBrakeTest(unittest.TestCase):
    """The driver's release holds, and releases a passenger pull."""

    def setUp(self) -> None:
        self.loop = _Loop(OPEN_LINE)
        self.assertTrue(self.loop.run_until(lambda: self.loop.speed_mps > 5))
        self.core = self.loop.controller_fleet.get("G1")

    def stop_and_release(self) -> None:
        """Wait for a stand, then release as the driver."""
        self.assertTrue(self.core.state.emergency_brake)
        self.assertTrue(self.loop.run_until(
            lambda: self.core.release_emergency()
        ))

    def test_driver_release_is_not_undone(self) -> None:
        self.core.engage_emergency()
        self.stop_and_release()
        for _ in range(4 * ECHO_TICKS):
            self.loop.step()
            self.assertFalse(self.core.state.emergency_brake)
        self.assertTrue(self.loop.run_until(lambda: self.loop.speed_mps > 1))

    def test_passenger_pull_and_release(self) -> None:
        self.loop.model_fleet.get("G1").applyEmergencyBrake()
        self.assertTrue(self.loop.run_until(
            lambda: self.core.state.emergency_brake, limit_s=3 * DT_S
        ))
        self.stop_and_release()
        self.loop.step()
        self.assertTrue(self.loop.commands["passenger_brake_release"])
        self.loop.step()
        self.assertFalse(self.loop.report["emergency_brake_active"])
        self.assertFalse(self.core.state.emergency_brake)
        self.assertTrue(self.loop.run_until(lambda: self.loop.speed_mps > 1))


if __name__ == "__main__":
    unittest.main()
