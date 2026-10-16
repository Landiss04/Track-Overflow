"""The Train Model window's header ads: they load and take turns."""

from pathlib import Path
import sys

from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: F401
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "TrainModel")]

from train_model.fleet import TrainModelFleet  # noqa: E402
from train_model.harness import TestHarnessState  # noqa: E402
from train_model.link import LocalLink  # noqa: E402
from ui.theme import build_theme  # noqa: E402

def wait_for(predicate, timeout_ms):
    waited = 0
    while not predicate() and waited < timeout_ms:
        QTest.qWait(10)
        waited += 10
    return predicate()


def main():
    app = QGuiApplication([])
    fleet = TrainModelFleet()
    state = fleet.add("T-1", "Blue")
    harness = TestHarnessState(LocalLink(state))
    engine = QQmlApplicationEngine()
    for name, value in [("theme", build_theme()), ("fleet", fleet),
                        ("harness", harness)]:
        engine.rootContext().setContextProperty(name, value)
    engine.load(QUrl.fromLocalFile(str(ROOT / "TrainModel/ui/Main.qml")))
    window = engine.rootObjects()[0]
    banner = window.findChild(QObject, "adBanner")
    image = window.findChild(QObject, "adImage")
    assert banner is not None and image is not None

    # Every ad file is in pics/, and each one loads.
    ads = [str(x) for x in banner.property("ads").toVariant()]
    assert len(ads) == 4, ads
    shown = []
    for i in range(len(ads)):
        banner.setProperty("index", i)
        source = image.property("source")
        # Relative to Main.qml, as the Image resolves it.
        path = ROOT / "TrainModel/ui" / source.toString()
        assert path.resolve().is_file(), path
        assert wait_for(lambda: image.property("progress") == 1.0
                        and image.property("implicitWidth") == 711
                        and image.property("implicitHeight") == 44,
                        2000), ads[i]
        shown.append(source.toString())
    assert len(set(shown)) == len(ads), shown

    # Each ad stays up for 30 s, as tall as the header's controls.
    assert banner.property("interval") == 30000
    assert banner.height() == build_theme()["control_h_lg"]

    # They take turns, wrapping back to the first after the last.
    banner.setProperty("index", 0)
    banner.setProperty("interval", 100)
    seen = [0]
    for _ in range(len(ads)):
        before = seen[-1]
        wait_for(lambda: banner.property("index") != before, 1000)
        seen.append(banner.property("index"))
    assert seen == [0, 1, 2, 3, 0], seen

    print("ad banner ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
