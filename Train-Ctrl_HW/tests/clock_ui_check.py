"""Test UI clock controls and output rows, in a real offscreen window.

Run by ``test_harness_clock.py`` in its own process, so it can own a
``QGuiApplication``. Clicks are real mouse events on the controls.
"""

from pathlib import Path
import sys

from PySide6.QtCore import QPointF, QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow  # noqa: F401: register Qt wrappers
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "TrainModel")]

from train_model.harness import TestHarnessState  # noqa: E402
from train_model.link import LinkError, LocalLink  # noqa: E402
from train_model.state import TrainModelState  # noqa: E402
from ui.theme import build_theme  # noqa: E402


def walk(item):
    yield item
    for child in item.childItems():
        yield from walk(child)


def main():
    app = QGuiApplication([])
    state = TrainModelState()
    link = LocalLink(state)
    harness = TestHarnessState(link)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("theme", build_theme())
    engine.rootContext().setContextProperty("harness", harness)
    engine.load(QUrl.fromLocalFile(
        str(ROOT / "TrainModel/ui/TestMain.qml")))
    window = engine.rootObjects()[0]
    QTest.qWait(50)

    def items():
        return list(walk(window.contentItem()))

    def named(name):
        return next(x for x in items() if x.objectName() == name)

    def click(item):
        # Scroll the page so the control is on screen, then click it.
        view = item.parentItem()
        while view.property("contentY") is None:
            view = view.parentItem()
        top = item.mapToItem(view.property("contentItem"), QPointF(0, 0))
        bottom = view.property("contentHeight") - view.height()
        view.setProperty("contentY", min(max(0.0, top.y() - 100), bottom))
        QTest.qWait(10)
        QTest.mouseClick(
            window, Qt.LeftButton, Qt.NoModifier,
            item.mapToScene(item.boundingRect().center()).toPoint(),
        )
        QTest.qWait(10)

    def segment(text):
        toggle = named("speedToggle")
        return next(x for x in walk(toggle)
                    if x.property("text") == text and hasattr(x, "clicked"))

    # The speed toggle lists the clock's speeds and sets them.
    assert [x.property("text") for x in walk(named("speedToggle"))
            if hasattr(x, "clicked")] == ["1x", "10x"]
    assert named("speedToggle").property("currentIndex") == 0
    click(segment("10x"))
    assert harness.speed == 10
    assert named("speedToggle").property("currentIndex") == 1
    assert harness.dt == 0.1
    click(segment("1x"))
    assert harness.speed == 1
    assert named("speedToggle").property("currentIndex") == 0

    # Output rows are created once; ticks update their values in place.
    harness.setInput("power_command", 100000)
    assert harness.sendInputs()
    rows = {x.objectName(): x for x in items()
            if x.objectName().startswith("output-")}
    assert len(rows) == len(harness.outputDefinitions)
    speed_row = rows["output-position_offset"]
    before = speed_row.property("value")
    for _ in range(3):
        harness.advanceTick()
    QTest.qWait(10)
    after = {x.objectName(): x for x in items()
             if x.objectName().startswith("output-")}
    assert all(after[name] == row for name, row in rows.items())
    assert speed_row.property("value") > before
    assert speed_row.property("value") == harness.outputValues[
        "position_offset"]

    # Clock drift: none while every tick is a step; a lost step shows
    # at the next 30-tick check, with a warning, until a reset.
    drift = named("clockDrift")
    warning = named("driftWarning")
    for _ in range(30):
        harness.advanceTick()
    QTest.qWait(10)
    assert drift.property("value") == "0 ticks (0.0 s)"
    assert not warning.isVisible()

    def lose_reply(*args, **kwargs):
        del link.step  # back to the real step for the next tick
        raise LinkError("Train Model did not respond")

    link.step = lose_reply
    for _ in range(30):
        harness.advanceTick()
    QTest.qWait(10)
    assert drift.property("value") == "1 tick (0.1 s)"
    assert warning.isVisible()
    harness.resetModule()
    QTest.qWait(10)
    assert drift.property("value") == "0 ticks (0.0 s)"
    assert not warning.isVisible()
    del engine
    del app


if __name__ == "__main__":
    main()
