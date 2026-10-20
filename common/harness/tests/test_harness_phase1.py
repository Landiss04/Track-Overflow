"""End-to-end test of Phase 1: the real Train Model and Train
Controller processes, and stubs for the rest.

The harness starts all seven module processes. The CTC Office's stub
releases G1 onto the Green Line on the first tick, and G1 runs over a
fixed track feed with a stop at GLENBURY. The Train Controller process
plays the engineer (``--engineer-gains``), so the train moves without
a person. The run checks the roster, the commands both ways through
the protocol, and the door interlock, then shuts down. It takes about
ten real seconds, most of it the windows starting offscreen.

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
    TRAIN_CONTROLLER_SW,
    TRAIN_MODEL,
    system_specs,
)
from common.harness.track_feed import (  # noqa: E402
    FeedBeacon,
    FeedSegment,
    FixedTrackFeed,
)
from utils.event_log import EventLog  # noqa: E402

_APP = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])

# Generous: seven processes start at once, two of them with windows.
WAIT_S = 90.0
LAST_TICK = 600
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

#: Faults that must not appear in a clean run.
FAULTS = {
    "TICK_REJECTED",
    "INPUTS_FAILED",
    "EDGES_FAILED",
    "PROTOCOL_ERROR",
    "UNEXPECTED_REPLY",
    "REPLY_LATE",
    "MODULE_DISCONNECTED",
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


class PhaseOneTest(unittest.TestCase):
    """One train, released, driven, stopped at a station, sent on."""

    @classmethod
    def setUpClass(cls) -> None:
        folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(folder.cleanup)
        log = EventLog(Path(folder.name) / "events.csv")
        cls.addClassCleanup(log.close)
        harness = Harness(
            system_specs({
                CTC_OFFICE: [
                    "--run-on-ready",
                    "--speedup-at-tick", "0",
                    "--release-train", "G1:Green@1",
                ],
                TRAIN_CONTROLLER_SW: ["--engineer-gains", "400000", "8000"],
            }),
            log,
            SystemEdges(FixedTrackFeed(STATION_STOP)),
        )
        cls.addClassCleanup(harness.stop)
        cls.events: list[tuple[int, str, str, str]] = []
        # Per tick: G1's Train Model report and Train Controller
        # commands, as each module last sent them.
        cls.trace: dict[int, tuple[Any, Any]] = {}

        def on_event(source: str, event: str, detail: str) -> None:
            cls.events.append(
                (harness.clock.tick_count, source, event, detail)
            )

        def on_tick(tick: int, _round_trip_s: float) -> None:
            outputs = harness.outputs
            model = outputs.get(TRAIN_MODEL, {}).get("trains", {})
            controller = outputs.get(TRAIN_CONTROLLER_SW, {}).get(
                "trains", {}
            )
            cls.trace[tick] = (model.get("G1"), controller.get("G1"))

        harness.eventLogged.connect(on_event)
        harness.tickCompleted.connect(on_tick)
        harness.start()
        if not wait_until(lambda: LAST_TICK in cls.trace):
            raise AssertionError(f"never reached tick {LAST_TICK}: "
                                 f"{cls.events}")
        cls.exit_codes = harness.stop()

    def driven(self) -> list[tuple[int, dict, dict]]:
        """Each tick with G1's report and commands, once both exist."""
        return [
            (tick, model["controller"], controller)
            for tick, (model, controller) in sorted(self.trace.items())
            if model is not None and controller is not None
        ]

    def test_release_reaches_both_modules(self) -> None:
        self.assertIn((1, "harness", "TRAIN_ADDED", "G1 on Green"),
                      self.events)
        first_report = min(
            tick for tick, (model, _) in self.trace.items()
            if model is not None
        )
        first_commands = min(
            tick for tick, (_, controller) in self.trace.items()
            if controller is not None
        )
        self.assertEqual((first_report, first_commands), (2, 3))

    def test_run_is_clean(self) -> None:
        faults = [event for event in self.events if event[2] in FAULTS]
        self.assertEqual(faults, [])
        self.assertEqual(self.exit_codes, dict.fromkeys(MODULE_NAMES, 0))

    def test_the_train_runs_at_its_commanded_speed(self) -> None:
        top = max(report["actual_speed_mps"] for _, report, _ in
                  self.driven())
        self.assertAlmostEqual(top, 10.0, delta=0.2)

    def test_doors_open_at_a_stand_on_the_platform_side(self) -> None:
        opened = [
            report for _, report, _ in self.driven()
            if report["door_left_open"] or report["door_right_open"]
        ]
        self.assertTrue(opened, "the doors never opened at GLENBURY")
        for report in opened:
            self.assertFalse(report["door_left_open"])
            self.assertLess(abs(report["actual_speed_mps"]), STANDSTILL_MPS)

    def test_no_power_while_a_door_is_open(self) -> None:
        for _, report, commands in self.driven():
            if report["door_left_open"] or report["door_right_open"]:
                self.assertEqual(commands["power_w"], 0.0)

    def test_the_train_moves_off_with_its_doors_shut(self) -> None:
        driven = self.driven()
        opened_at = next(
            tick for tick, report, _ in driven if report["door_right_open"]
        )
        moving = [
            report for tick, report, _ in driven
            if tick > opened_at and report["actual_speed_mps"] > 0.0
        ]
        self.assertTrue(moving, "the train never moved off")
        self.assertFalse(moving[0]["door_right_open"])
        self.assertGreater(driven[-1][1]["actual_speed_mps"], 1.0)


if __name__ == "__main__":
    unittest.main()
