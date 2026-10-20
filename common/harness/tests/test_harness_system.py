"""End-to-end test of the system as wired: Phase 3.

The harness starts all seven module processes: the Track Controller SW,
the Track Model, the Train Model and the Train Controller SW as
themselves, and stubs for the rest.

The main run starts with the Track Controller's starter PLC programs
loaded (``--load-starters``), as a person would load them (R44). A
scripted CTC Office, standing in for its dispatch and suggestions,
reads every Green wayside ready and releases G1. The Track Model places
it on the yard exit block, and the stand-in's suggestions reach it
through the Track Controller, block by block, to a stop at GLENBURY and
on. The stand-in gives authority back 15 s after the train enters the
station's block, once it stands, and the Train Controller still holds
the 45 s dwell (truth D007). The Train Controller process plays the
engineer (``--engineer-gains``), so the train moves without a person.
The run checks readiness before the release, the order the modules
take the train, the blocks it runs through, the station stop behind the
door interlock and its dwell, and a clean shutdown. It takes about
fifteen real seconds.

A second, short run loads no program: the clock runs, the Track
Controller reports every wayside not ready, and no train is released.

Run from the repository root with
``python -m unittest discover -s common/harness/tests``.
"""

from __future__ import annotations

import sys
import tempfile
import time
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PySide6.QtCore import QCoreApplication, QEventLoop  # noqa: E402

from common.harness.core import Harness  # noqa: E402
from common.harness.ctc_script import (  # noqa: E402
    CtcRoute,
    RouteBlock,
    ScriptedCtc,
)
from common.harness.edges import SystemEdges  # noqa: E402
from common.harness.modules import (  # noqa: E402
    CTC_OFFICE,
    MODULE_NAMES,
    TRACK_CONTROLLER_SW,
    TRACK_MODEL,
    TRAIN_CONTROLLER_SW,
    TRAIN_MODEL,
    system_specs,
)
from utils.event_log import EventLog  # noqa: E402

_APP = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])

# Generous: seven processes start at once, four of them with windows.
WAIT_S = 120.0
LAST_TICK = 1100
STANDSTILL_MPS = 0.1
GLENBURY = "65"
DWELL_S = 45.0

#: Out of the yard exit block at 10 m/s, a stop at GLENBURY (platform
#: on the right) whose authority comes back 15 s after the train
#: enters, and on to block 67.
ROUTE = CtcRoute(
    train_id="G1",
    line="Green",
    blocks=(
        RouteBlock("63", 10),
        RouteBlock("64", 10),
        RouteBlock(GLENBURY, 10, hold_s=15.0),
        RouteBlock("66", 10),
        RouteBlock("67", 10),
    ),
)

#: The CTC Office's stub: Run once ready, at 10x.
CTC_STUB = ["--run-on-ready", "--speedup-at-tick", "0"]

#: Faults that must not appear in a clean run.
FAULTS = {
    "TICK_REJECTED",
    "INPUTS_FAILED",
    "EDGES_FAILED",
    "PROTOCOL_ERROR",
    "UNEXPECTED_REPLY",
    "REPLY_LATE",
    "MODULE_DISCONNECTED",
    "TRAIN_LEFT_TRACK",
}


def wait_until(
    condition: Callable[[], bool], timeout_s: float = WAIT_S
) -> bool:
    """Run the event loop until ``condition`` holds or time runs out."""
    deadline = time.monotonic() + timeout_s
    while not condition():
        if time.monotonic() > deadline:
            return False
        _APP.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
    return True


