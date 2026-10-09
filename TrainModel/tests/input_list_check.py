"""The test UI's input list scrolls in place and wraps; outputs are trimmed.

Failures are set only in the Train Model window, so the test UI has no
failure controls.
"""

from pathlib import Path
import sys

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QUrl
from PySide6.QtGui import (
    QGuiApplication, QInputDevice, QPointingDevice, QWheelEvent,
)
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow  # noqa: F401: register Qt wrappers
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "TrainModel")]

from train_model.harness import TestHarnessState  # noqa: E402
from train_model.link import LocalLink  # noqa: E402
from train_model.state import FAILURE_MODES, TrainModelState  # noqa: E402
from ui.theme import build_theme  # noqa: E402

# What the Train Controller and the Track Model act on, and no more.
EXPECTED_OUTPUTS = {
    "position_block", "position_offset", "passenger_capacity",
}


def walk(item):
    yield item
    for child in item.childItems():
        yield from walk(child)


def wheel(window, item, notches):
    """Send one wheel event of ``notches`` notches over ``item``."""
    centre = item.mapToScene(item.boundingRect().center())
    event = QWheelEvent(
        QPointF(centre), QPointF(window.mapToGlobal(centre.toPoint())),
        QPoint(0, 0), QPoint(0, 120 * notches), Qt.NoButton, Qt.NoModifier,
        Qt.NoScrollPhase, False,
    )
    QGuiApplication.sendEvent(window, event)
    QTest.qWait(200)


