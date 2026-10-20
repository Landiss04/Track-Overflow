"""The four wired modules in a loop, with the CTC Office's stand-in.

The harness's tick, in one process and without sockets: on each tick
the Track Controller SW, the Track Model, the Train Model and the Train
Controller SW step on the outputs every module gave on the tick before,
mapped by ``SystemEdges``, just as the harness does it across
processes. Every input and output goes through JSON on the way, as it
would between processes. This runs each module's own code, so it
checks the loop itself:

- nothing is released while a Green wayside has no PLC program (R44),
  and the clock runs on;
- once every wayside has one, the scripted CTC Office releases G1, the
  Track Model places it at the yard exit block, and the Track
  Controller passes the stand-in's suggestions down each block's track
  circuit, the next block preloaded (R49). G1 runs block by block,
  stops at GLENBURY behind the door interlock and the dwell, and at
  DORMONT at the end of its route;
- a switch the CTC Office commands moves the Track Model's switch, and
  its read-back, and each light's, reaches the Track Controller and the
  CTC Office;
- a failed block reads occupied to the Track Controller and to the CTC
  Office (R33, R69), and the train stops short of it;
- the driver releases the emergency brake, with and without a
  passenger pull.

Run from the repository root with
``python -m unittest discover -s common/harness/tests``.
"""

from __future__ import annotations

import json
import sys
import unittest
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
for _folder in (
    _REPO, _REPO / "TrackModel", _REPO / "TrainModel", _REPO / "Train-Ctrl_HW",
    _REPO / "TrackCtrlSW",
):
    if str(_folder) not in sys.path:
        sys.path.insert(0, str(_folder))

from PySide6.QtCore import QCoreApplication  # noqa: E402

from common.harness.ctc_script import (  # noqa: E402
    GREEN_YARD_TO_DORMONT,
    CtcRoute,
    RouteBlock,
    ScriptedCtc,
)
from common.harness.edges import SystemEdges  # noqa: E402
from common.harness.modules import (  # noqa: E402
    TRACK_CONTROLLER_SW,
    TRACK_MODEL,
    TRAIN_CONTROLLER_SW,
    TRAIN_MODEL,
)
from common.harness.roster import Event  # noqa: E402
from common.harness.wayside_edges import track_controller_to_ctc  # noqa: E402
from track_ctrl.module_process import (  # noqa: E402
    TrackControllerProcess,
    green_line,
)
from track_ctrl.state import TrackControllerState  # noqa: E402
from track_model.interface import TrackConfig, TrackFailure  # noqa: E402
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
OPEN_LINE = CtcRoute(
    "G1", "Green", tuple(RouteBlock(str(n), 10) for n in range(63, 74))
)

#: A stop at GLENBURY whose authority comes back 15 s after the train
#: enters: once it stands, but well before the dwell is over, which the
#: Train Controller enforces.
EARLY_RESUME = CtcRoute("G1", "Green", (
    RouteBlock("63", 10),
    RouteBlock("64", 10),
    RouteBlock(GLENBURY, 10, hold_s=15.0),
    RouteBlock("66", 10),
    RouteBlock("67", 10),
))

#: Truth D007: the CTC Office schedules the dwell; the Train Controller
#: enforces it.
DWELL_S = 45.0


def _wire(value: Any) -> Any:
    # Through JSON and back, as across a process boundary.
    return json.loads(json.dumps(value))


