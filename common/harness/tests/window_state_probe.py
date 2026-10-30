"""Check the window's focus and event selection in a GUI process.

Run by ``test_harness_window_state.py`` in a process of its own, for
the reason ``window_probe.py`` is: other suites create a
``QCoreApplication`` at import time.

A stand-in harness feeds the real console and QML, so status updates
and events come exactly when the probe sends them:

- a status update for one module must leave keyboard focus where it
  is, on another module's Show window button;
- rollover, the event list dropping its oldest events at its cap, must
  keep the selection on the same event, or clear it if that event is
  dropped, never move it to another.
"""

from __future__ import annotations

import sys
import time
import unittest
from typing import Any, cast

from PySide6.QtCore import (
    QEventLoop,
    QObject,
    Qt,
    QtMsgType,
    Signal,
    qInstallMessageHandler,
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickItem

from common.harness import console as console_module
from common.harness.console import MODULE_LABELS, HarnessConsole
from common.harness.window import HarnessWindow
from utils.system_clock import SystemClock

_APP = QGuiApplication(sys.argv[:1])
_APP.setApplicationName("TrackOverflow")

NAMES = tuple(MODULE_LABELS)
# A small cap, so rollover comes after a few events.
EVENT_CAP = 10


def settle(seconds: float = 0.35) -> None:
    """Pump GUI events past a console refresh."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        _APP.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)


def find_item(root: Any, name: str) -> QQuickItem | None:
    """Return the visual item named ``name``, Repeater rows included."""
    stack = [root.contentItem()]
    while stack:
        item = stack.pop()
        if item.objectName() == name:
            return item
        stack.extend(item.childItems())
    return None


class _StandInHarness(QObject):
    """What the console reads of a harness, set by the probe."""

    eventLogged = Signal(str, str, str)
    tickCompleted = Signal(int, float)

    def __init__(self) -> None:
        super().__init__()
        self.clock = SystemClock()
        self.states = {name: "READY" for name in NAMES}
        self.pids = {name: 100 + n for n, name in enumerate(NAMES)}
        self.hold_reason: str | None = None
        self.ready_modules = NAMES
        self.startup_timed_out_modules: tuple[str, ...] = ()
        self.dropped_ticks = 0
        self.log_path = "events.csv"
        self.outputs: dict[str, Any] = {}

    @property
    def module_statuses(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            {
                "name": name,
                "state": self.states[name],
                "pid": self.pids[name],
                "exit": None,
            }
            for name in NAMES
        )

    def show_window(self, _module: str) -> bool:
        return True

    def log(self, count: int, first: int) -> None:
        for n in range(first, first + count):
            self.eventLogged.emit("harness", f"EVENT_{n}", f"detail {n}")


class WindowStateProbe(unittest.TestCase):
    """Focus and selection survive updates the operator did not make."""

    def setUp(self) -> None:
        self.warnings: list[str] = []

        def record(kind: QtMsgType, context: Any, text: str) -> None:
            if kind in (
                QtMsgType.QtWarningMsg,
                QtMsgType.QtCriticalMsg,
                QtMsgType.QtFatalMsg,
            ):
                self.warnings.append(f"{context.file}: {text}")

        previous = qInstallMessageHandler(record)
        self.addCleanup(qInstallMessageHandler, previous)
        self.harness = _StandInHarness()
        self.console = HarnessConsole(cast(Any, self.harness))
        self.window = HarnessWindow(_APP, self.console)
        # Typed loosely: QML and Qt properties are dynamic.
        self.root = cast(Any, self.window.root)
        self.events = cast(Any, self.console.events)
        self.root.requestActivate()
        settle()

    def tearDown(self) -> None:
        self.window.close()
        self.assertEqual(self.warnings, [])

    def test_status_update_keeps_focus(self) -> None:
        name = f"show-{NAMES[2]}"
        button = find_item(self.root, name)
        assert button is not None
        button.forceActiveFocus(Qt.FocusReason.TabFocusReason)
        settle()
        self.assertTrue(button.property("activeFocus"))
        # Another module's status changes.
        self.harness.states[NAMES[5]] = "LATE"
        self.harness.pids[NAMES[4]] = 999
        settle()
        modules = cast(Any, self.console.modules)
        self.assertEqual(modules[5]["state"], "LATE", "update not shown")
        self.assertIs(find_item(self.root, name), button)
        self.assertTrue(button.property("activeFocus"))
        self.assertIs(self.root.activeFocusItem(), button)
        # The changed row is updated in place.
        late = find_item(self.root, f"show-{NAMES[5]}")
        assert late is not None
        self.assertTrue(late.property("enabled"))
        self.harness.states[NAMES[5]] = "DOWN"
        settle()
        self.assertFalse(late.property("enabled"))
        self.assertTrue(button.property("activeFocus"))

    def test_rollover_keeps_or_clears_the_selection(self) -> None:
        cap = console_module.MAX_EVENTS
        console_module.MAX_EVENTS = EVENT_CAP
        self.addCleanup(setattr, console_module, "MAX_EVENTS", cap)
        events: Any = self.root.findChild(QObject, "eventList")
        panel = events.parent()
        self.harness.log(EVENT_CAP, 0)
        settle()
        # The operator selects EVENT_6 and inspects it.
        panel.setProperty("following", False)
        events.setProperty("currentIndex", 6)
        panel.setProperty("inspecting", True)
        settle()

        def selected() -> str | None:
            index = events.property("currentIndex")
            name: str | None = self.events.row(index).get("eventName")
            return name

        self.assertEqual(selected(), "EVENT_6")
        # Three older events drop out: the selection follows EVENT_6.
        self.harness.log(3, EVENT_CAP)
        settle()
        self.assertEqual(events.property("currentIndex"), 3)
        self.assertEqual(selected(), "EVENT_6")
        self.assertTrue(panel.property("inspecting"))
        # EVENT_6 drops out: the selection clears, and moves nowhere.
        self.harness.log(5, EVENT_CAP + 3)
        settle()
        self.assertEqual(self.events.count, EVENT_CAP)
        self.assertEqual(events.property("currentIndex"), -1)
        self.assertIsNone(selected())
        self.assertFalse(panel.property("inspecting"))


if __name__ == "__main__":
    unittest.main()