def touchpad_swipe(window, item, pixels):
    """Send a two-finger swipe of ``pixels`` pixels over ``item``."""
    pad = QPointingDevice(
        "touchpad", 1, QInputDevice.DeviceType.TouchPad,
        QPointingDevice.PointerType.Finger,
        QInputDevice.Capability.Position | QInputDevice.Capability.Scroll
        | QInputDevice.Capability.PixelScroll, 2, 3,
    )
    centre = item.mapToScene(item.boundingRect().center())
    steps = 10
    for phase, delta in ([(Qt.ScrollBegin, 0)]
                         + [(Qt.ScrollUpdate, pixels // steps)] * steps
                         + [(Qt.ScrollEnd, 0)]):
        event = QWheelEvent(
            QPointF(centre), QPointF(window.mapToGlobal(centre.toPoint())),
            QPoint(0, delta), QPoint(0, 2 * delta), Qt.NoButton,
            Qt.NoModifier, phase, False, Qt.MouseEventNotSynthesized, pad,
        )
        QGuiApplication.sendEvent(window, event)
        QTest.qWait(10)
    QTest.qWait(200)


def on_screen(item):
    """Whether ``item`` lies inside every clipping parent: seen."""
    rect = item.mapRectToScene(QRectF(0, 0, item.width(), item.height()))
    seen = QRectF(rect)
    parent = item.parentItem()
    while parent is not None:
        if parent.clip():
            seen = seen.intersected(parent.mapRectToScene(
                QRectF(0, 0, parent.width(), parent.height())))
        parent = parent.parentItem()
    return seen.height() >= 0.9 * rect.height() and seen.width() > 0


def check_keyboard_focus(window, items):
    """Tab never focuses a control out of sight; a scroll keeps focus."""
    def editor(name):
        row = next(x for x in items if x.objectName() == "input-" + name)
        return next(x for x in walk(row) if x.objectName() == "valueEditor")

    editor("power_command").forceActiveFocus()
    stops = set()
    for key_modifier in (Qt.NoModifier, Qt.ShiftModifier):
        for _ in range(40):
            QTest.keyClick(window, Qt.Key_Tab, key_modifier)
            QTest.qWait(150)
            focus = window.activeFocusItem()
            assert on_screen(focus), focus
            stops.add(focus)
    # Every input row and run control was reached.
    rows = {x.objectName() for x in items
            if x.objectName().startswith("input-")}
    reached = set()
    for focus in stops:
        parent = focus
        while parent is not None and parent.objectName() not in rows:
            parent = parent.parentItem()
        if parent is not None:
            reached.add(parent.objectName())
    assert reached == rows, rows - reached

    # Scrolling while editing keeps the edit and its focus.
    speed = editor("commanded_speed")
    speed.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_A, Qt.ControlModifier)
    QTest.keyClick(window, Qt.Key_1)
    input_list = next(x for x in items if x.objectName() == "inputList")
    wheel(window, input_list, -2)
    assert window.activeFocusItem() is speed
    QTest.keyClick(window, Qt.Key_2)
    QTest.keyClick(window, Qt.Key_Return)
    assert speed.property("text") == "12"


def check_rejection_in_sight(window, harness, items):
    """A refused send scrolls its reason into sight; the bar shows."""
    column = next(x for x in items if x.objectName() == "rightColumn")
    bar = next(x for x in walk(column)
               if x.property("orientation") == Qt.Vertical
               and x.property("size") is not None)
    # Shown while idle, not only while scrolling: Run control goes on
    # below the fold.
    assert bar.isVisible() and bar.opacity() > 0
    harness.setInput("power_command", -1.0)
    assert not harness.sendInputs()
    QTest.qWait(200)
    error = next(x for x in walk(window.contentItem())
                 if x.objectName() == "inputError")
    assert error.isVisible() and on_screen(error)
    harness.setInput("power_command", 0.0)
    assert harness.sendInputs()


def main():
    app = QGuiApplication([])
    state = TrainModelState()
    harness = TestHarnessState(LocalLink(state))
    engine = QQmlApplicationEngine()
    for name, value in [("theme", build_theme()), ("trainModel", state),
                        ("harness", harness)]:
        engine.rootContext().setContextProperty(name, value)
    engine.load(QUrl.fromLocalFile(str(ROOT / "TrainModel/ui/TestMain.qml")))
    window = engine.rootObjects()[0]
    QTest.qWait(100)
    items = list(walk(window.contentItem()))

    inputs = next(x for x in items if x.objectName() == "inputList")
    count = inputs.property("count")
    shown = inputs.property("pathItemCount")
    assert count == len(harness.inputDefinitions)
    # Only the rows that fit are on the path, and they fit.
    assert 1 <= shown < count, (shown, count)
    assert shown * inputs.property("slot") <= inputs.height()
    # Every row stays alive off the path, so no edit is lost to a scroll.
    rows = [x for x in items if x.objectName().startswith("input-")]
    assert len(rows) == count

    # Wraps both ways: before the first row comes the last.
    assert inputs.property("currentIndex") == 0
    wheel(window, inputs, 1)
    assert inputs.property("currentIndex") == count - 1
    wheel(window, inputs, -1)
    assert inputs.property("currentIndex") == 0
    # A touchpad scrolls it too, one row per row height of travel.
    slot = inputs.property("slot")
    touchpad_swipe(window, inputs, -round(2.5 * slot))
    assert inputs.property("currentIndex") == 2
    touchpad_swipe(window, inputs, round(2.5 * slot))
    assert inputs.property("currentIndex") == 0
    for _ in range(count):
        inputs.incrementCurrentIndex()
    QTest.qWait(300)
    assert inputs.property("currentIndex") == 0

    outputs = {x.objectName().removeprefix("output-") for x in items
               if x.objectName().startswith("output-")}
    assert outputs == EXPECTED_OUTPUTS, outputs

    titles = {x.property("title") for x in items}
    assert "Failure modes" not in titles, titles
    texts = {x.property("text") for x in items}
    assert not texts & set(FAILURE_MODES), texts & set(FAILURE_MODES)

    track = next(x for x in items if x.objectName() == "track")
    assert track.property("value") == "Blue Line"
    limiter = next(x for x in items if x.objectName() == "speedLimiter")
    assert limiter.property("value") == "31.1 mph cap"
    dwell = next(x for x in items if x.objectName() == "dwell")
    assert dwell.property("value") == "\u2014"

    check_keyboard_focus(window, items)
    check_rejection_in_sight(window, harness, items)

    del engine
    del app


if __name__ == "__main__":
    main()
