"""The five wired modules in a loop: the Iteration 3 scenario.

The harness's tick, in one process and without sockets: on each tick
the CTC Office, the Track Controller SW, the Track Model, the Train
Model and the Train Controller SW step on the outputs every module gave
on the tick before, mapped by ``SystemEdges``, just as the harness does
it across processes. Every input and output goes through JSON on the
way, as it would between processes. This runs each module's own code,
the CTC Office's included, so it checks the loop itself:

- nothing is released while a Green wayside has no PLC program (R44),
  and the clock runs on;
- the dispatcher sends G1 from the yard to GLENBURY (the Iteration 3
  scenario). Once every wayside has a program, the CTC Office releases
  it (D022), the Track Model places it at the yard exit block, and the
  CTC Office finds it there and follows it from occupancy, block by
  block, never taking it for a failure. Its suggestions reach the
  train through the Track Controller, the next block preloaded (R49),
  so authority never falls from two blocks or more to none. G1 stops
  at GLENBURY behind the door interlock and holds the dwell; the
  dispatcher sends it on, and it stops at DORMONT;
- every ticket the Track Model sells reaches the CTC Office once (R52);
- a switch the CTC Office commands in maintenance mode moves the Track
  Model's switch, and its read-back, and each light's, reaches the
  Track Controller and the CTC Office;
- a failed block reads occupied to the Track Controller and to the CTC
  Office (R33, R69), and the train stops short of it;
- the driver releases the emergency brake, with and without a
  passenger pull.

The dispatcher's actions are the CTC Office module's own, taken
between ticks as its window would take them.

Run from the repository root with
``python -m unittest discover -s common/harness/tests``.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
for _folder in (
    _REPO, _REPO / "TrackModel", _REPO / "TrainModel", _REPO / "Train-Ctrl_HW",
    _REPO / "TrackCtrlSW", _REPO / "CTC-Office",
):
    if str(_folder) not in sys.path:
        sys.path.insert(0, str(_folder))

from PySide6.QtCore import QCoreApplication  # noqa: E402

from common.harness.edges import SystemEdges  # noqa: E402
from common.harness.modules import (  # noqa: E402
    CTC_OFFICE,
    TRACK_CONTROLLER_SW,
    TRACK_MODEL,
    TRAIN_CONTROLLER_SW,
    TRAIN_MODEL,
)
from common.harness.roster import Event  # noqa: E402
from common.harness.wayside_edges import track_controller_to_ctc  # noqa: E402
from ctc.module_process import (  # noqa: E402
    CtcOfficeProcess,
    Dispatch,
    layout_files,
)
from ctc.schedule import parse_schedule  # noqa: E402
from ctc.track_layout import load_layout  # noqa: E402
from ctc_ui.ctc_host import CtcHost  # noqa: E402
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
KMH_PER_MPS = 3.6

#: Out of the yard exit block, GLENBURY (platform on the right), and
#: on to DORMONT (platform on the right).
ROUTE = [str(number) for number in range(63, 74)]
GLENBURY, DORMONT = "65", "73"

#: The Iteration 3 scenario: G1 from the yard to a Green station.
TO_GLENBURY = Dispatch("G1", "Green", GLENBURY)

#: Truth D007: the CTC Office schedules the dwell; the Train Controller
#: enforces it.
DWELL_S = 45.0

_LAYOUT = load_layout(layout_files())


def _wire(value: Any) -> Any:
    # Through JSON and back, as across a process boundary.
    return json.loads(json.dumps(value))


class _Loop:
    """The harness's tick for the five wired modules, in one process."""

    def __init__(
        self,
        dispatches: Sequence[Dispatch] = (TO_GLENBURY,),
        starters: bool = True,
    ) -> None:
        """Wire the modules, the Track Controller started up or not.

        Args:
            dispatches: What the dispatcher orders, given once the
                line is ready (the CTC Office process's test option).
            starters: Commit the starter PLC programs before the first
                tick, as a person would load them.
        """
        self.edges = SystemEdges()
        self.ctc_host = CtcHost(layout=_LAYOUT, serve_test_ui=False)
        self.ctc = self.ctc_host.module
        self.ctc_process = CtcOfficeProcess(
            self.ctc_host, "unused", dispatches=dispatches,
            parent=self.ctc_host,
        )
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
        # Tickets the Track Model sold, summed over every tick.
        self.tickets_sold = 0

    def step(self) -> None:
        """One tick: every module steps on the last tick's outputs."""
        self.tick += 1
        sim_time_s = START_S + self.tick * DT_S
        fresh = {}
        for name, process in (
            (CTC_OFFICE, self.ctc_process),
            (TRACK_CONTROLLER_SW, self.wayside),
            (TRACK_MODEL, self.track_model),
            (TRAIN_MODEL, self.model),
            (TRAIN_CONTROLLER_SW, self.controller),
        ):
            inputs = self.edges.inputs_for(
                name, self.tick, sim_time_s, self.outputs
            )
            fresh[name] = _wire(
                process.step(self.tick, DT_S, sim_time_s, _wire(inputs))
            )
        self.outputs.update(fresh)
        self.tickets_sold += sum(
            fresh[TRACK_MODEL]["ctc"]["tickets_sold_now"].values()
        )
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
    def at_rest_with_doors_open(self) -> bool:
        """Whether G1 stands with its right-hand doors open."""
        return (
            self.has(TRAIN_MODEL)
            and abs(self.speed_mps) < STANDSTILL_MPS
            and self.report["door_right_open"]
        )

    @property
    def followed(self) -> tuple[str, ...]:
        """The blocks the CTC Office follows G1 in; none if it does not."""
        for train in self.ctc.snapshot().trains:
            if train.train_id == "G1":
                return train.blocks
        return ()

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
    """Out of the yard to GLENBURY, then sent on to DORMONT."""

    loop: _Loop
    core: Any
    # The tick each module first named G1.
    joined: dict[str, int]
    # Per tick once the three train modules have G1: the block the
    # Train Model reports, its controller outputs, the commands, and
    # the feed.
    trace: list[tuple[int, str, dict[str, Any], dict[str, Any],
                      dict[str, Any]]]
    # The blocks the CTC Office followed G1 in, as they changed.
    followed: list[tuple[str, ...]]
    # The tick G1 stood at GLENBURY with its doors open.
    at_glenbury: int

    @classmethod
    def setUpClass(cls) -> None:
        loop = _Loop()
        cls.loop = loop
        cls.joined = {}
        cls.trace = []
        cls.followed = []

        def watch() -> None:
            for module in (CTC_OFFICE, TRACK_MODEL, TRAIN_MODEL,
                           TRAIN_CONTROLLER_SW):
                if module == CTC_OFFICE:
                    named = bool(loop.ctc.snapshot().orders)
                else:
                    named = loop.has(module)
                if named:
                    cls.joined.setdefault(module, loop.tick)
            followed = loop.followed
            if followed and (not cls.followed
                             or cls.followed[-1] != followed):
                cls.followed.append(followed)
            if len(cls.joined) == 4:
                cls.trace.append((loop.tick, loop.block, loop.report,
                                  loop.commands, loop.feed))

        def at(block: str) -> Callable[[], bool]:
            def condition() -> bool:
                watch()
                return (len(cls.joined) == 4 and loop.block == block
                        and loop.at_rest_with_doors_open)
            return condition

        if not loop.run_until(at(GLENBURY), limit_s=200.0):
            raise AssertionError(
                f"G1 never stood at GLENBURY: at tick {loop.tick}, "
                f"{loop.events}"
            )
        cls.at_glenbury = loop.tick
        # The dispatcher sends it on, as its window would, between
        # ticks; the Train Controller holds the dwell.
        loop.ctc.dispatch("G1", "Green", DORMONT)
        if not loop.run_until(at(DORMONT), limit_s=300.0):
            raise AssertionError(
                f"G1 never stood at DORMONT: at tick {loop.tick} it was "
                f"in block {loop.block}"
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
        # Ordered once the CTC Office reads the line ready, released on
        # its next step, then placed by the Track Model, fed to the
        # Train Model and reported to the Train Controller, a tick
        # apart each.
        ordered = self.joined[CTC_OFFICE]
        self.assertEqual(self.joined, {
            CTC_OFFICE: ordered,
            TRACK_MODEL: ordered + 2,
            TRAIN_MODEL: ordered + 3,
            TRAIN_CONTROLLER_SW: ordered + 4,
        })

    def test_the_ctc_office_follows_the_train_block_by_block(self) -> None:
        # Found leaving the yard at the exit block where the harness
        # placed it, then never taken for a failure, so never lost.
        self.assertEqual(self.followed[0], ("63",))
        heads: list[str] = []
        for blocks in self.followed:
            if not heads or heads[-1] != blocks[-1]:
                heads.append(blocks[-1])
        self.assertEqual(heads, ROUTE)
        self.assertEqual(self.loop.ctc.snapshot().lost_trains, ())

    def test_the_train_runs_block_by_block(self) -> None:
        blocks: list[str] = []
        for _, here, *_ in self.trace:
            if not blocks or blocks[-1] != here:
                blocks.append(here)
        self.assertEqual(blocks, ROUTE)

    def test_authority_never_falls_from_two_blocks_to_none(self) -> None:
        # The preloaded next block carries the train's values as it
        # enters; without it the train would read a stop at every
        # block (R49).
        authority = [report["authority_blocks"]
                     for _, _, report, _, _ in self.trace]
        for before, after in zip(authority, authority[1:]):
            if after == 0 and before:
                self.assertLess(before, 2)
        self.assertFalse(self.core.state.failures["signal_pickup"])
        self.assertFalse(self.core.state.emergency_brake)

    def test_the_commanded_speed_keeps_under_each_block_limit(
        self,
    ) -> None:
        green = _LAYOUT["Green"]
        for _, here, report, _, _ in self.trace:
            limit_mps = green.block(here).speed_limit_kmh / KMH_PER_MPS
            self.assertLessEqual(report["commanded_speed_mps"], limit_mps)
        top = max(report["actual_speed_mps"] for _, _, report, _, _ in
                  self.trace)
        self.assertGreater(top, 10.0)

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

    def test_the_doors_stay_open_for_the_dwell(self) -> None:
        # Sent on as soon as it stood there: the Train Controller still
        # holds the doors open for the dwell (D007).
        open_ticks = [
            tick for tick, report, _ in self.at(GLENBURY)
            if report["door_right_open"]
        ]
        self.assertGreaterEqual(len(open_ticks) * DT_S, DWELL_S)
        self.assertLess(len(open_ticks) * DT_S, DWELL_S + 1.0)
        self.assertEqual(open_ticks[-1] - open_ticks[0] + 1, len(open_ticks))

    def test_doors_close_before_the_train_leaves_glenbury(self) -> None:
        departing = [
            report for tick, report, _ in self.at(GLENBURY)
            if tick > self.at_glenbury and report["actual_speed_mps"] > 0.0
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
        # Out of the yard, G1 runs 63 -> 64 past switch 62's point, whose
        # light faces the other way (TM-2): the light ahead of it is the
        # next it comes onto from the fixed side, switch 85's at 85. The
        # starter program shows that GREEN, with no train near it.
        self.assertEqual(self.core.state.next_signal, "GREEN")

    def test_every_ticket_sold_reaches_the_ctc_office_once(self) -> None:
        # The last tick's sales are still on their way.
        sold = sum(self.loop.ctc.snapshot().tickets_sold.values())
        pending = sum(self.loop.edges._sales.pending.values())
        self.assertGreater(sold, 0)
        self.assertEqual(sold + pending, self.loop.tickets_sold)

    def test_the_route_ends_at_a_stand_with_no_authority(self) -> None:
        _, here, report, _, _ = self.trace[-1]
        self.assertEqual(here, DORMONT)
        self.assertEqual(report["authority_blocks"], 0)
        self.assertEqual(report["commanded_speed_mps"], 0.0)
        (limit,) = self.loop.ctc.snapshot().authorities
        self.assertEqual((limit.blocks, limit.reason), (0, "destination"))

    def test_the_track_model_followed_the_train(self) -> None:
        trains = self.loop.track.snapshot().trains
        self.assertEqual([train.train_id for train in trains], ["G1"])
        self.assertEqual(trains[0].block_id, "GREEN L-73")
        self.assertNotIn(
            "TRAIN_LEFT_TRACK", [event[1] for event in self.loop.events]
        )

    def test_the_ctc_office_reads_the_train_where_it_is(self) -> None:
        occupied = [
            each["block_id"] for each in self.loop.ctc_view["occupancy"]
            if each["occupied"]
        ]
        self.assertEqual(occupied, [DORMONT])
        self.assertEqual(self.loop.followed, (DORMONT,))


#: The whole Green Line from the yard exit block round to the yard
#: entry block, as the track runs it (``next_blocks``): out through the
#: loop at 85, back over 85 to 77, on to 101 and round to 150, over 28
#: down to 1, and over 13 up to 57.
GREEN_ROUND = [str(number) for number in (
    *range(63, 101), *range(85, 76, -1), *range(101, 151),
    *range(28, 0, -1), *range(13, 58),
)]

#: Set to 1 to run the round trip back to the yard, which is slow.
ROUND_TRIP_OPTION = "TRACK_OVERFLOW_ROUND_TRIP"

#: Each switch G1 runs through, by its points block.
POINTS = {"12": "13", "28": "28", "76": "77", "85": "85"}

#: The yard entry block, where a train sent back to the yard is retired
#: (truth D022).
YARD_ENTRY = "57"

#: One scheduled Green run, due at once, stopping at DORMONT only
#: (``ctc.schedule``, the ``utils/schedule_v4.json`` form; D020).
TO_DORMONT_AND_BACK = {
    "time_unit": "s",
    "lines": [{"line": "Green", "trains": [{
        "train_id": "1",
        "stops": [{"block_id": DORMONT, "station": "DORMONT",
                   "arrival_s": 0}],
    }]}],
}


@unittest.skipUnless(
    os.environ.get(ROUND_TRIP_OPTION) == "1",
    f"about 140 s of real time; set {ROUND_TRIP_OPTION}=1 to run",
)
class ReturnToYardTest(unittest.TestCase):
    """A scheduled run to DORMONT, then round the line back to the yard.

    The CTC Office runs the schedule in automatic mode (D020): it
    releases G1 (D022), stops it at DORMONT for the dwell, then sends it
    to the yard entry block, 57. The way there is the whole line, over
    switches 85, 76, 28 and 12 in both positions, set by the Track
    Controller's starter programs; the CTC Office counts authority only
    up to a switch not set for the route. Stopped at 57 with no
    authority, G1 is retired, once.

    About 2,100 s of simulated time, 21,000 ticks: historically some
    140 s of real time, so these five tests run only when asked
    (``TRACK_OVERFLOW_ROUND_TRIP=1``). Since the engine-detector fix
    in 460579b, all five pass with the detector enabled: G1 completes
    the round trip and is retired at Green 57.
    """

    loop: _Loop
    # The blocks the Train Model reported G1 in, as they changed.
    blocks: list[str]
    # For each switch, each time G1 was on its points: every position
    # the Track Controller commanded it to meanwhile.
    on_points: dict[str, list[set[str]]]
    # The yard switches' positions while G1 was on the line.
    yard_switches: set[str]
    # The tick G1 stood at DORMONT with its doors open, and was retired.
    at_dormont: int
    retired_at: int
    # G1 as last reported before it was retired.
    last_report: dict[str, Any]
    # Whether the Train Controller ever latched these, while G1 ran.
    emergency: bool
    pickup_failure: bool
    retired_events: list[str]

    @classmethod
    def setUpClass(cls) -> None:
        loop = _Loop(dispatches=())
        loop.ctc.load_schedule(parse_schedule(TO_DORMONT_AND_BACK))
        loop.ctc_host.setAutomaticMode(True)
        cls.loop = loop
        cls.blocks = []
        cls.on_points = {switch: [] for switch in POINTS}
        cls.yard_switches = set()
        cls.at_dormont = 0
        cls.retired_events = []
        cls.emergency = cls.pickup_failure = False
        cls.last_report = {}

        def removed() -> bool:
            return any(name == "TRAIN_REMOVED" for _, name, _ in loop.events)

        def watch() -> bool:
            cls.retired_events += [
                item["train_id"]
                for item in loop.outputs[CTC_OFFICE].get("retired_trains", [])
            ]
            if removed():
                return True
            if not (loop.has(TRAIN_MODEL) and loop.has(TRAIN_CONTROLLER_SW)):
                return False
            here = loop.block
            cls.last_report = loop.report
            entered = not cls.blocks or cls.blocks[-1] != here
            if entered:
                cls.blocks.append(here)
            if (not cls.at_dormont and here == DORMONT
                    and loop.at_rest_with_doors_open):
                cls.at_dormont = loop.tick
            for entry in loop.outputs[TRACK_CONTROLLER_SW]["track_model"][
                    "switch_commands"]:
                switch = entry["block"]["block_id"]
                if switch in ("58", "62"):
                    cls.yard_switches.add(entry["value"])
                elif POINTS.get(switch) == here:
                    if entered:
                        cls.on_points[switch].append(set())
                    cls.on_points[switch][-1].add(entry["value"])
            core = loop.controller_fleet.get("G1")
            cls.emergency |= core.state.emergency_brake
            cls.pickup_failure |= core.state.failures["signal_pickup"]
            return False

        if not loop.run_until(watch, limit_s=4_000.0):
            raise AssertionError(
                f"G1 was never retired: at tick {loop.tick} it was in "
                f"block {cls.blocks[-1:]}, {loop.ctc.snapshot().authorities}"
            )
        cls.retired_at = loop.tick
        # Long enough for any second retirement to show.
        loop.run_until(lambda: bool(watch()) and False, limit_s=5.0)

    def test_it_stops_at_its_scheduled_station(self) -> None:
        self.assertGreater(self.at_dormont, 0)

    def test_it_runs_the_whole_line_round_to_the_yard_entry(self) -> None:
        self.assertEqual(self.blocks, GREEN_ROUND)

    def test_each_switch_is_set_for_it_and_held_on_the_points(
        self,
    ) -> None:
        # G1 is on each switch's points twice, once each way; the switch
        # stands for its way through, and does not move while it is on
        # them.
        self.assertEqual(self.on_points, {
            # 76 -> 77 -> 78, then 78 -> 77 -> 101.
            "76": [{"normal"}, {"reverse"}],
            # 84 -> 85 -> 86, then 100 -> 85 -> 84.
            "85": [{"normal"}, {"reverse"}],
            # 150 -> 28 -> 27, then 27 -> 28 -> 29.
            "28": [{"reverse"}, {"normal"}],
            # 14 -> 13 -> 12, then 1 -> 13 -> 14.
            "12": [{"normal"}, {"reverse"}],
        })
        # The yard is never routed (D022).
        self.assertEqual(self.yard_switches, {"normal"})

    def test_it_is_retired_once_stopped_at_57(self) -> None:
        self.assertEqual(self.blocks[-1], YARD_ENTRY)
        self.assertLess(abs(self.last_report["actual_speed_mps"]),
                        STANDSTILL_MPS)
        self.assertEqual(self.last_report["authority_blocks"], 0)
        self.assertEqual(self.retired_events, ["G1"])
        removed = [detail for _, name, detail in self.loop.events
                   if name == "TRAIN_REMOVED"]
        self.assertEqual(removed, ["G1"])
        self.assertEqual(self.loop.track.snapshot().trains, ())
        self.assertNotIn(
            "TRAIN_LEFT_TRACK", [event[1] for event in self.loop.events]
        )
        (run,) = self.loop.ctc.snapshot().scheduled_runs
        self.assertEqual(run.status, "done")

    def test_no_emergency_brake_and_no_pickup_failure(self) -> None:
        self.assertFalse(self.emergency)
        self.assertFalse(self.pickup_failure)
        self.assertNotIn("PROTOCOL_ERROR",
                         [event[1] for event in self.loop.events])


class ReadinessTest(unittest.TestCase):
    """Nothing is released until every wayside has a program (R44)."""

    def test_the_clock_runs_and_nothing_is_released_until_ready(
        self,
    ) -> None:
        loop = _Loop(starters=False)
        for _ in range(50):
            loop.step()
        self.assertEqual(loop.tick, 50)
        self.assertEqual(len(loop.edges.roster), 0)
        self.assertFalse(loop.has(TRACK_MODEL))
        # The dispatcher's order waits: the CTC Office refuses it.
        self.assertEqual(loop.ctc.snapshot().orders, ())
        self.assertEqual(loop.ctc_process.pending_dispatches,
                         (TO_GLENBURY,))
        self.assertEqual(
            loop.outputs[CTC_OFFICE]["track_controller"]["suggestions"], []
        )
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


class SwitchAndLightTest(unittest.TestCase):
    """Switch and light commands and read-back, through both names."""

    def setUp(self) -> None:
        self.loop = _Loop(dispatches=())
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
        # Green 12 (12-13; 1-13) is the Track Model's switch D-13. The
        # dispatcher sets it in maintenance mode.
        self.assertEqual(self.track_model()["switch_states"]["GREEN D-13"],
                         "NORMAL")
        self.loop.ctc.set_maintenance_mode(True)
        self.loop.ctc.set_switch("Green", "12", "reverse")
        for _ in range(5):
            self.loop.step()
        self.assertEqual(self.track_model()["switch_states"]["GREEN D-13"],
                         "REVERSE")
        self.assertEqual(self.read_back("switches")["12"], "reverse")
        self.assertIn(
            {"line": "Green", "switch_id": "12", "position": "reverse"},
            self.loop.ctc_view["switches"],
        )
        self.assertTrue(self.loop.wayside_state.system.maintenance)
        self.loop.step()
        reported = self.loop.ctc.snapshot().inputs
        assert reported is not None
        self.assertIn(
            ("12", "reverse"),
            {(each.switch_id, each.position)
             for each in reported.track_controller.switches},
        )

    def test_each_light_shows_what_its_wayside_commands(self) -> None:
        # The Track Controller names a light by its switch's block, the
        # Track Model by the switch's point, where it stands (TM-2).
        lights = {"12": "GREEN D-13", "28": "GREEN F-28",
                  "58": "GREEN I-57", "62": "GREEN K-63",
                  "76": "GREEN N-77", "85": "GREEN N-85"}
        commands = {
            entry["block"]["block_id"]: entry["value"]
            for entry in self.loop.outputs[TRACK_CONTROLLER_SW][
                "track_model"]["signal_commands"]
        }
        # Every light starts RED in the Track Model; with no train on
        # the line, the starter program shows them all GREEN.
        self.assertEqual(set(commands), set(lights))
        self.assertEqual(set(commands.values()), {"green"})
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

    # Harry's Track Controller SW transmits nothing until it is started
    # up (TrackCtrlSW README, Startup), so the Track Model keeps its
    # crossings' last state (up) instead of holding them down. Speed and
    # authority are still fail-safe (a block not commanded reads 0/0).
    # Harry (2026-10-28): the module does not arm its crossings by
    # default yet, but will. This test expects that behaviour, so it
    # stays an expected failure until his change lands.
    @unittest.expectedFailure
    def test_crossings_follow_their_wayside(self) -> None:
        # Not ready, every wayside holds its crossings down: fail-safe.
        # The Red Line's have no Track Controller yet, and stay up.
        loop = _Loop(dispatches=(), starters=False)
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
        loop = _Loop(dispatches=(Dispatch("G1", "Green", DORMONT),))
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
        # It stops at 66, one empty block (67) short of the occupied
        # 68 (CTC Office, one empty block between trains).
        stopped = loop.run_until(
            lambda: loop.block == "66" and abs(loop.speed_mps) < 0.01,
            limit_s=120.0,
        )
        self.assertTrue(stopped, f"G1 is in block {loop.block}")
        (limit,) = loop.ctc.snapshot().authorities
        self.assertEqual((limit.reason, limit.at), ("occupied", "68"))
        for _ in range(100):
            loop.step()
            self.assertEqual(loop.block, "66")
        core = loop.controller_fleet.get("G1")
        self.assertFalse(core.state.emergency_brake)

        # Repaired, the block clears and the train goes on.
        loop.track.set_block_failure("GREEN K-68", TrackFailure.NONE)
        self.assertTrue(loop.run_until(lambda: loop.block == "69"))
        # The CTC Office follows it there, a few ticks behind.
        self.assertTrue(loop.run_until(
            lambda: loop.followed[-1:] == ("69",), limit_s=1.0
        ))


class SignalPickupTest(unittest.TestCase):
    """A pickup failure injected in the Train Model reaches the Train
    Controller as null, and it stops the train (Kevin Schillinger
    2026-10-28)."""

    def test_null_track_signal_stops_the_train(self) -> None:
        loop = _Loop(dispatches=(Dispatch("G1", "Green", DORMONT),))
        self.assertTrue(loop.run_until(
            lambda: loop.has(TRAIN_MODEL) and loop.speed_mps > 5
        ))
        core = loop.controller_fleet.get("G1")
        self.assertFalse(core.state.failures["signal_pickup"])
        loop.model_fleet.get("G1").setFailure("signal_pickup_failure", True)
        self.assertTrue(loop.run_until(
            lambda: core.state.failures["signal_pickup"],
            limit_s=4 * ECHO_TICKS * DT_S,
        ))
        self.assertIsNone(loop.report["commanded_speed_mps"])
        self.assertIsNone(loop.report["authority_blocks"])
        self.assertTrue(core.state.emergency_brake)
        self.assertTrue(loop.run_until(lambda: loop.speed_mps == 0.0))


class EmergencyBrakeTest(unittest.TestCase):
    """The driver's release holds, and releases a passenger pull."""

    def setUp(self) -> None:
        self.loop = _Loop(dispatches=(Dispatch("G1", "Green", DORMONT),))
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

    # A pull stays latched until the Train Controller sends emergency
    # brake false (Kevin Schillinger 2026-10-28).
    def test_passenger_pull_and_release(self) -> None:
        self.loop.model_fleet.get("G1").applyEmergencyBrake()
        self.assertTrue(self.loop.run_until(
            lambda: self.core.state.emergency_brake, limit_s=3 * DT_S
        ))
        self.stop_and_release()
        self.assertTrue(self.loop.run_until(
            lambda: not self.loop.report["emergency_brake_active"],
            limit_s=4 * ECHO_TICKS * DT_S,
        ))
        for _ in range(4 * ECHO_TICKS):
            self.loop.step()
            self.assertFalse(self.core.state.emergency_brake)
        self.assertFalse(self.core.state.emergency_brake)
        self.assertTrue(self.loop.run_until(lambda: self.loop.speed_mps > 1))


if __name__ == "__main__":
    unittest.main()
