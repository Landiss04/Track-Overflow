"""Exercise QML input-to-Python signals with real keyboard/mouse events.

Run: QT_QPA_PLATFORM=offscreen .venv/bin/python tests/test_ui_components.py
"""

import os
from pathlib import Path
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest

from train_model.harness import INPUT_SPEC, TestHarnessState
from train_model.state import TrainModelState
from train_model.theme import build_theme

UI = Path(__file__).resolve().parents[1] / "ui"
APP = QGuiApplication.instance() or QGuiApplication([])


def descendants(item):
    """Walk visual children, including Repeater-created controls."""
    yield item
    for child in item.childItems():
        yield from descendants(child)


class ComponentsTest(unittest.TestCase):
    """Check actual input delivery and rejected/disabled actions."""

    def setUp(self):
        """Give each check an isolated QML engine and window."""
        self.engine = QQmlEngine()
        self.engine.rootContext().setContextProperty("theme", build_theme())
        self.warnings = []
        self.engine.warnings.connect(
            lambda errors: self.warnings.extend(e.toString() for e in errors)
        )
        self.window = QQuickWindow()
        self.window.resize(1100, 700)
        self.window.show()
        self.objects = []
        self.components = []
        self.keep_alive = []
        self.extra_windows = []

    def tearDown(self):
        """Release QML before its engine and reject runtime warnings."""
        for window in [self.window, *self.extra_windows]:
            window.close()
            window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.assertEqual(self.warnings, [])

    def make(self, name, properties=""):
        """Instantiate a component relative to the real component library."""
        component = QQmlComponent(self.engine)
        component.setData(
            ('import QtQuick\nimport "components"\n'
             + name + ' { width: 700; ' + properties + ' }').encode(),
            QUrl.fromLocalFile(str(UI / "test.qml")),
        )
        self.assertFalse(component.isError(), component.errorString())
        item = component.create()
        self.assertIsNotNone(item, component.errorString())
        item.setParentItem(self.window.contentItem())
        self.components.append(component)
        self.objects.append(item)
        QTest.qWait(20)
        return item

    def button(self, item, text):
        """Find a real control by its visible text."""
        return next(child for child in descendants(item)
                    if child.property("text") == text
                    and child.metaObject().indexOfSignal("clicked()") >= 0)

    def activate(self, item):
        """Use the keyboard path, not direct signal invocation."""
        item.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Space)
        QTest.qWait(10)

    def test_button_toggle_and_navigation(self):
        """Native controls emit once and honor disabled state."""
        for name, properties, signal, label in [
            ("AppButton", 'text: "Send"', "clicked", "Send"),
            ("SegmentedToggle", 'options: ["On", "Off"]',
             "activated", "Off"),
            ("NavRail", 'height: 150; entries: ["Main", "Test"]',
             "activated", "Test"),
            ("ModuleHeader", 'navigationEntries: ["Main", "Test"]',
             "navigationActivated", "Test"),
        ]:
            item = self.make(name, properties)
            received = []
            getattr(item, signal).connect(lambda *args: received.append(args))
            button = self.button(item, label)
            self.activate(button)
            self.assertEqual(len(received), 1, name)
            if name != "AppButton":
                self.assertEqual(received[0], (1,))
            item.setEnabled(False)
            self.activate(button)
            self.assertEqual(len(received), 1, name)
            item.setVisible(False)

    def test_value_field(self):
        """Numbers reach Python as numbers; invalid values emit nothing."""
        field = self.make("ValueField", 'kind: "float"; label: "Speed"')
        received = []
        field.committed.connect(received.append)
        editor = field.findChild(QQuickItem, "valueEditor")
        editor.forceActiveFocus()
        editor.setProperty("text", "12.5")
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertEqual(received, [12.5])
        editor.setProperty("text", "-")
        self.assertFalse(field.property("valid"))
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertEqual(received, [12.5])
        field.setProperty("kind", "int")
        editor.setProperty("text", "3.5")
        self.assertFalse(field.property("valid"))
        editor.setProperty("text", "42")
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertEqual(received[-1], 42)
        field.setProperty("kind", "string")
        editor.setProperty("text", "")
        QTest.keyClick(self.window, Qt.Key_Return)
        self.assertEqual(received[-1], "")

    def test_select_and_table(self):
        """Selections deliver backend values and whole row objects."""
        select = self.make("SelectField", '''label: "Train";
            model: [{ label: "First", id: "001" },
                    { label: "Second", id: "002" }];
            textRole: "label"; valueRole: "id"''')
        received = []
        select.committed.connect(received.append)
        editor = select.findChild(QQuickItem, "selectEditor")
        editor.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Down)
        self.assertEqual(received, ["002"])
        select.setVisible(False)
        table = self.make("DataTable", '''
            columns: [{key: "id", label: "Train", mono: true},
                      {key: "speed", label: "Speed", numeric: true}];
            rows: [{id: "001", speed: 0}, {id: "002", speed: null}]''')
        rows = []
        table.rowActivated.connect(
            lambda index, row: rows.append((index, row))
        )
        buttons = [c for c in descendants(table)
                   if c.metaObject().indexOfSignal("clicked()") >= 0]
        self.activate(buttons[1])
        self.assertEqual(rows, [(1, {"id": "002", "speed": None})])

    def test_safety_confirmation(self):
        """Only confirmation dispatches; changed state cancels stale intent."""
        safety = self.make("SafetyButton", 'label: "Emergency brake"')
        received = []
        safety.confirmed.connect(lambda: received.append(True))
        self.activate(self.button(safety, "EMERGENCY BRAKE"))
        self.assertEqual(received, [])
        self.activate(self.button(safety, "Cancel"))
        self.assertFalse(safety.property("armed"))
        self.activate(self.button(safety, "EMERGENCY BRAKE"))
        self.activate(self.button(safety, "CONFIRM"))
        self.assertEqual(received, [True])
        self.activate(self.button(safety, "EMERGENCY BRAKE"))
        safety.setProperty("applied", True)
        self.assertFalse(safety.property("armed"))
        safety.setProperty("confirmationRequired", False)
        self.activate(self.button(safety, "RELEASE EMERGENCY BRAKE"))
        self.assertEqual(received, [True, True])

    def test_signal_row_and_complete_submission(self):
        """A QML edit reaches a Python slot and the outbound payload."""
        state = TrainModelState()
        harness = TestHarnessState(state)
        row = self.make("SignalRow", '''name: "power_command";
            kind: "float"; value: 118000; editable: true''')
        row.edited.connect(
            lambda value: harness.setInput("power_command", value)
        )
        editor = row.findChild(QQuickItem, "valueEditor")
        editor.forceActiveFocus()
        editor.setProperty("text", "25000")
        QTest.keyClick(self.window, Qt.Key_Return)
        received = []
        harness.inputsSubmitted.connect(received.append)
        harness.sendInputs()
        self.assertEqual(set(received[0]), {r["name"] for r in INPUT_SPEC})
        self.assertEqual(received[0]["power_command"], 25000.0)
        self.assertIsInstance(received[0]["service_brake_command"], bool)
        self.assertIsInstance(received[0]["passengers_boarded"], int)
        send = self.make("AppButton", 'y: 150; text: "Send"')
        send.clicked.connect(harness.sendInputs)
        editor.forceActiveFocus()
        editor.setProperty("text", "25001")
        point = send.mapToScene(QPointF(40, 15)).toPoint()
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point)
        self.assertEqual(received[-1]["power_command"], 25001.0)
        harness.setInput("power_command", 10)
        self.assertEqual(received[0]["power_command"], 25000.0)

    def test_application_views(self):
        """Render both application pages with their real Python state."""
        state = TrainModelState()
        harness = TestHarnessState(state)
        self.keep_alive.extend([state, harness])
        context = self.engine.rootContext()
        context.setContextProperty("trainModel", state)
        context.setContextProperty("harness", harness)
        component = QQmlComponent(
            self.engine, QUrl.fromLocalFile(str(UI / "Main.qml"))
        )
        window = component.create()
        self.assertIsNotNone(window, component.errorString())
        self.extra_windows.append(window)
        self.components.append(component)
        QTest.qWait(100)
        screenshots = os.environ.get("UI_SCREENSHOTS")
        if screenshots:
            Path(screenshots).mkdir(parents=True, exist_ok=True)
            window.grabWindow().save(str(Path(screenshots) / "overview.png"))
        navigation = self.button(window.contentItem(), "Test harness")
        navigation.forceActiveFocus()
        QTest.keyClick(window, Qt.Key_Space)
        QTest.qWait(100)
        self.assertFalse(window.grabWindow().isNull())
        if screenshots:
            window.grabWindow().save(str(Path(screenshots) / "harness.png"))


    def test_every_component_loads(self):
        """Compile and instantiate every library file, including readouts."""
        for path in sorted((UI / "components").glob("*.qml")):
            item = self.make(path.stem)
            item.setVisible(False)


if __name__ == "__main__":
    unittest.main()
