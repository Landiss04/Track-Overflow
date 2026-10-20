"""The CTC Office process the harness drives, without the harness.

The process's step is called directly, as the harness's ``STEP`` would
call it: the JSON form of the inputs and outputs (``ctc.wire``), a bad
input refusing the tick and changing nothing, ticket sales counted once
per step, the harness's time in the window's header, Run, Pause and the
speed reaching the harness as ``STATE`` (R51), no test link (D025), the
window redrawn after the reply, and the test-only options that stand in
for the dispatcher.

Run from ``CTC-Office`` with ``python -m unittest discover tests``.
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
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PySide6.QtCore import QCoreApplication  # noqa: E402

from ctc.module_process import (  # noqa: E402
    WINDOW_REFRESH_MS,
    CtcOfficeProcess,
    Dispatch,
    _parse_args,
    layout_files,
)
from ctc.track_layout import load_layout  # noqa: E402
from ctc_ui.ctc_host import CtcHost  # noqa: E402
from ctc_ui.harness_clock import time_of_day_text  # noqa: E402
from utils.module_link import TickRejectedError  # noqa: E402

_APP = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])

DT_S = 0.1
FIVE_AM_S = 18_000.0
SECONDS_PER_DAY = 86_400.0
_LAYOUT = load_layout(layout_files())


def waysides(ready: bool = True) -> list[dict[str, Any]]:
    """The Green Line's six waysides, as the Track Controller reports."""
    return [
        {"wayside_id": f"GTC-0{n}", "line": "Green", "ready": ready,
         "reason": "" if ready else "no PLC program"}
        for n in range(1, 7)
    ]


def wire_inputs(
    occupied: tuple[str, ...] = (),
    ready: bool = True,
    sales: dict[str, int] | None = None,
) -> dict[str, Any]:
    """The module's inputs as the harness sends them."""
    return {
        "track_controller": {
            "occupancy": [
                {"line": "Green", "block_id": block, "occupied": True}
                for block in occupied
            ],
            "switches": [],
            "crossings": [],
            "waysides": waysides(ready),
        },
        "track_model": {"ticket_sales": dict(sales or {})},
    }


def wait_for(condition: Callable[[], bool], timeout_s: float = 3.0) -> bool:
    """Spin the event loop until ``condition`` holds or time runs out."""
    deadline = time.monotonic() + timeout_s
    while not condition() and time.monotonic() < deadline:
        _APP.processEvents()
    return condition()


