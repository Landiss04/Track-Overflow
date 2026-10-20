"""The Track Model, Train Model and Train Controller in a loop.

The harness's tick, in one process and without sockets: on each tick
the three wired module processes step on the outputs every module gave
on the tick before, mapped by ``SystemEdges``, just as the harness does
it across processes. Every input and output goes through JSON on the
way, as it would between processes. This runs each module's own code,
so it checks the loop itself: one train released by the CTC Office,
placed by the Track Model at the yard exit block, driven by its
controller block by block on the scripted wayside's commands, stopping
at GLENBURY behind the door interlock and at DORMONT at the end of its
route; and the emergency brake released by the driver, with and
without a passenger pull.

Run from the repository root with
``python -m unittest discover -s common/harness/tests``.
"""

from __future__ import annotations

import json
import sys
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
for _folder in (
    _REPO, _REPO / "TrackModel", _REPO / "TrainModel", _REPO / "Train-Ctrl_HW"
):
    if str(_folder) not in sys.path:
        sys.path.insert(0, str(_folder))

from PySide6.QtCore import QCoreApplication  # noqa: E402

from common.harness.edges import SystemEdges  # noqa: E402
from common.harness.modules import (  # noqa: E402
    CTC_OFFICE,
    TRACK_MODEL,
    TRAIN_CONTROLLER_SW,
    TRAIN_MODEL,
)
from common.harness.roster import Event  # noqa: E402
from common.harness.wayside_script import (  # noqa: E402
    GREEN_YARD_TO_DORMONT,
    RouteBlock,
    ScriptedWayside,
    WaysideRoute,
)
from track_model.interface import TrackConfig  # noqa: E402
from track_model.model import TrackModel  # noqa: E402
from track_model.module_process import (  # noqa: E402
    TrackModelProcess,
    layout_paths,
)
from track_model.state import TrackModelState  # noqa: E402
from train_ctrl import ECHO_TICKS, TrainControllerFleet  # noqa: E402
from train_ctrl.module_process import TrainControllerProcess  # noqa: E402
from train_model.fleet import TrainModelFleet  # noqa: E402
from train_model.module_process import TrainModelProcess  # noqa: E402

_APP = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])

DT_S = 0.1
START_S = 18_000.0
KP, KI = 400_000.0, 8_000.0
STANDSTILL_MPS = 0.1

#: The default route's blocks, in order.
ROUTE = [block.block_id for block in GREEN_YARD_TO_DORMONT.blocks]
GLENBURY, DORMONT = "65", "73"

#: Eleven blocks at 10 m/s with no stop before the last.
OPEN_LINE = WaysideRoute(
    "Green", tuple(RouteBlock(str(n), 10.0) for n in range(63, 74))
)

#: A stop at GLENBURY whose authority comes back 15 s after the train
#: enters: once it stands, but well before the dwell is over, which the
#: Train Controller enforces.
EARLY_RESUME = WaysideRoute("Green", (
    RouteBlock("63", 10.0),
    RouteBlock("64", 10.0),
    RouteBlock(GLENBURY, 10.0, hold_s=15.0),
    RouteBlock("66", 10.0),
    RouteBlock("67", 10.0),
))

#: Truth D007: the CTC Office schedules the dwell; the Train Controller
#: enforces it.
DWELL_S = 45.0


def _wire(value: Any) -> Any:
    # Through JSON and back, as across a process boundary.
    return json.loads(json.dumps(value))


