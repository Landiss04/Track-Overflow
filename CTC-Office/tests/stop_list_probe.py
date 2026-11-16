"""Load the CTC Office window offscreen in Manual mode, give a train
its stops through the Dispatch panel with the mouse, and report what the
panel shows after each action, for ``test_ctc_window``.

Run as its own process (the window needs a QGuiApplication). Prints one
JSON object, ``steps``: per action, its name, the submit button's text,
the stop cards the list shows (each card's texts, in order) and the
train's stops as the CTC holds them.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QSG_NO_VSYNC", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PySide6.QtCore import QPoint, QPointF, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from ctc.module_process import _ENTRY_QML, layout_files  # noqa: E402
from ctc.scheduler import SIMULATION_START_S  # noqa: E402
from ctc.track_layout import load_layout  # noqa: E402
from ctc_ui.ctc_host import CtcHost  # noqa: E402
from ctc_ui.harness_clock import HarnessClockBridge  # noqa: E402
from ctc_ui.track_map import TrackMapModel  # noqa: E402
from tests.occupancy import ready_office  # noqa: E402

TRAIN = "G1"


def main() -> int:
    app = QGuiApplication(sys.argv[:1])  # noqa: F841  the one application
    from ui.theme import build_theme

    layout = load_layout(layout_files())
    host = CtcHost(ready_office(), layout=layout, serve_test_ui=False)
    host.start_at(SIMULATION_START_S)
    clock = HarnessClockBridge(host, SIMULATION_START_S, lambda _: None)
    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    context.setContextProperty("theme", build_theme())
    context.setContextProperty("trackMap", TrackMapModel(layout))
    context.setContextProperty("ctc", host)
    context.setContextProperty("simClock", clock)
    engine.load(QUrl.fromLocalFile(str(_ENTRY_QML)))
    roots = engine.rootObjects()
    if not roots:
        print(json.dumps({"error": "the window did not load"}))
        return 1
    window = roots[0]
    window.setProperty("modeIndex", 1)
    host.setAutomaticMode(False)
    steps: list[dict[str, Any]] = []

    def settle() -> None:
        # Let the window lay out and draw: a ListView makes its
        # delegates as it polishes, before a frame.
        for _ in range(3):
            QTest.qWait(20)

    def items() -> list[QQuickItem]:
        found: list[QQuickItem] = []
        pending = [window.contentItem()]
        while pending:
            item = pending.pop()
            found.append(item)
            pending.extend(item.childItems())
        return found

    def find(name: str) -> QQuickItem:
        # The one visible item by that name (each view has its own).
        matches = [i for i in items()
                   if i.objectName() == name and i.isVisible()]
        if len(matches) != 1:
            raise LookupError(f"{len(matches)} visible items {name!r}")
        return matches[0]

    def centre(item: QQuickItem) -> QPoint:
        return item.mapToScene(
            QPointF(item.width() / 2, item.height() / 2)).toPoint()

    def click(name: str) -> None:
        QTest.mouseClick(window, Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier, centre(find(name)))
        settle()

    def drag(name: str, dy: float) -> None:
        start = centre(find(name))
        buttons = Qt.MouseButton.LeftButton
        QTest.mousePress(window, buttons, Qt.KeyboardModifier.NoModifier,
                         start)
        for i in range(1, 11):
            QTest.mouseMove(window, start + QPoint(0, round(dy * i / 10)),
                            20)
            settle()
        QTest.mouseRelease(window, buttons, Qt.KeyboardModifier.NoModifier,
                           start + QPoint(0, round(dy)))
        settle()

    def pick(name: str, value: str) -> None:
        field = find(name)
        field.setProperty("picked", value)
        field.metaObject().invokeMethod(field, "restore")
        settle()

    def texts(item: QQuickItem) -> list[str]:
        found = []
        pending = [item]
        while pending:
            child = pending.pop(0)
            text = child.property("text")
            if (isinstance(text, str) and text and child.isVisible()
                    and child.metaObject().className().startswith(
                        ("QQuickText", "MonoText"))):
                found.append(text)
            pending.extend(child.childItems())
        return found

    def record(action: str) -> None:
        cards = []
        index = 0
        while True:
            try:
                card = find(f"stop-card-{index}")
            except LookupError:
                break
            cards.append(texts(card))
            index += 1
        steps.append({
            "action": action,
            "button": find("stop-submit").property("text"),
            "list": find("stop-list").property("count")
            if cards else 0,
            "cards": cards,
            "stops": [c["block"]
                      for c in host.stopQueues.get(TRAIN, [])],
            "message": find("dispatch-message").property("text"),
        })

    def add_station(block: str, arrival: str) -> None:
        pick("stop-station", block)
        find("stop-arrival").setProperty("text", arrival)
        settle()
        click("stop-submit")

    settle()
    pick("dispatch-line", "Green")
    pick("dispatch-train", TRAIN)
    record("picked")
    add_station("65", "05:10")
    record("dispatched 65")
    add_station("73", "05:20")
    record("queued 73")
    # A block, not a station: Block in STOP AT, then type its number.
    stop_kind = find("stop-kind")
    block_segment = next(i for i in items() if i.isVisible()
                         and i.property("text") == "Block"
                         and i.parentItem() is not None
                         and stop_kind.isAncestorOf(i))
    QTest.mouseClick(window, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, centre(block_segment))
    settle()
    block_field = find("stop-block")
    combo = next(i for i in block_field.childItems()
                 if i.metaObject().indexOfProperty("editText") >= 0)
    combo.setProperty("editText", "70")
    settle()
    click("stop-submit")
    record("queued block 70")
    click("stop-down-0")
    record("moved 1 down")
    click("stop-remove-1")
    record("removed 2")
    click("stop-up-1")
    record("moved 2 up")
    pitch = find("stop-card-1").mapToScene(QPointF(0, 0)).y() - \
        find("stop-card-0").mapToScene(QPointF(0, 0)).y()
    station_segment = next(i for i in items() if i.isVisible()
                           and i.property("text") == "Station"
                           and stop_kind.isAncestorOf(i))
    QTest.mouseClick(window, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier,
                     centre(station_segment))
    settle()
    add_station("77", "")
    record("queued 77")
    drag("stop-handle-2", -2 * pitch)
    record("dragged 3 to 1")
    print(json.dumps({"steps": steps}))
    del engine
    return 0


if __name__ == "__main__":
    sys.exit(main())
