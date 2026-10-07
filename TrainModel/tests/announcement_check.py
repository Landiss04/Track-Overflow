"""The Train Model window's announcement popup and red active failures."""

from pathlib import Path
import sys

from PySide6.QtCore import QObject, QRectF, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow  # noqa: F401: register Qt wrappers
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "TrainModel")]

from train_model.harness import TestHarnessState  # noqa: E402
from train_model.link import LocalLink  # noqa: E402
from train_model.state import TrainModelState  # noqa: E402
from ui.theme import build_theme  # noqa: E402


def walk(item):
    yield item
    for child in item.childItems():
        yield from walk(child)


def main():
    app = QGuiApplication([])
    state = TrainModelState()
    harness = TestHarnessState(LocalLink(state))
    engine = QQmlApplicationEngine()
    for name, value in [("theme", build_theme()), ("trainModel", state),
                        ("harness", harness)]:
        engine.rootContext().setContextProperty(name, value)
    engine.load(QUrl.fromLocalFile(str(ROOT / "TrainModel/ui/Main.qml")))
    window = engine.rootObjects()[0]
    QTest.qWait(50)
    popup = window.findChild(QObject, "announcementPopup")
    assert popup is not None
    assert not popup.property("visible")

    def announce(text):
        harness.setInput("announcement", text)
        assert harness.sendInputs(), harness.inputError
        QTest.qWait(50)

    def shown_height(content):
        return next(x for x in walk(content)
                    if x.objectName() == "announcementText").height()

    def shown_text():
        return next(x for x in walk(popup)
                    if x.objectName() == "announcementText").property("text")

    announce("Next stop: Station B")
    assert popup.property("visible")
    assert shown_text() == "Next stop: Station B"

    # Dismissed, the same announcement on later ticks stays dismissed.
    dismiss = next(x for x in walk(popup)
                   if x.property("text") == "Dismiss")
    dismiss.clicked.emit()
    QTest.qWait(50)
    assert not popup.property("visible")
    for _ in range(5):
        harness.advanceTick()
    QTest.qWait(50)
    assert not popup.property("visible")

    # A new announcement opens it again; an empty one closes it.
    announce("Doors opening on the right")
    assert popup.property("visible")
    assert shown_text() == "Doors opening on the right"
    announce("")
    assert not popup.property("visible")

    # Escape closes it.
    announce("Mind the gap")
    QTest.keyClick(window, Qt.Key_Escape)
    QTest.qWait(50)
    assert not popup.property("visible")

    # Not modal: the passenger emergency brake stays in reach.
    announce("Please stand clear of the doors")
    brake = next(x for x in walk(window.contentItem())
                 if x.property("text") == "APPLY EMERGENCY BRAKE")
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, brake.mapToScene(
        brake.boundingRect().center()).toPoint())
    QTest.qWait(50)
    assert any(x.property("text") == "CONFIRM" and x.isVisible()
               for x in walk(window.contentItem()))
    QTest.keyClick(window, Qt.Key_Escape)

    # It scales with the window, like the rest of the design. A long
    # announcement scrolls inside it, and Dismiss stays in the window.
    window.resize(720, 450)
    QTest.qWait(50)
    announce(" ".join(["Please stand clear of the closing doors."] * 60))
    QTest.qWait(50)
    shown = popup.mapRectToScene(QRectF(0, 0, popup.width(),
                                        popup.height()))
    assert shown.width() == popup.width() / 2, shown
    assert shown.bottom() <= window.height(), shown
    dismiss = next(x for x in walk(popup)
                   if x.property("text") == "Dismiss")
    corner = dismiss.mapToScene(dismiss.boundingRect().bottomRight())
    assert corner.y() <= window.height(), corner
    scroll = next(x for x in walk(popup)
                  if x.objectName() == "announcementScroll")
    assert scroll.height() < shown_height(popup)
    window.resize(1440, 900)
    QTest.qWait(50)

    # An active failure's button is red (danger), an idle one secondary.
    def failure_button(label):
        return next(x for x in walk(window.contentItem())
                    if x.property("text") == label)

    assert failure_button("Induce Engine failure").property(
        "variant") == "secondary"
    state.setFailure("engine_failure", True)
    QTest.qWait(50)
    assert failure_button("Clear Engine failure").property(
        "variant") == "danger"
    QTest.keyClick(window, Qt.Key_Escape)

    del engine
    del app


if __name__ == "__main__":
    main()