class _Loop:
    """The harness's tick for the three wired modules, in one process."""

    def __init__(self, route: WaysideRoute) -> None:
        self.edges = SystemEdges(ScriptedWayside(route))
        self.track = TrackModel(TrackConfig(layout_paths()))
        self.track_state = TrackModelState(self.track)
        self.track_model = TrackModelProcess(
            self.track, self.track_state, "unused", parent=self.track_state
        )
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
        self.events: list[Event] = []
        self.tick = 0
        # The CTC Office released G1 on the tick before the first.
        self.edges.tick_completed(0, START_S, {CTC_OFFICE: {
            "new_trains": [{"train_id": "G1", "line": "Green"}],
        }})

    def step(self) -> None:
        """One tick: every module steps on the last tick's outputs."""
        self.tick += 1
        sim_time_s = START_S + self.tick * DT_S
        fresh = {}
        for name, process in (
            (TRACK_MODEL, self.track_model),
            (TRAIN_MODEL, self.model),
            (TRAIN_CONTROLLER_SW, self.controller),
        ):
            inputs = _wire(self.edges.inputs_for(
                name, self.tick, sim_time_s, self.outputs
            ))
            fresh[name] = _wire(
                process.step(self.tick, DT_S, sim_time_s, inputs)
            )
        self.outputs.update(fresh)
        self.events += self.edges.tick_completed(
            self.tick, sim_time_s, fresh
        )

    def run_until(
        self, condition: Callable[[], bool], limit_s: float = 120.0
    ) -> bool:
        """Step until ``condition()`` holds, for at most ``limit_s``."""
        for _ in range(round(limit_s / DT_S)):
            self.step()
            if condition():
                return True
        return False

    def has(self, module: str) -> bool:
        """Whether ``module``'s last outputs name G1."""
        key = "train_feeds" if module == TRACK_MODEL else "trains"
        return "G1" in self.outputs.get(module, {}).get(key, {})

    @property
    def report(self) -> dict[str, Any]:
        """G1's Train Model ``controller`` outputs, as last reported."""
        return self.outputs[TRAIN_MODEL]["trains"]["G1"]["controller"]

    @property
    def block(self) -> str:
        """The block G1's Train Model last reported."""
        return self.outputs[TRAIN_MODEL]["trains"]["G1"]["track"]["block_id"]

    @property
    def feed(self) -> dict[str, Any]:
        """G1's Track Model feed, as last sent."""
        return self.outputs[TRACK_MODEL]["train_feeds"]["G1"]

    @property
    def commands(self) -> dict[str, Any]:
        """G1's Train Controller commands, as last sent."""
        return self.outputs[TRAIN_CONTROLLER_SW]["trains"]["G1"]

    @property
    def speed_mps(self) -> float:
        """G1's speed, as the Train Model last reported it."""
        return self.report["actual_speed_mps"]


