"""The Train Model window's announcement popup and red active failures."""

from pathlib import Path
import sys

from PySide6.QtCore import QObject, Qt, QUrl
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

    def shown_text():
        content = popup.property("contentItem")
        return next(x for x in walk(content)
                    if x.objectName() == "announcementText").property("text")

    announce("Next stop: Station B")
    assert popup.property("visible")
    assert shown_text() == "Next stop: Station B"

    # Dismissed, the same announcement on later ticks stays dismissed.
    content = popup.property("contentItem")
    dismiss = next(x for x in walk(content)
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

    # Not modal: the passenger emergency brake stays usable.
    announce("Please stand clear of the doors")
    assert not popup.property("modal")

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
