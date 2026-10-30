"""End-to-end test of the system as wired: Phase 4, Iteration 3.

The harness starts all seven module processes: the CTC Office, the
Track Controller SW, the Track Model, the Train Model and the Train
Controller SW as themselves, and stubs for the two HW variants.

The main run is the Iteration 3 scenario: a train dispatched from the
yard to a Green station. Test options stand in for the people who
start a run, as ``--engineer-gains`` stands in for the engineer: the
Track Controller commits its starter PLC programs (``--load-starters``,
R44); the CTC Office presses Run and 10x once ready, and dispatches G1
to GLENBURY once the Green waysides are ready (``--run-on-ready``,
``--speedup-at-tick 0``, ``--dispatch``). The CTC Office releases G1
(D022), the Track Model places it on the yard exit block, and the CTC
Office's suggestions reach it through the Track Controller, block by
block, to a stop at GLENBURY with its doors open. The run checks the
clock waiting for Run, readiness before the release, the order the
modules take the train, the blocks it runs through, that authority
never falls from two blocks or more to none, the station stop behind
the door interlock, a run with no fault, and seven clean exits. It
takes about ten real seconds.

A second, short run loads no program: the clock runs, the Track
Controller reports every wayside not ready, and the CTC Office releases
no train.

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
from common.harness.edges import SystemEdges  # noqa: E402
from common.harness.modules import (  # noqa: E402
    CTC_OFFICE,
    MODULE_NAMES,
    TRACK_CONTROLLER_SW,
    TRACK_CONTROLLER_HW,
    TRAIN_CONTROLLER_HW,
    TRACK_MODEL,
    TRAIN_CONTROLLER_SW,
    TRAIN_MODEL,
    system_specs,
)
from utils.event_log import EventLog  # noqa: E402

_APP = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])

# Generous: seven processes start at once, five of them with windows.
WAIT_S = 120.0
STANDSTILL_MPS = 0.1
GLENBURY = "65"
#: Ticks to keep running once G1 stands at GLENBURY with its doors open.
AFTER_STOP_TICKS = 20

#: The CTC Office: Run and 10x once ready, and G1 to GLENBURY once the
#: Green waysides are ready, standing in for the dispatcher.
CTC_OPTIONS = ["--run-on-ready", "--speedup-at-tick", "0",
               "--dispatch", f"G1:Green:{GLENBURY}"]

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
    "TIME_SLIPPED",
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
    """One train, dispatched from the yard to GLENBURY, stopped there."""

    events: list[tuple[int, str, str, str]]
    # Per tick: G1's Track Model feed, Train Model outputs and Train
    # Controller commands, and the CTC Office's outputs, as each module
    # last sent them.
    trace: dict[int, tuple[Any, Any, Any, Any]]
    exit_codes: dict[str, int | None]
    stopped_at: int

    @classmethod
    def setUpClass(cls) -> None:
        folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(folder.cleanup)
        log = EventLog(Path(folder.name) / "events.csv")
        cls.addClassCleanup(log.close)
        harness = Harness(
            system_specs({
                CTC_OFFICE: CTC_OPTIONS,
                TRACK_CONTROLLER_HW: ["--test-pi", "process"],
                TRAIN_CONTROLLER_HW: ["--test-pi", "process"],
                TRACK_CONTROLLER_SW: ["--load-starters"],
                TRAIN_CONTROLLER_SW: ["--engineer-gains", "400000", "8000"],
            }),
            log,
            SystemEdges(),
        )
        cls.addClassCleanup(harness.stop)
        cls.events = []
        cls.trace = {}
        stopped: list[int] = []

        def on_event(source: str, event: str, detail: str) -> None:
            cls.events.append(
                (harness.clock.tick_count, source, event, detail)
            )

        def on_tick(tick: int, _round_trip_s: float) -> None:
            outputs = harness.outputs
            model = outputs.get(TRAIN_MODEL, {}).get("trains", {}).get("G1")
            cls.trace[tick] = (
                outputs.get(TRACK_MODEL, {}).get("train_feeds", {}).get(
                    "G1"),
                model,
                outputs.get(TRAIN_CONTROLLER_SW, {}).get("trains", {}).get(
                    "G1"),
                outputs.get(CTC_OFFICE),
            )
            if (not stopped and model is not None
                    and model["track"]["block_id"] == GLENBURY
                    and model["controller"]["door_right_open"]):
                stopped.append(tick)

        harness.eventLogged.connect(on_event)
        harness.tickCompleted.connect(on_tick)
        harness.start()
        if not wait_until(
            lambda: bool(stopped)
            and stopped[0] + AFTER_STOP_TICKS in cls.trace
        ):
            raise AssertionError(
                f"G1 never stood at GLENBURY: {cls.events}"
            )
        cls.stopped_at = stopped[0]
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
            for tick, (_, model, controller, _) in sorted(
                self.trace.items())
            if model is not None and controller is not None
        ]

    def logged(self, event: str) -> tuple[int, str, str]:
        """The tick, source and detail of the first ``event``."""
        return next(
            (tick, source, detail)
            for tick, source, name, detail in self.events
            if name == event
        )

    def test_the_clock_waits_for_run_from_the_ctc_office(self) -> None:
        names = [event[2] for event in self.events]
        self.assertLess(names.index("ALL_READY"),
                        names.index("CLOCK_RESUMED"))
        self.assertEqual(self.logged("SPEED_CHANGED")[1:],
                         ("harness", "10x"))
        self.assertEqual(self.logged("CLOCK_RESUMED")[0], 0)
        self.assertEqual(min(self.trace), 1)

    def test_the_waysides_are_ready_before_the_release(self) -> None:
        ready_at, source, line = self.logged("WAYSIDES_READY")
        self.assertEqual((source, line), (TRACK_CONTROLLER_SW, "Green"))
        self.assertNotIn("WAYSIDES_NOT_READY",
                         [event[2] for event in self.events])
        added_at, source, detail = self.logged("TRAIN_ADDED")
        self.assertEqual((source, detail), ("harness", "G1 on Green"))
        # The CTC Office reads the line ready a tick after the Track
        # Controller says so, orders G1 then, and releases it on its
        # next step.
        self.assertEqual(added_at, ready_at + 2)
        (released,) = [
            outputs["new_trains"] for tick, (*_, outputs)
            in self.trace.items()
            if outputs is not None and outputs["new_trains"]
        ]
        self.assertEqual(released, [{"train_id": "G1", "line": "Green"}])

    def test_each_module_takes_the_train_in_turn(self) -> None:
        added_at = self.logged("TRAIN_ADDED")[0]
        self.assertEqual(
            (self.first_tick(0), self.first_tick(1), self.first_tick(2)),
            (added_at + 1, added_at + 2, added_at + 3),
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
        self.assertEqual(blocks, ["63", "64", GLENBURY])

    def test_authority_never_falls_from_two_blocks_to_none(self) -> None:
        authority = [report["authority_blocks"]
                     for _, _, report, _ in self.driven()]
        for before, after in zip(authority, authority[1:]):
            if after == 0 and before:
                self.assertLess(before, 2)
        self.assertFalse(any(
            report["emergency_brake_active"]
            for _, _, report, _ in self.driven()
        ))

    def test_the_ctc_office_suggests_for_the_train_where_it_is(
        self,
    ) -> None:
        suggestions = self.trace[max(self.trace)][3]["track_controller"][
            "suggestions"]
        self.assertEqual(suggestions, [{
            "train_id": "G1", "line": "Green", "block_id": GLENBURY,
            "suggested_speed_mps": 0, "authority_blocks": 0,
        }])

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
        self.assertEqual(len(opened), max(self.trace) - self.stopped_at + 1)

    def test_no_power_while_a_door_is_open(self) -> None:
        for _, _, report, commands in self.driven():
            if report["door_left_open"] or report["door_right_open"]:
                self.assertEqual(commands["power_w"], 0.0)


class NotReadyTest(unittest.TestCase):
    """No PLC program: the clock runs and no train is released (R44)."""

    def test_nothing_is_released_while_the_waysides_are_not_ready(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder, EventLog(
            Path(folder) / "events.csv"
        ) as log:
            harness = Harness(
                system_specs({
                    CTC_OFFICE: CTC_OPTIONS,
                    TRACK_CONTROLLER_HW: ["--test-pi", "process"],
                    TRAIN_CONTROLLER_HW: ["--test-pi", "process"],
                }),
                log,
                SystemEdges(),
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
        self.assertEqual(
            harness.outputs[CTC_OFFICE]["track_controller"]["suggestions"],
            [],
        )
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
