"""The test UI adds, selects and removes trains from its header.

Both windows run here on one fleet, the test UI over an in-process
link, so a train the test UI adds shows up in the Train Model window's
own selector.
"""

from pathlib import Path
import sys

from PySide6.QtCore import QtMsgType, QUrl, Qt, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow  # noqa: F401: register Qt wrappers
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "TrainModel")]

from train_model.fleet import TrainModelFleet  # noqa: E402
from train_model.harness import TestHarnessState  # noqa: E402
from train_model.link import LocalLink  # noqa: E402
from ui.theme import build_theme  # noqa: E402


def walk(item):
    yield item
    for child in item.childItems():
        yield from walk(child)


def main():
    warnings = []

    def on_message(kind, _context, message):
        if kind != QtMsgType.QtDebugMsg:
            warnings.append(message)

    qInstallMessageHandler(on_message)
    app = QGuiApplication([])
    fleet = TrainModelFleet()
    fleet.add("T-1")
    harness = TestHarnessState(LocalLink(fleet))
    engine = QQmlApplicationEngine()
    for name, value in [("theme", build_theme()), ("fleet", fleet),
                        ("harness", harness)]:
        engine.rootContext().setContextProperty(name, value)
    engine.load(QUrl.fromLocalFile(str(ROOT / "TrainModel/ui/TestMain.qml")))
    engine.load(QUrl.fromLocalFile(str(ROOT / "TrainModel/ui/Main.qml")))
    test_ui, model_window = engine.rootObjects()
    QTest.qWait(100)

    def named(window, name):
        return next(x for x in walk(window.contentItem())
                    if x.objectName() == name)

    def click(name):
        item = named(test_ui, name)
        assert item.isEnabled(), name
        QTest.mouseClick(
            test_ui, Qt.LeftButton, Qt.NoModifier,
            item.mapToScene(item.boundingRect().center()).toPoint(),
        )
        QTest.qWait(50)

    def selector(window):
        field = named(window, "trainSelector")
        return next(x for x in walk(field)
                    if x.objectName() == "selectEditor")

    def row_value(name):
        return named(test_ui, "input-" + name).property("value")

    # One train: it cannot be removed.
    assert not named(test_ui, "removeTrain").isEnabled()
    assert selector(test_ui).property("displayText") == "T-1"

    # Added from the header: selected here, listed in the other window.
    click("addTrain")
    assert harness.trainIds == ["T-1", "T-2"]
    assert selector(test_ui).property("displayText") == "T-2"
    assert selector(model_window).property("count") == 2
    assert named(test_ui, "removeTrain").isEnabled()

    # Each train's rows are its own.
    harness.setInput("power_command", 200_000.0)
    assert row_value("power_command") == 200.0
    combo = selector(test_ui)
    combo.setProperty("currentIndex", 0)
    combo.activated.emit(0)
    QTest.qWait(50)
    assert harness.selectedTrain == "T-1"
    assert row_value("power_command") == 0.0

    # Every train moves on a send, whichever is shown.
    assert harness.sendInputs(), harness.inputError
    for _ in range(10):
        harness.advanceTick()
    assert fleet.get("T-2").outputs().controller.actual_speed_mps > 0

    # Removed from the header: the next train is selected.
    click("removeTrain")
    assert harness.trainIds == ["T-2"]
    assert selector(test_ui).property("displayText") == "T-2"
    assert selector(model_window).property("count") == 1
    assert not named(test_ui, "removeTrain").isEnabled()

    del engine
    del app
    assert not warnings, warnings


if __name__ == "__main__":
    main()