class SystemTest(unittest.TestCase):
    """One train, placed, driven block by block, stopped, sent on."""

    events: list[tuple[int, str, str, str]]
    # Per tick: G1's Track Model feed, Train Model outputs and Train
    # Controller commands, as each module last sent them.
    trace: dict[int, tuple[Any, Any, Any]]
    exit_codes: dict[str, int | None]

    @classmethod
    def setUpClass(cls) -> None:
        folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(folder.cleanup)
        log = EventLog(Path(folder.name) / "events.csv")
        cls.addClassCleanup(log.close)
        harness = Harness(
            system_specs({
                CTC_OFFICE: CTC_STUB,
                TRACK_CONTROLLER_SW: ["--load-starters"],
                TRAIN_CONTROLLER_SW: ["--engineer-gains", "400000", "8000"],
            }),
            log,
            SystemEdges(ScriptedCtc(ROUTE)),
        )
        cls.addClassCleanup(harness.stop)
        cls.events = []
        cls.trace = {}

        def on_event(source: str, event: str, detail: str) -> None:
            cls.events.append(
                (harness.clock.tick_count, source, event, detail)
            )

        def on_tick(tick: int, _round_trip_s: float) -> None:
            outputs = harness.outputs
            cls.trace[tick] = (
                outputs.get(TRACK_MODEL, {}).get("train_feeds", {}).get(
                    "G1"),
                outputs.get(TRAIN_MODEL, {}).get("trains", {}).get("G1"),
                outputs.get(TRAIN_CONTROLLER_SW, {}).get("trains", {}).get(
                    "G1"),
            )

        harness.eventLogged.connect(on_event)
        harness.tickCompleted.connect(on_tick)
        harness.start()
        if not wait_until(lambda: LAST_TICK in cls.trace):
            raise AssertionError(f"never reached tick {LAST_TICK}: "
                                 f"{cls.events}")
        cls.exit_codes = harness.stop()

    def first_tick(self, column: int) -> int:
        """The first tick a module's outputs named G1."""
        return min(
            tick for tick, row in self.trace.items()
            if row[column] is not None
        )

    def driven(self) -> list[tuple[int, str, dict[str, Any], Any]]:
        """Each tick with G1's block, report and commands, once both
        modules have it."""
        return [
            (tick, model["track"]["block_id"], model["controller"],
             controller)
            for tick, (_, model, controller) in sorted(self.trace.items())
            if model is not None and controller is not None
        ]

    def logged(self, event: str) -> tuple[int, str, str]:
        """The tick, source and detail of the first ``event``."""
        return next(
            (tick, source, detail)
            for tick, source, name, detail in self.events
            if name == event
        )

    def test_the_waysides_are_ready_when_the_train_is_released(
        self,
    ) -> None:
        self.assertEqual(self.logged("WAYSIDES_READY"),
                         (2, TRACK_CONTROLLER_SW, "Green"))
        self.assertNotIn("WAYSIDES_NOT_READY",
                         [event[2] for event in self.events])
        self.assertEqual(self.logged("TRAIN_ADDED"),
                         (2, "harness", "G1 on Green"))

    def test_each_module_takes_the_train_in_turn(self) -> None:
        self.assertEqual(
            (self.first_tick(0), self.first_tick(1), self.first_tick(2)),
            (3, 4, 5),
        )

    def test_run_is_clean(self) -> None:
        faults = [event for event in self.events if event[2] in FAULTS]
        self.assertEqual(faults, [])
        self.assertEqual(self.exit_codes, dict.fromkeys(MODULE_NAMES, 0))

    def test_the_track_model_places_the_train_at_the_yard_exit(
        self,
    ) -> None:
        first = self.trace[self.first_tick(0)][0]
        self.assertEqual(first["track_info"]["block_id"], "GREEN K-63")

    def test_the_train_runs_block_by_block(self) -> None:
        blocks: list[str] = []
        for _, block, _, _ in self.driven():
            if not blocks or blocks[-1] != block:
                blocks.append(block)
        self.assertEqual(blocks, ["63", "64", GLENBURY, "66"])

    def test_the_train_runs_at_its_commanded_speed(self) -> None:
        top = max(report["actual_speed_mps"] for _, _, report, _ in
                  self.driven())
        self.assertAlmostEqual(top, 10.0, delta=0.2)

    def test_doors_open_at_a_stand_on_the_platform_side(self) -> None:
        opened = [
            (block, report) for _, block, report, _ in self.driven()
            if report["door_left_open"] or report["door_right_open"]
        ]
        self.assertTrue(opened, "the doors never opened at GLENBURY")
        for block, report in opened:
            self.assertEqual(block, GLENBURY)
            self.assertFalse(report["door_left_open"])
            self.assertLess(abs(report["actual_speed_mps"]), STANDSTILL_MPS)

    def test_no_power_while_a_door_is_open(self) -> None:
        for _, _, report, commands in self.driven():
            if report["door_left_open"] or report["door_right_open"]:
                self.assertEqual(commands["power_w"], 0.0)

    def test_the_doors_stay_open_for_the_dwell(self) -> None:
        open_ticks = [
            tick for tick, _, report, _ in self.driven()
            if report["door_right_open"]
        ]
        self.assertGreaterEqual(len(open_ticks) * 0.1, DWELL_S)
        self.assertEqual(open_ticks[-1] - open_ticks[0] + 1, len(open_ticks))

    def test_the_train_moves_off_with_its_doors_shut(self) -> None:
        driven = self.driven()
        opened_at = next(
            tick for tick, _, report, _ in driven
            if report["door_right_open"]
        )
        moving = [
            report for tick, _, report, _ in driven
            if tick > opened_at and report["actual_speed_mps"] > 0.0
        ]
        self.assertTrue(moving, "the train never moved off")
        self.assertFalse(moving[0]["door_right_open"])
        self.assertGreater(driven[-1][2]["actual_speed_mps"], 1.0)


class NotReadyTest(unittest.TestCase):
    """No PLC program: the clock runs and no train is released (R44)."""

    def test_nothing_is_released_while_the_waysides_are_not_ready(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder, EventLog(
            Path(folder) / "events.csv"
        ) as log:
            harness = Harness(
                system_specs({CTC_OFFICE: CTC_STUB}),
                log,
                SystemEdges(ScriptedCtc(ROUTE)),
            )
            events: list[tuple[str, str, str]] = []
            harness.eventLogged.connect(
                lambda *event: events.append(event)
            )
            harness.start()
            try:
                self.assertTrue(
                    wait_until(lambda: harness.clock.tick_count >= 100)
                )
            finally:
                exit_codes = harness.stop()
        names = [event[1] for event in events]
        self.assertNotIn("TRAIN_ADDED", names)
        self.assertNotIn("WAYSIDES_READY", names)
        source, _, detail = next(
            event for event in events if event[1] == "WAYSIDES_NOT_READY"
        )
        self.assertEqual(source, TRACK_CONTROLLER_SW)
        self.assertEqual(
            detail,
            "Green: GTC-01, GTC-02, GTC-03, GTC-04, GTC-05, GTC-06: "
            "no PLC program",
        )
        self.assertEqual(exit_codes, dict.fromkeys(MODULE_NAMES, 0))


if __name__ == "__main__":
    unittest.main()