class _ProcessCase(unittest.TestCase):
    """A process to step, as the harness steps it."""

    def make(self, **options: Any) -> CtcOfficeProcess:
        """A process on a fresh module, its pushes recorded."""
        self.host = CtcHost(layout=_LAYOUT, serve_test_ui=False)
        self.addCleanup(self.host.deleteLater)
        process = CtcOfficeProcess(
            self.host, "unused", parent=self.host, **options
        )
        self.pushed: list[dict[str, Any]] = []
        patcher = mock.patch.object(
            process._link, "push_state", self.pushed.append
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        return process

    def setUp(self) -> None:
        self.process = self.make()
        self.tick = 0

    def step(self, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        """One step, its inputs and outputs through JSON."""
        self.tick += 1
        sent = json.loads(json.dumps(inputs or wire_inputs()))
        return json.loads(json.dumps(self.process.step(
            self.tick, DT_S, FIVE_AM_S + self.tick * DT_S, sent
        )))


class ProcessTest(_ProcessCase):
    """One step at a time, as the harness sends them."""

    def test_the_outputs_are_the_modules_json_form(self) -> None:
        outputs = self.step()
        self.assertEqual(
            set(outputs["track_controller"]),
            {"suggestions", "closed_blocks", "switch_commands"},
        )
        self.assertIs(outputs["clock_paused"], True)
        self.assertIs(outputs["clock_speedup"], False)

    def test_it_opens_no_test_link(self) -> None:
        # D025: the harness drives the module, and nothing else does.
        self.assertIsNone(self.host._server)

    def test_a_bad_input_refuses_the_tick_and_changes_nothing(
        self,
    ) -> None:
        self.step(wire_inputs(sales={"GLENBURY": 2}))
        before = self.host.module.snapshot()
        missing = wire_inputs()
        del missing["track_controller"]["waysides"][0]["ready"]
        for bad in (
            {**wire_inputs(), "extra": {}},
            missing,
            wire_inputs(occupied=("999",)),
            wire_inputs(sales={"NOWHERE": 1}),
            wire_inputs(sales={"GLENBURY": -1}),
            {"track_controller": {"occupancy": "63"}},
        ):
            with self.subTest(bad=bad), self.assertRaises(TickRejectedError):
                self.process.step(2, DT_S, FIVE_AM_S, bad)
        with self.assertRaises(TickRejectedError):
            self.process.step(2, -DT_S, FIVE_AM_S, wire_inputs())
        self.assertEqual(self.host.module.snapshot(), before)

    def test_each_steps_ticket_sales_count_once(self) -> None:
        self.step(wire_inputs(sales={"GLENBURY": 3}))
        self.step(wire_inputs(sales={"GLENBURY": 2, "DORMONT": 1}))
        self.step()
        sold = self.host.module.snapshot().tickets_sold
        self.assertEqual((sold["GLENBURY"], sold["DORMONT"]), (5, 1))

    def test_the_header_shows_the_harness_time(self) -> None:
        clock = self.process.clock
        self.assertEqual(clock.property("timeText"), "05:00:00")
        self.process.step(1, DT_S, FIVE_AM_S + 3_725.0, wire_inputs())
        self.assertEqual(clock.property("timeText"), "06:02:05")
        # Unwrapped: a day on is the same time of day.
        self.assertEqual(
            time_of_day_text(FIVE_AM_S + SECONDS_PER_DAY), "05:00:00"
        )

    def test_it_starts_paused_at_1x(self) -> None:
        clock = self.process.clock
        self.assertTrue(clock.property("paused"))
        self.assertEqual(clock.property("speed"), 1)

    def test_run_pause_and_speed_go_to_the_harness_at_once(self) -> None:
        clock = self.process.clock
        # Before READY nothing may go: READY comes first.
        clock.resume()
        self.assertEqual(self.pushed, [])
        self.process._announce()
        self.assertEqual(
            self.pushed, [{"clock_paused": False, "clock_speedup": False}]
        )
        clock.setSpeed(10)
        clock.pause()
        clock.pause()
        self.assertEqual(self.pushed[1:], [
            {"clock_paused": False, "clock_speedup": True},
            {"clock_paused": True, "clock_speedup": True},
        ])
        # The outputs carry them too.
        outputs = self.step()
        self.assertEqual(
            (outputs["clock_paused"], outputs["clock_speedup"]),
            (True, True),
        )

    def test_the_window_redraws_after_the_reply(self) -> None:
        redraws: list[int] = []
        self.host.stateChanged.connect(lambda: redraws.append(1))
        self.step()
        self.assertEqual(redraws, [])
        self.assertTrue(wait_for(
            lambda: bool(redraws), timeout_s=10 * WINDOW_REFRESH_MS / 1000
        ))


class TestOptionsTest(_ProcessCase):
    """The options that stand in for the dispatcher, in tests only."""

    def test_run_on_ready_presses_run_after_ready(self) -> None:
        process = self.make(run_on_ready=True)
        self.assertEqual(self.pushed, [])
        process._announce()
        self.assertEqual(
            self.pushed, [{"clock_paused": False, "clock_speedup": False}]
        )

    def test_speedup_from_the_start(self) -> None:
        process = self.make(speedup_at_tick=0, run_on_ready=True)
        process._announce()
        self.assertEqual(self.pushed[-1],
                         {"clock_paused": False, "clock_speedup": True})

    def test_speedup_at_a_tick_is_pressed_after_its_reply(self) -> None:
        self.process = self.make(speedup_at_tick=2)
        self.process._announce()
        self.assertFalse(self.step()["clock_speedup"])
        # Pressed after the reply to step 2, so its outputs say 1x.
        self.assertFalse(self.step()["clock_speedup"])
        self.assertTrue(wait_for(lambda: bool(self.pushed)))
        self.assertTrue(self.pushed[-1]["clock_speedup"])
        self.assertTrue(self.step()["clock_speedup"])

    def test_a_dispatch_waits_for_its_line_to_be_ready(self) -> None:
        self.process = self.make(
            dispatches=[Dispatch("G1", "Green", "65")]
        )
        self.step(wire_inputs(ready=False))
        self.assertEqual(self.host.module.snapshot().orders, ())
        self.assertEqual(len(self.process.pending_dispatches), 1)
        self.step()
        (order,) = self.host.module.snapshot().orders
        self.assertEqual(
            (order.train_id, order.line, order.destination_block_id),
            ("G1", "Green", "65"),
        )
        self.assertEqual(self.process.pending_dispatches, ())

    def test_the_options_parse(self) -> None:
        options = _parse_args([
            "--harness", "server", "--run-on-ready",
            "--speedup-at-tick", "0", "--dispatch", "G1:Green:65",
        ])
        self.assertEqual(options.dispatch, [Dispatch("G1", "Green", "65")])
        self.assertEqual(options.speedup_at_tick, 0)
        for bad in (["--dispatch", "G1:Green"], ["--speedup-at-tick", "-1"]):
            with self.subTest(bad=bad), mock.patch("sys.stderr"), \
                    self.assertRaises(SystemExit):
                _parse_args(["--harness", "server", *bad])


if __name__ == "__main__":
    unittest.main()
