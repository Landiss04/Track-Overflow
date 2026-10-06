"""The test UI's input list scrolls in place and wraps; outputs are trimmed.

Failures are set only in the Train Model window, so the test UI has no
failure controls.
"""

from pathlib import Path
import sys

from PySide6.QtCore import QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QGuiApplication, QWheelEvent
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
    "emergency_brake_state", "left_door_state", "right_door_state",
    "interior_light_state", "exterior_light_state", "cabin_temp",
    "position_block", "position_offset", "actual_speed",
    "passenger_capacity", "speed_limit",
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

    del engine
    del app


if __name__ == "__main__":
    main()