class StationStopTest(unittest.TestCase):
    """The default route: out of the yard, GLENBURY, then DORMONT."""

    loop: _Loop
    core: Any
    # The tick each module first named G1.
    joined: dict[str, int]
    # Per tick once all three have G1: the block the Train Model
    # reports, its controller outputs, the commands, and the feed.
    trace: list[tuple[int, str, dict[str, Any], dict[str, Any],
                      dict[str, Any]]]

    @classmethod
    def setUpClass(cls) -> None:
        loop = _Loop(GREEN_YARD_TO_DORMONT)
        cls.loop = loop
        cls.joined = {}
        cls.trace = []

        def at_rest_at_dormont() -> bool:
            for module in (TRACK_MODEL, TRAIN_MODEL, TRAIN_CONTROLLER_SW):
                if loop.has(module):
                    cls.joined.setdefault(module, loop.tick)
            if len(cls.joined) < 3:
                return False
            cls.trace.append((loop.tick, loop.block, loop.report,
                              loop.commands, loop.feed))
            return (
                loop.block == DORMONT
                and abs(loop.speed_mps) < STANDSTILL_MPS
                and loop.report["door_right_open"]
            )

        if not loop.run_until(at_rest_at_dormont, limit_s=400.0):
            raise AssertionError(
                f"G1 never came to rest at DORMONT: at tick {loop.tick} "
                f"it was in block {loop.block}"
            )
        cls.core = loop.controller_fleet.get("G1")

    def at(
        self, block: str
    ) -> list[tuple[int, dict[str, Any], dict[str, Any]]]:
        """The ticks G1 reported ``block``: report and commands."""
        return [
            (tick, report, commands)
            for tick, here, report, commands, _ in self.trace
            if here == block
        ]

    def test_each_module_takes_the_train_in_turn(self) -> None:
        # Placed by the Track Model, then fed to the Train Model, then
        # reported to the Train Controller: a tick apart each.
        self.assertEqual(self.joined, {
            TRACK_MODEL: 2, TRAIN_MODEL: 3, TRAIN_CONTROLLER_SW: 4,
        })

    def test_the_train_runs_block_by_block(self) -> None:
        blocks: list[str] = []
        for _, here, *_ in self.trace:
            if not blocks or blocks[-1] != here:
                blocks.append(here)
        self.assertEqual(blocks, ROUTE)

    def test_authority_never_falls_from_two_blocks_to_none(self) -> None:
        # The Train Controller would read that as a pickup failure.
        authority = [report["authority_blocks"]
                     for _, _, report, _, _ in self.trace]
        for before, after in zip(authority, authority[1:]):
            if after == 0 and before:
                self.assertLess(before, 2)
        self.assertFalse(self.core.state.failures["signal_pickup"])
        self.assertFalse(self.core.state.emergency_brake)

    def test_the_train_reaches_its_commanded_speed(self) -> None:
        top = max(report["actual_speed_mps"] for _, _, report, _, _ in
                  self.trace)
        self.assertAlmostEqual(top, 45 / 3.6, delta=0.3)

    def test_doors_open_only_at_a_stand_on_the_platform_side(self) -> None:
        opened = [
            (here, report) for _, here, report, _, _ in self.trace
            if report["door_left_open"] or report["door_right_open"]
        ]
        self.assertEqual({here for here, _ in opened}, {GLENBURY, DORMONT})
        for _, report in opened:
            self.assertFalse(report["door_left_open"])
            self.assertLess(abs(report["actual_speed_mps"]), STANDSTILL_MPS)

    def test_no_power_while_a_door_is_open(self) -> None:
        for _, _, report, commands, _ in self.trace:
            if report["door_left_open"] or report["door_right_open"]:
                self.assertEqual(commands["power_w"], 0.0)

    def test_doors_close_before_the_train_leaves_glenbury(self) -> None:
        at_station = self.at(GLENBURY)
        first_open = next(
            tick for tick, report, _ in at_station
            if report["door_right_open"]
        )
        departing = [
            report for tick, report, _ in at_station
            if tick > first_open and report["actual_speed_mps"] > 0.0
        ]
        self.assertTrue(departing, "the train never moved off")
        self.assertFalse(departing[0]["door_right_open"])

    def test_passengers_board_at_glenbury(self) -> None:
        boarded = sum(
            feed["passengers_boarded"]
            for _, here, _, _, feed in self.trace if here == GLENBURY
        )
        self.assertGreater(boarded, 0)

    def test_the_driver_sees_the_light_on_block_64(self) -> None:
        self.assertEqual(self.core.state.next_signal, "GREEN")

    def test_the_route_ends_at_a_stand_with_no_authority(self) -> None:
        _, here, report, _, _ = self.trace[-1]
        self.assertEqual(here, DORMONT)
        self.assertEqual(report["authority_blocks"], 0)
        self.assertEqual(report["commanded_speed_mps"], 0.0)

    def test_the_track_model_followed_the_train(self) -> None:
        trains = self.loop.track.snapshot().trains
        self.assertEqual([train.train_id for train in trains], ["G1"])
        self.assertEqual(trains[0].block_id, "GREEN L-73")
        self.assertNotIn(
            "TRAIN_LEFT_TRACK", [event[1] for event in self.loop.events]
        )


class DwellTest(unittest.TestCase):
    """The Train Controller holds the dwell, however soon it may go."""

    def test_the_doors_stay_open_for_the_dwell(self) -> None:
        loop = _Loop(EARLY_RESUME)
        ticks: dict[str, int] = {}

        def doors_closed_again() -> bool:
            if not loop.has(TRAIN_MODEL):
                return False
            if loop.report["door_right_open"]:
                ticks.setdefault("opened", loop.tick)
            elif "opened" in ticks:
                ticks["closed"] = loop.tick
                return True
            return False

        self.assertTrue(loop.run_until(doors_closed_again, limit_s=150.0))
        open_s = (ticks["closed"] - ticks["opened"]) * DT_S
        self.assertGreaterEqual(open_s, DWELL_S)
        self.assertLess(open_s, DWELL_S + 1.0)
        self.assertTrue(loop.run_until(lambda: loop.speed_mps > 1.0))


class EmergencyBrakeTest(unittest.TestCase):
    """The driver's release holds, and releases a passenger pull."""

    def setUp(self) -> None:
        self.loop = _Loop(OPEN_LINE)
        self.assertTrue(self.loop.run_until(
            lambda: self.loop.has(TRAIN_MODEL) and self.loop.speed_mps > 5
        ))
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
