"""No readout in the Train Model window shows a negative zero.

Full power on the Blue Line brings the train up to the speed cap, which
it reaches from just above, so its acceleration is a few millionths of a
m/s² below zero. Rounded for display, that must read 0.00, not -0.00.
"""

from pathlib import Path
import re
import sys

from PySide6.QtCore import QUrl
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

# A minus sign on a number that is all zeros: "-0", "-0.0", "-0.00 ft".
NEGATIVE_ZERO = re.compile(r"(?<![\w.])-0(\.0+)?(?![\d.])")


def walk(item):
    yield item
    for child in item.childItems():
        yield from walk(child)


def main():
    app = QGuiApplication([])
    fleet = TrainModelFleet()
    state = fleet.add("T-1", "Blue")
    harness = TestHarnessState(LocalLink(state))
    engine = QQmlApplicationEngine()
    for name, value in [("theme", build_theme()), ("fleet", fleet)]:
        engine.rootContext().setContextProperty(name, value)
    engine.load(QUrl.fromLocalFile(str(ROOT / "TrainModel/ui/Main.qml")))
    window = engine.rootObjects()[0]

    harness.setInput("power_command", 480_000.0)
    assert harness.sendInputs()
    # The case under test: below zero, yet 0.00 in ft/s².
    for _ in range(900):
        harness.advanceTick()
        if -0.005 / 3.28084 < state.snapshot["acceleration"] < 0.0:
            break
    else:
        raise AssertionError("acceleration never just below zero")
    QTest.qWait(50)

    texts = [str(x.property("text")) for x in walk(window.contentItem())
             if x.property("text") is not None]
    assert any(t == "0.00 ft/s²" for t in texts), texts
    shown = [t for t in texts if NEGATIVE_ZERO.search(t)]
    assert not shown, shown

    del engine
    del app


if __name__ == "__main__":
    main()