class _Loop:
    """The harness's tick for the four wired modules, in one process."""

    def __init__(self, route: CtcRoute, starters: bool = True) -> None:
        """Wire the modules, the Track Controller started up or not.

        Args:
            route: The stand-in's run.
            starters: Commit the starter PLC programs before the first
                tick, as a person would load them.
        """
        self.edges = SystemEdges(ScriptedCtc(route))
        self.wayside_state = TrackControllerState(lines=(green_line(),))
        if starters:
            self.wayside_state.loadStarterPrograms()
        self.wayside = TrackControllerProcess(
            self.wayside_state, "unused", parent=self.wayside_state
        )
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
        # Switch commands added to the Track Controller's inputs, as
        # the CTC Office sends them in maintenance mode.
        self.switch_commands: list[dict[str, Any]] = []

    def step(self) -> None:
        """One tick: every module steps on the last tick's outputs."""
        self.tick += 1
        sim_time_s = START_S + self.tick * DT_S
        fresh = {}
        for name, process in (
            (TRACK_CONTROLLER_SW, self.wayside),
            (TRACK_MODEL, self.track_model),
            (TRAIN_MODEL, self.model),
            (TRAIN_CONTROLLER_SW, self.controller),
        ):
            inputs = self.edges.inputs_for(
                name, self.tick, sim_time_s, self.outputs
            )
            if name == TRACK_CONTROLLER_SW:
                inputs["ctc"]["switch_commands"] += self.switch_commands
            fresh[name] = _wire(
                process.step(self.tick, DT_S, sim_time_s, _wire(inputs))
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

    def first(self, event: str) -> tuple[str, str]:
        """The source and detail of the first ``event`` logged."""
        return next(
            (source, detail) for source, name, detail in self.events
            if name == event
        )

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

    @property
    def ctc_view(self) -> dict[str, Any]:
        """What the CTC Office reads from the Track Controller now."""
        return track_controller_to_ctc(self.outputs[TRACK_CONTROLLER_SW])

    def occupied_to_ctc(self, block: str) -> bool:
        """Whether the CTC Office reads Green ``block`` occupied."""
        return any(
            each["block_id"] == block and each["occupied"]
            for each in self.ctc_view["occupancy"]
        )


class StationStopTest(unittest.TestCase):
    """The default route: out of the yard, GLENBURY, then DORMONT."""

    loop: _Loop
    core: Any
    # The tick each module first named G1.
    joined: dict[str, int]
    # Per tick once the three train modules have G1: the block the
    # Train Model reports, its controller outputs, the commands, and
    # the feed.
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

    def test_the_waysides_are_ready_before_the_release(self) -> None:
        events = [(source, name) for source, name, _ in self.loop.events]
        ready = events.index((TRACK_CONTROLLER_SW, "WAYSIDES_READY"))
        added = events.index(("harness", "TRAIN_ADDED"))
        self.assertLess(ready, added)
        self.assertEqual(self.loop.first("TRAIN_ADDED")[1], "G1 on Green")

    def test_each_module_takes_the_train_in_turn(self) -> None:
        # Released on the tick the stand-in first reads the waysides
        # ready; then placed by the Track Model, fed to the Train Model
        # and reported to the Train Controller, a tick apart each.
        released = self.joined[TRACK_MODEL] - 1
        self.assertEqual(self.joined, {
            TRACK_MODEL: released + 1,
            TRAIN_MODEL: released + 2,
            TRAIN_CONTROLLER_SW: released + 3,
        })

    def test_the_train_runs_block_by_block(self) -> None:
        blocks: list[str] = []
        for _, here, *_ in self.trace:
            if not blocks or blocks[-1] != here:
                blocks.append(here)
        self.assertEqual(blocks, ROUTE)

    def test_authority_never_falls_from_two_blocks_to_none(self) -> None:
        # The preloaded next block carries the train's values as it
        # enters; without it the Train Controller would read a pickup
        # failure at every block.
        authority = [report["authority_blocks"]
                     for _, _, report, _, _ in self.trace]
        for before, after in zip(authority, authority[1:]):
            if after == 0 and before:
                self.assertLess(before, 2)
        self.assertFalse(self.core.state.failures["signal_pickup"])
        self.assertFalse(self.core.state.emergency_brake)

    def test_the_train_reaches_its_suggested_speed(self) -> None:
        top = max(report["actual_speed_mps"] for _, _, report, _, _ in
                  self.trace)
        self.assertAlmostEqual(top, 12.0, delta=0.3)

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

    def test_the_driver_sees_the_light_the_wayside_set(self) -> None:
        # The light on block 64 is the yard switch's (Green 62). The
        # starter program shows it YELLOW while the blocks past it, 63
        # and 64, are occupied, as they are while G1 enters 64.
        self.assertEqual(self.core.state.next_signal, "YELLOW")

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

    def test_the_ctc_office_reads_the_train_where_it_is(self) -> None:
        self.assertTrue(self.loop.occupied_to_ctc(DORMONT))
        occupied = [
            each["block_id"] for each in self.loop.ctc_view["occupancy"]
            if each["occupied"]
        ]
        self.assertEqual(occupied, [DORMONT])


class ReadinessTest(unittest.TestCase):
    """Nothing is released until every wayside has a program (R44)."""

    def test_the_clock_runs_and_nothing_is_released_until_ready(
        self,
    ) -> None:
        loop = _Loop(GREEN_YARD_TO_DORMONT, starters=False)
        for _ in range(50):
            loop.step()
        self.assertEqual(loop.tick, 50)
        self.assertEqual(len(loop.edges.roster), 0)
        self.assertFalse(loop.has(TRACK_MODEL))
        source, detail = loop.first("WAYSIDES_NOT_READY")
        self.assertEqual(source, TRACK_CONTROLLER_SW)
        self.assertTrue(detail.startswith("Green: GTC-01, GTC-02"))
        self.assertTrue(detail.endswith("no PLC program"))
        # Every wayside reports, and none is ready.
        waysides = loop.ctc_view["waysides"]
        self.assertEqual(len(waysides), 6)
        self.assertFalse(any(each["ready"] for each in waysides))

        # A person loads the programs; the run starts.
        loop.wayside_state.loadStarterPrograms()
        self.assertTrue(loop.run_until(
            lambda: loop.has(TRAIN_CONTROLLER_SW), limit_s=2.0
        ))
        self.assertEqual(
            loop.first("WAYSIDES_READY"), (TRACK_CONTROLLER_SW, "Green")
        )
        self.assertTrue(loop.run_until(lambda: loop.block == "64"))


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


class SwitchAndLightTest(unittest.TestCase):
    """Switch and light commands and read-back, through both names."""

    def setUp(self) -> None:
        self.loop = _Loop(GREEN_YARD_TO_DORMONT)
        for _ in range(10):
            self.loop.step()

    def track_model(self) -> Mapping[str, Any]:
        """The Track Model's last outputs to the Track Controller."""
        return self.loop.outputs[TRACK_MODEL]["controller"]

    def read_back(self, field: str) -> dict[str, Any]:
        """One read-back field the Track Controller was last given."""
        snapshot = self.loop.wayside_state.system.snapshot()
        if field == "switches":
            return {
                state.switch.block_id: state.reported
                for wayside in snapshot.waysides
                for state in wayside.switches
            }
        return {
            key.block_id: value
            for wayside in snapshot.waysides
            for key, value in wayside.signal_reports.items()
        }

    def test_a_commanded_switch_moves_and_reads_back(self) -> None:
        # Green 12 (12-13; 1-13) is the Track Model's switch D-13.
        self.assertEqual(self.track_model()["switch_states"]["GREEN D-13"],
                         "NORMAL")
        self.loop.switch_commands = [{
            "block": {"line": "Green", "block_id": "12"},
            "value": "reverse",
        }]
        for _ in range(4):
            self.loop.step()
        self.assertEqual(self.track_model()["switch_states"]["GREEN D-13"],
                         "REVERSE")
        self.assertEqual(self.read_back("switches")["12"], "reverse")
        self.assertIn(
            {"line": "Green", "switch_id": "12", "position": "reverse"},
            self.loop.ctc_view["switches"],
        )
        self.assertTrue(self.loop.wayside_state.system.maintenance)

    def test_each_light_shows_what_its_wayside_commands(self) -> None:
        # The Track Controller names a light by its switch's block, the
        # Track Model by the block it stands on.
        lights = {"12": "GREEN D-14", "28": "GREEN F-27",
                  "58": "GREEN I-56", "62": "GREEN K-64",
                  "76": "GREEN N-78", "85": "GREEN N-84"}
        commands = {
            entry["block"]["block_id"]: entry["value"]
            for entry in self.loop.outputs[TRACK_CONTROLLER_SW][
                "track_model"]["signal_commands"]
        }
        # Every light starts RED in the Track Model; these are not.
        self.assertEqual(set(commands.values()), {"green", "yellow"})
        self.loop.step()
        for switch, light in lights.items():
            self.assertEqual(
                self.track_model()["signal_states"][light],
                commands[switch].upper(),
            )
        self.loop.step()
        self.assertEqual(
            self.read_back("lights"),
            {switch: commands[switch] for switch in lights},
        )

    def test_crossings_follow_their_wayside(self) -> None:
        # Not ready, every wayside holds its crossings down: fail-safe.
        # The Red Line's have no Track Controller yet, and stay up.
        loop = _Loop(GREEN_YARD_TO_DORMONT, starters=False)
        for _ in range(3):
            loop.step()

        def crossings() -> tuple[dict[str, bool], dict[str, str]]:
            states = loop.outputs[TRACK_MODEL]["controller"][
                "crossing_states"]
            return states, {
                each["crossing_id"]: each["state"]
                for each in loop.ctc_view["crossings"]
            }

        self.assertEqual(crossings(), (
            {"GREEN E-19": True, "GREEN T-108": True,
             "RED D-11": False, "RED I-47": False},
            {"19": "active", "108": "active"},
        ))
        # Started up, they lift: no train is near either.
        loop.wayside_state.loadStarterPrograms()
        for _ in range(3):
            loop.step()
        self.assertEqual(crossings(), (
            {"GREEN E-19": False, "GREEN T-108": False,
             "RED D-11": False, "RED I-47": False},
            {"19": "inactive", "108": "inactive"},
        ))


class FailureTest(unittest.TestCase):
    """A failed block reads occupied, and the train stops short of it."""

    def test_a_broken_rail_ahead_stops_the_train_before_it(self) -> None:
        loop = _Loop(OPEN_LINE)
        self.assertTrue(loop.run_until(
            lambda: loop.has(TRAIN_MODEL) and loop.block == "64"
        ))
        loop.track.set_block_failure("GREEN K-68", TrackFailure.BROKEN_RAIL)
        self.assertTrue(loop.run_until(
            lambda: loop.occupied_to_ctc("68"), limit_s=1.0
        ))
        # Occupied to the Track Controller as to the CTC Office, with
        # nothing else said of it (R33, R69).
        snapshot = loop.wayside_state.system.snapshot()
        self.assertIn(
            "68",
            {key.block_id for wayside in snapshot.waysides
             for key in wayside.occupied_blocks},
        )
        stopped = loop.run_until(
            lambda: loop.block == "67" and abs(loop.speed_mps) < 0.01,
            limit_s=120.0,
        )
        self.assertTrue(stopped, f"G1 is in block {loop.block}")
        for _ in range(100):
            loop.step()
            self.assertEqual(loop.block, "67")

        # Repaired, the block clears and the train goes on.
        loop.track.set_block_failure("GREEN K-68", TrackFailure.NONE)
        self.assertTrue(loop.run_until(lambda: loop.block == "69"))


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
