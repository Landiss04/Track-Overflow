"""Exercise the QML window in an isolated offscreen GUI process."""

from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

from PySide6.QtCore import (
    QEventLoop,
    QObject,
    Qt,
    QtMsgType,
    qInstallMessageHandler,
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest

from common.harness.console import HarnessConsole, WINDOW_TITLE
from common.harness.core import Harness
from common.harness.modules import (
    CTC_OFFICE,
    TRACK_MODEL,
    TRAIN_CONTROLLER_SW,
    TRAIN_MODEL,
    stub_specs,
)
from common.harness.window import HarnessWindow
from utils.event_log import EventLog

_APP = QGuiApplication(sys.argv[:1])
_APP.setApplicationName("TrackOverflow")


def wait_until(condition, timeout_s: float = 15.0) -> bool:
    """Pump GUI events until a condition holds or time runs out."""
    deadline = time.monotonic() + timeout_s
    while not condition():
        if time.monotonic() >= deadline:
            return False
        _APP.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
        time.sleep(0.001)
    return True


class WindowProbe(unittest.TestCase):
    """Verify that actual QML consumes state from a faulted stub run."""

    def test_window(self) -> None:
        """Render, inspect faults and confirm with the keyboard."""
        warnings = []

        def record(kind, context, text) -> None:
            if kind in (
                QtMsgType.QtWarningMsg,
                QtMsgType.QtCriticalMsg,
                QtMsgType.QtFatalMsg,
            ):
                warnings.append(f"{context.file}: {text}")

        previous = qInstallMessageHandler(record)
        self.addCleanup(qInstallMessageHandler, previous)
        with tempfile.TemporaryDirectory() as folder:
            with EventLog(Path(folder) / "events.csv") as log:
                harness = Harness(stub_specs({
                    CTC_OFFICE: ["--run-on-ready",
                                 "--speedup-at-tick", "0"],
                    TRAIN_MODEL: ["--ready-delay-ms", "600",
                                  "--reject-at-tick", "2"],
                    TRACK_MODEL: ["--delay-ms", "1600",
                                  "--delay-at-tick", "4"],
                    TRAIN_CONTROLLER_SW: ["--exit-at-tick", "8"],
                }), log, startup_timeout_s=0.3)
                console = HarnessConsole(harness)
                window = HarnessWindow(_APP, console)
                try:
                    self.assertEqual(window.root.title(), WINDOW_TITLE)
                    self.assertTrue(window.root.isVisible())
                    self.assertEqual(len(console.modules), 7)
                    self.assertEqual(
                        {r["state"] for r in console.modules}, {"STARTING"}
                    )
                    scroll = window.root.findChild(
                        QObject, "moduleScroll"
                    )
                    window.root.requestActivate()
                    _APP.processEvents()
                    for _ in range(20):
                        QTest.keyClick(window.root, Qt.Key.Key_Tab)
                        if scroll.property("activeFocus"):
                            break
                    self.assertTrue(scroll.property("activeFocus"))
                    self.assertTrue(scroll.property("visualFocus"))
                    snapshots = []
                    console.snapshotChanged.connect(
                        lambda: snapshots.append(console.snapshot)
                    )
                    console.select_module(TRAIN_MODEL)
                    harness.start()
                    self.assertTrue(wait_until(lambda: any(
                        "Train Model" in s["startup_timeout"]
                        for s in snapshots
                    )))
                    scroll.forceActiveFocus(Qt.FocusReason.TabFocusReason)
                    content = scroll.property("contentItem")
                    QTest.keyClick(window.root, Qt.Key.Key_Down)
                    self.assertGreaterEqual(content.property("contentY"), 0)
                    self.assertTrue(wait_until(lambda: any(
                        r["name"] == TRACK_MODEL and r["state"] == "LATE"
                        for r in console.modules
                    )))
                    self.assertEqual(console.snapshot["state"], "PAUSED")
                    self.assertIn("Track Model", console.snapshot["hold"])
                    self.assertTrue(console.show_window(CTC_OFFICE))
                    self.assertTrue(wait_until(lambda: any(
                        r["name"] == TRAIN_CONTROLLER_SW
                        and r["state"] == "EXITED"
                        for r in console.modules
                    )))
                    rows = [console.events.row(i)
                            for i in range(console.events.count)]
                    for event in (
                        "TICK_REJECTED", "REPLY_LATE", "MODULE_EXITED"
                    ):
                        self.assertTrue(any(
                            r["eventName"] == event and r["fault"]
                            for r in rows
                        ))
                    self.assertNotEqual(console.output_text, "—")
                    inspector = window.root.findChild(
                        QObject, "outputInspector"
                    )
                    self.assertEqual(inspector.property("text"),
                                     console.output_text)
                    self.assertTrue(window.root.grabWindow().save(
                        "/tmp/harness-window-preview.png"
                    ))
                    ended = []
                    console.endRunRequested.connect(
                        lambda: ended.append(True)
                    )
                    dialog = window.root.findChild(QObject, "endRunDialog")
                    cancel = window.root.findChild(QObject, "cancelEndRun")
                    confirm = window.root.findChild(
                        QObject, "confirmEndRun"
                    )
                    self.assertFalse(window.root.close())
                    self.assertTrue(wait_until(
                        lambda: dialog.property("visible")
                    ))
                    self.assertTrue(cancel.property("activeFocus"))
                    self.assertTrue(cancel.property("visualFocus"))
                    QTest.keyClick(window.root, Qt.Key.Key_Space)
                    self.assertTrue(wait_until(
                        lambda: not dialog.property("visible")
                    ))
                    self.assertEqual(ended, [])
                    self.assertTrue(window.root.isVisible())
                    window.root.close()
                    self.assertTrue(wait_until(
                        lambda: dialog.property("visible")
                    ))
                    QTest.keyClick(window.root, Qt.Key.Key_Escape)
                    self.assertTrue(wait_until(
                        lambda: not dialog.property("visible")
                    ))
                    window.root.close()
                    self.assertTrue(wait_until(
                        lambda: dialog.property("visible")
                    ))
                    confirm.forceActiveFocus()
                    QTest.keyClick(window.root, Qt.Key.Key_Space)
                    self.assertTrue(wait_until(lambda: ended == [True]))
                finally:
                    harness.stop()
                    window.close()
                self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
