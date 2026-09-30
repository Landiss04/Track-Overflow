"""Native QML synchronization regression, isolated from QCoreApplication."""

from pathlib import Path
import sys

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow  # noqa: F401: register Qt wrappers
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "TrainModel")]

from train_model.harness import TestHarnessState  # noqa: E402
from train_model.state import TrainModelState  # noqa: E402
from ui.theme import build_theme  # noqa: E402


def walk(item):
    yield item
    for child in item.childItems():
        yield from walk(child)


def main():
    app = QGuiApplication([])
    state = TrainModelState()
    harness = TestHarnessState(state)
    engine = QQmlApplicationEngine()
    for name, value in [("theme", build_theme()), ("trainModel", state),
                        ("harness", harness)]:
        engine.rootContext().setContextProperty(name, value)
    engine.load(QUrl.fromLocalFile(str(ROOT / "TrainModel/ui/Main.qml")))
    assert engine.rootObjects()
    window = engine.rootObjects()[0]
    QTest.qWait(50)

    def items():
        return list(walk(window.contentItem()))

    def click(text, root=None):
        matches = [x for x in walk(root or window.contentItem())
                   if x.property("text") == text and x.isVisible()
                   and hasattr(x, "clicked")]
        assert len(matches) == 1, (text, len(matches))
        item = matches[0]
        QTest.mouseClick(
            window, Qt.LeftButton, Qt.NoModifier,
            item.mapToScene(item.boundingRect().center()).toPoint(),
        )
        QTest.qWait(10)

    def row(name):
        return next(x for x in items() if x.objectName() == "input-" + name)

    # Overview apply updates the hidden test control immediately, paused.
    click("APPLY EMERGENCY BRAKE")
    click("CONFIRM")
    assert row("emergency_brake_command").property("value") is True
    assert state.snapshot["emergency_brake"]
    click("RELEASE EMERGENCY BRAKE")
    click("CONFIRM")
    assert state.snapshot["emergency_brake"]  # normal release unchanged
    click("Test harness")
    click("False", row("emergency_brake_command"))
    assert row("emergency_brake_command").property("pending")
    harness.sendInputs()
    assert row("emergency_brake_command").property("value") is False
    assert not row("emergency_brake_command").property("pending")

    # Live updates must neither recreate the editor nor destroy raw text.
    harness.setInput("power_command", 100000)
    harness.sendInputs()
    power_row = row("power_command")
    editor = next(x for x in walk(power_row)
                  if x.objectName() == "valueEditor")
    editor.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_A, Qt.ControlModifier)
    QTest.keyClick(window, Qt.Key_9)
    QTest.keyClick(window, Qt.Key_9)
    state.setFailure("engine_failure", True)
    for _ in range(3):
        harness.advanceTick()
    QTest.qWait(20)
    assert row("power_command") == power_row
    assert editor.property("activeFocus")
    assert editor.property("text") == "99"
    QTest.keyClick(window, Qt.Key_Return)
    assert harness.inputValues["power_command"] == 99
    assert power_row.property("pending")
    click("Overview")  # commit/blur without rebuilding test delegates
    harness.sendInputs()
    assert harness.inputValues["power_command"] == 0  # engine failed
    state.setFailure("engine_failure", False)
    assert harness.inputValues["power_command"] == 99
    harness.resetModule()
    QTest.qWait(10)
    assert editor.property("text") == "0"
    assert not power_row.property("pending")
    assert state.snapshot["clock"] == harness.elapsed == "00:00:00"
    del engine
    del app


if __name__ == "__main__":
    main()
