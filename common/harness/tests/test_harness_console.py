"""Test display state, buffering and fault runs against seven stubs."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import PropertyMock, patch

from PySide6.QtCore import QCoreApplication, QModelIndex

from common.harness.console import (
    MAX_EVENTS,
    MAX_OUTPUT_CHARS,
    HarnessConsole,
)
from common.harness.core import Harness
from common.harness.modules import (
    CTC_OFFICE,
    MODULE_NAMES,
    TRACK_MODEL,
    TRAIN_CONTROLLER_SW,
    TRAIN_MODEL,
    stub_specs,
)
from common.harness.tests.test_harness_end_to_end import wait_until
from common.harness.window import resource_path
from utils.event_log import EventLog

_APP = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])


class ConsoleStateTest(unittest.TestCase):
    """Keep publications bounded and independent of tick frequency."""

    def setUp(self) -> None:
        """Prepare an unstarted harness and view model."""
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.log = EventLog(Path(self.folder.name) / "events.csv")
        self.addCleanup(self.log.close)
        self.harness = Harness(stub_specs(), self.log)
        self.console = HarnessConsole(self.harness)
        self.addCleanup(self.console.deleteLater)

    def test_initial_snapshot_and_status_copies(self) -> None:
        """Show seven starting processes using independent rows."""
        rows = self.harness.module_statuses
        self.assertEqual(len(rows), 7)
        self.assertEqual(tuple(row["name"] for row in rows), MODULE_NAMES)
        self.assertEqual({r["state"] for r in rows}, {"STARTING"})
        rows[0]["state"] = "BROKEN"
        self.assertEqual(
            self.harness.module_statuses[0]["state"], "STARTING"
        )
        self.assertEqual(self.console.snapshot["time"], "05:00:00")
        self.assertEqual(self.console.snapshot["state"], "PAUSED")
        self.assertIn("every module", self.harness.hold_reason)
        self.assertEqual(self.harness.startup_timed_out_modules, ())
        self.assertEqual(self.console.snapshot["log_path"],
                         str(self.log.path.resolve()))
        self.assertFalse(self.harness.show_window(TRAIN_MODEL))
        self.assertFalse(self.harness.show_window("unknown"))

    def test_events_wait_for_one_bounded_batch(self) -> None:
        """Avoid per-event QML changes even when the queue overflows."""
        notifications = []
        self.console.events.countChanged.connect(
            lambda: notifications.append(True)
        )
        for i in range(MAX_EVENTS + 5):
            self.harness.eventLogged.emit(
                TRAIN_MODEL, "TICK_REJECTED", str(i)
            )
        self.assertEqual(self.console.events.count, 0)
        self.console.refresh()
        model = self.console.events
        self.assertEqual(notifications, [True])
        self.assertEqual(model.count, MAX_EVENTS)
        self.assertEqual(model.row(0)["detail"], "5")
        self.assertTrue(model.row(0)["fault"])
        self.assertEqual(model.row(0)["source"], "Train Model")
        self.assertEqual(model.data(QModelIndex()), None)
        self.harness.eventLogged.emit(TRAIN_MODEL, "MODULE_EXITED",
                                      "exit code 0")
        self.console.refresh()
        self.assertEqual(model.count, MAX_EVENTS)
        self.assertFalse(model.row(MAX_EVENTS - 1)["fault"])
        self.assertEqual(model.row(0)["detail"], "6")

    def test_exit_without_code_is_a_fault(self) -> None:
        """Distinguish abnormal exits from a clean zero exit."""
        for detail in ("exit code 3", "crashed", "", "no exit code"):
            self.harness.eventLogged.emit(
                TRAIN_MODEL, "MODULE_EXITED", detail
            )
        self.console.refresh()
        self.assertTrue(all(
            self.console.events.row(i)["fault"] for i in range(4)
        ))

    def test_outputs_are_selected_bounded_and_throttled(self) -> None:
        """Format opaque outputs at most twice a second."""
        with (
            patch("common.harness.console.time.monotonic") as now,
            patch.object(Harness, "outputs",
                         new_callable=PropertyMock) as outputs,
        ):
            now.return_value = 100.0
            outputs.return_value = {}
            console = HarnessConsole(self.harness)
            self.addCleanup(console.deleteLater)
            console.select_module(TRAIN_MODEL)
            outputs.return_value = {
                TRAIN_MODEL: {"arbitrary": "x" * (MAX_OUTPUT_CHARS * 2)}
            }
            now.return_value = 100.4
            console.refresh()
            self.assertEqual(console.output_text, "—")
            now.return_value = 100.5
            console.refresh()
            self.assertIn("truncated", console.output_text)
            self.assertLessEqual(len(console.output_text),
                                 MAX_OUTPUT_CHARS + 20)
            console.select_module(CTC_OFFICE)
            outputs.return_value = {CTC_OFFICE: {"opaque": [1, 2]}}
            now.return_value = 100.9
            console.refresh()
            self.assertIn("truncated", console.output_text)
            now.return_value = 101.0
            console.refresh()
            self.assertEqual(json.loads(console.output_text),
                             {"opaque": [1, 2]})

    def test_metrics_publish_only_on_refresh_and_expire(self) -> None:
        """Keep recent mean and maximum separate from tick emission."""
        with patch("common.harness.console.time.monotonic") as now:
            now.return_value = 200.0
            self.harness.tickCompleted.emit(1, 0.001)
            self.harness.tickCompleted.emit(2, 0.003)
            self.assertEqual(self.console.snapshot["mean_ms"], "—")
            self.console.refresh()
            self.assertEqual(self.console.snapshot["mean_ms"], "2.00")
            self.assertEqual(self.console.snapshot["max_ms"], "3.00")
            now.return_value = 206.0
            self.console.refresh()
            self.assertEqual(self.console.snapshot["mean_ms"], "—")

    def test_source_and_frozen_resource_paths(self) -> None:
        """Resolve QML through the same helper in both builds."""
        self.assertTrue(resource_path("common/harness/ui/Main.qml").is_file())
        with patch.object(sys, "_MEIPASS", "/tmp/test-bundle", create=True):
            self.assertEqual(resource_path("common/harness/ui/Main.qml"),
                             Path("/tmp/test-bundle/common/harness/ui/"
                                  "Main.qml"))


class ConsoleFaultRunTest(unittest.TestCase):
    """Expose startup and faults without interpreting output fields."""

    @classmethod
    def setUpClass(cls) -> None:
        """Script each fault into a different moment of the same run."""
        cls.folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.folder.cleanup)
        cls.log = EventLog(Path(cls.folder.name) / "events.csv")
        cls.addClassCleanup(cls.log.close)
        cls.harness = Harness(stub_specs({
            CTC_OFFICE: ["--run-on-ready", "--speedup-at-tick", "0"],
            TRAIN_MODEL: ["--ready-delay-ms", "600",
                          "--reject-at-tick", "2"],
            TRACK_MODEL: ["--delay-ms", "1600", "--delay-at-tick", "4"],
            TRAIN_CONTROLLER_SW: ["--exit-at-tick", "8"],
        }), cls.log, startup_timeout_s=0.3)
        cls.addClassCleanup(cls.harness.stop)
        cls.console = HarnessConsole(cls.harness)
        cls.addClassCleanup(cls.console.deleteLater)
        cls.snapshots = []
        cls.console.snapshotChanged.connect(
            lambda: cls.snapshots.append(cls.console.snapshot)
        )
        cls.harness.start()
        if not wait_until(
            lambda: TRAIN_MODEL in cls.harness.startup_timed_out_modules
        ):
            raise AssertionError("No startup timeout")
        cls.startup_tick = cls.harness.clock.tick_count
        if not wait_until(lambda: TRACK_MODEL in cls.harness.late_modules):
            raise AssertionError("No late reply")
        cls.late_statuses = cls.harness.module_statuses
        cls.late_reason = cls.harness.hold_reason
        cls.show_sent = cls.console.show_window(CTC_OFFICE)
        if not wait_until(lambda: TRAIN_CONTROLLER_SW
                          in cls.harness.down_modules):
            raise AssertionError("No module crash")
        if not wait_until(lambda: any(
            r["state"] == "EXITED" for r in cls.console.modules
        )):
            raise AssertionError("No exit in console")
        cls.console.refresh()

    def test_startup_timeout_names_the_loading_module(self) -> None:
        """Hold at tick zero and name readiness stragglers."""
        self.assertEqual(self.startup_tick, 0)
        self.assertTrue(any(
            "Train Model" in s["startup_timeout"] for s in self.snapshots
        ))
        self.assertEqual(self.harness.startup_timed_out_modules, ())

    def test_late_reply_pauses_and_names_the_module(self) -> None:
        """Observe the late state while its reply is still missing."""
        row = next(r for r in self.late_statuses
                   if r["name"] == TRACK_MODEL)
        self.assertEqual(row["state"], "LATE")
        self.assertIn(TRACK_MODEL, self.late_reason)
        self.assertTrue(any(
            s["state"] == "PAUSED" and "Track Model" in s["hold"]
            for s in self.snapshots
        ))

    def test_rejection_and_crash_keep_event_time(self) -> None:
        """Retain the rejected tick and nonzero crash exit code."""
        rows = [self.console.events.row(i)
                for i in range(self.console.events.count)]
        for event in ("TICK_REJECTED", "REPLY_LATE", "MODULE_EXITED"):
            matching = [r for r in rows if r["eventName"] == event]
            self.assertTrue(matching)
            self.assertTrue(all(r["fault"] for r in matching))
        rejected = next(r for r in rows
                        if r["eventName"] == "TICK_REJECTED")
        self.assertEqual(rejected["tick"], "2")
        self.assertEqual(rejected["time"], "05:00:00")
        crashed = next(r for r in self.console.modules
                       if r["name"] == TRAIN_CONTROLLER_SW)
        self.assertEqual(crashed["state"], "EXITED")
        self.assertEqual(crashed["exit_text"], "exit code 3")
        self.assertIsInstance(crashed["pid"], int)
        self.assertIn(TRAIN_CONTROLLER_SW, self.harness.hold_reason)
        self.assertFalse(self.harness.show_window(TRAIN_CONTROLLER_SW))

    def test_show_is_additive_and_stubs_ignore_it(self) -> None:
        """Accept SHOW without a protocol error or duplicate reply."""
        self.assertTrue(self.show_sent)
        events = {self.console.events.row(i)["eventName"]
                  for i in range(self.console.events.count)}
        self.assertNotIn("PROTOCOL_ERROR", events)
        self.assertNotIn("UNEXPECTED_REPLY", events)


if __name__ == "__main__":
    unittest.main()
