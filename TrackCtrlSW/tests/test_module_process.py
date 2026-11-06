"""The Track Controller process the harness drives, without the harness.

The process's step is called directly, as the harness's ``STEP`` would
call it: the JSON form of the inputs and outputs, the step's simulation
time as the module's, a bad input refusing the tick and changing
nothing, the Green Line alone (R77), startup by a person (R44), and the
clock the window's header shows.

Run from ``TrackCtrlSW``::

    .venv/Scripts/python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import sys
import time
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# This module's folder, and the repository root for the shared link.
for _folder in Path(__file__).resolve().parents[1:3]:
    if str(_folder) not in sys.path:
        sys.path.insert(0, str(_folder))

from PySide6.QtCore import QCoreApplication  # noqa: E402

from track_ctrl.module_process import (  # noqa: E402
    CLOCK_IDLE_MS,
    TrackControllerProcess,
    green_line,
)
from track_ctrl.state import TrackControllerState  # noqa: E402
from track_ctrl.wire import outputs_from_wire  # noqa: E402
from utils.module_link import TickRejectedError  # noqa: E402

_APP = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])

DT_S = 0.1
FIVE_AM_S = 18_000.0
SECONDS_PER_DAY = 86_400.0


def _block(number: str) -> dict[str, str]:
    return {"line": "Green", "block_id": number}


def wire_inputs(**changes: Any) -> dict[str, Any]:
    """The module's inputs as the harness sends them: G1 in block 63."""
    inputs: dict[str, Any] = {
        "ctc": {
            "closed_blocks": [],
            "switch_commands": [],
            "suggestions": [
                {"block": _block("63"),
                 "value": {"speed_mps": 12, "authority_blocks": 2}},
                {"block": _block("64"),
                 "value": {"speed_mps": 12, "authority_blocks": 1}},
            ],
        },
        "track_model": {
            "occupied_blocks": [_block("63")],
            "switch_positions": [],
            "crossings_active": [],
            "signal_aspects": [],
        },
    }
    inputs.update(changes)
    return inputs


def wait_for(condition: Callable[[], bool], timeout_s: float = 3.0) -> bool:
    """Spin the event loop until ``condition`` holds or time runs out."""
    deadline = time.monotonic() + timeout_s
    while not condition() and time.monotonic() < deadline:
        _APP.processEvents()
    return condition()


class ProcessTest(unittest.TestCase):
    """One step at a time, as the harness sends them."""

    def setUp(self) -> None:
        self.state = TrackControllerState(lines=(green_line(),))
        self.process = TrackControllerProcess(
            self.state, "unused", parent=self.state
        )

    def tearDown(self) -> None:
        self.state.deleteLater()
        _APP.processEvents()

    def step(
        self, inputs: dict[str, Any] | None = None, tick: int = 1
    ) -> dict[str, Any]:
        """One step, its inputs and outputs through JSON."""
        sent = json.loads(json.dumps(inputs or wire_inputs()))
        return json.loads(json.dumps(self.process.step(
            tick, DT_S, FIVE_AM_S + tick * DT_S, sent
        )))

    def circuits(self, outputs: dict[str, Any]) -> dict[str, Any]:
        """Each block's track circuit: speed and authority."""
        return {
            key.block_id: (circuit.speed_mps, circuit.authority_blocks)
            for key, circuit in outputs_from_wire(
                outputs).track_model.track_circuits.items()
        }

    def test_it_runs_the_green_line_alone(self) -> None:
        system = self.state.system
        self.assertEqual([line.key for line in system.lines], ["Green"])
        self.assertEqual(
            system.wayside_ids,
            ("GTC-01", "GTC-02", "GTC-03", "GTC-04", "GTC-05", "GTC-06"),
        )

    def test_not_ready_until_a_person_loads_the_programs(self) -> None:
        outputs = self.step()
        decoded = outputs_from_wire(outputs)
        self.assertFalse(decoded.ready)
        self.assertEqual(
            {report.reason for report in decoded.ctc_reports},
            {"no PLC program"},
        )
        # A wayside running nothing transmits nothing (README, Startup).
        # That is fail-safe: the Track Model reads a block not commanded
        # this tick as speed 0, authority 0.
        self.assertEqual(self.circuits(outputs), {})

    def test_started_up_it_passes_the_suggestions_on(self) -> None:
        self.state.loadStarterPrograms()
        outputs = self.step()
        self.assertTrue(outputs_from_wire(outputs).ready)
        # Block 64 is the next block, preloaded for G1 in 63.
        self.assertEqual(self.circuits(outputs),
                         {"63": (12, 2), "64": (12, 1)})

    def test_the_steps_time_is_the_modules(self) -> None:
        self.step(tick=3)
        self.assertAlmostEqual(self.state.system.time_s or 0.0,
                               FIVE_AM_S + 0.3)
        self.assertEqual(self.state.property("clock"), "05:00:00")
        # Unwrapped simulation time: a day on is the same time of day.
        self.process.step(4, DT_S, FIVE_AM_S + SECONDS_PER_DAY,
                          wire_inputs())
        self.assertEqual(self.state.property("clock"), "05:00:00")

    def test_a_bad_input_refuses_the_tick_and_changes_nothing(
        self,
    ) -> None:
        self.state.loadStarterPrograms()
        self.step()
        before = self.state.system.snapshot()
        fractional = wire_inputs()
        fractional["ctc"]["suggestions"][0]["value"]["speed_mps"] = 12.5
        for bad in (
            {"ctc": wire_inputs()["ctc"]},
            wire_inputs(time_s=FIVE_AM_S),
            wire_inputs(extra=True),
            fractional,
        ):
            with self.subTest(bad=bad), self.assertRaises(TickRejectedError):
                self.process.step(2, DT_S, FIVE_AM_S, bad)
        with self.assertRaises(TickRejectedError):
            self.process.step(2, -DT_S, FIVE_AM_S, wire_inputs())
        self.assertEqual(self.state.system.snapshot(), before)

    def test_the_header_shows_the_clock_running_while_steps_come(
        self,
    ) -> None:
        self.assertTrue(self.state.property("clockPaused"))
        self.step()
        self.assertFalse(self.state.property("clockPaused"))
        # No step for a while: the clock is paused, as far as it knows.
        self.assertTrue(wait_for(
            lambda: bool(self.state.property("clockPaused")),
            timeout_s=3 * CLOCK_IDLE_MS / 1000,
        ))


if __name__ == "__main__":
    unittest.main()
