"""Load the CTC Office window offscreen, redraw it, and report what it
shows, for ``test_ctc_window``.

Run as its own process: the window needs a QGuiApplication, and the
other tests' QCoreApplication would be the process's one application.
Prints one JSON object: for each redraw, every train car on the map
(its item's address, where it is drawn, where ``placeTrains`` puts it),
every signal marker on the map (its item's address, the block it is
drawn at, the shape showing and its size on screen) and every row of
the Signals panels (the aspect it shows).
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

import shiboken6  # noqa: E402
from PySide6.QtCore import QRectF, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402

from ctc.interface import SignalReport, TrackModelInputs  # noqa: E402
from ctc.module_process import _ENTRY_QML, layout_files  # noqa: E402
from ctc.scheduler import SIMULATION_START_S  # noqa: E402
from ctc.track_layout import load_layout  # noqa: E402
from ctc_ui.ctc_host import CtcHost  # noqa: E402
from ctc_ui.harness_clock import HarnessClockBridge  # noqa: E402
from ctc_ui.track_map import TrackMapModel  # noqa: E402
from tests.occupancy import at, place, ready_office, reports  # noqa: E402

DT_S = 0.1


def main() -> int:
    app = QGuiApplication(sys.argv[:1])
    from ui.theme import build_theme

    layout = load_layout(layout_files())
    host = CtcHost(ready_office(), layout=layout, serve_test_ui=False)
    clock = HarnessClockBridge(host, SIMULATION_START_S, lambda _: None)
    track_map = TrackMapModel(layout)
    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    context.setContextProperty("theme", build_theme())
    context.setContextProperty("trackMap", track_map)
    context.setContextProperty("ctc", host)
    context.setContextProperty("simClock", clock)
    engine.load(QUrl.fromLocalFile(str(_ENTRY_QML)))
    roots = engine.rootObjects()
    if not roots:
        print(json.dumps({"error": "the window did not load"}))
        return 1
    root = roots[0]
    module = host.module
    now = [SIMULATION_START_S]
    redraws: list[dict[str, Any]] = []

    def step(*trains: Any, tickets: int = 0,
             signals: tuple[SignalReport, ...] = ()) -> None:
        # One harness step, then the redraw the process would make.
        place(module, *trains)
        inputs = reports(*trains, signals=signals)
        if tickets:
            inputs = type(inputs)(
                track_controller=inputs.track_controller,
                track_model=TrackModelInputs({"GLENBURY": tickets}))
        now[0] += DT_S
        host.step_at(DT_S, now[0], inputs)
        host.refresh()
        app.processEvents()
        redraws.append(shown())

    def address(item: QQuickItem) -> int:
        return int(shiboken6.getCppPointer(item)[0])

    def items() -> list[QQuickItem]:
        # Every item in the window, visual children included: a
        # Repeater's delegates have no QObject parent to find them by.
        found: list[QQuickItem] = []
        pending = [root.contentItem()]
        while pending:
            item = pending.pop()
            found.append(item)
            pending.extend(item.childItems())
        return found

    def shown() -> dict[str, Any]:
        expected = {t["train"]: t
                    for t in track_map.placeTrains(host.mapTrains)}
        cars = {}
        every = items()
        for item in every:
            name = item.objectName()
            if name.startswith("train-") and item.isVisible():
                train = name.removeprefix("train-")
                cars[train] = {
                    "address": address(item),
                    "x": item.x(), "y": item.y(),
                    "expected": [expected[train]["x"],
                                 expected[train]["y"]]
                    if train in expected else None,
                }
        lights = {}
        rows: dict[str, list[str]] = {}
        for item in every:
            name = item.objectName()
            if name.startswith("signal-row-"):
                rows.setdefault(name.removeprefix("signal-row-"), []).append(
                    str(item.property("aspect")))
            if not name.startswith("signal-") or name.startswith(
                    "signal-row-"):
                continue
            marker = next(c for c in item.childItems()
                          if c.objectName() == "marker")
            shapes = [c.objectName() for c in marker.childItems()
                      if c.isVisible() and c.objectName()]
            line = name.split("-")[1]
            drawn_at = next(
                (b["blockId"] for b in track_map.blocks
                 if b["line"] == line
                 and b["mid"] == [round(item.x(), 1), round(item.y(), 1)]),
                None)
            rect = marker.mapRectToScene(
                QRectF(0, 0, marker.width(), marker.height()))
            lights[name.removeprefix("signal-")] = {
                "address": address(item),
                "visible": item.isVisible(),
                "aspect": str(marker.property("aspect")),
                "shapes": shapes,
                "drawnAt": drawn_at,
                "screenSize": [round(rect.width(), 1),
                               round(rect.height(), 1)],
            }
        return {"cars": cars, "lights": lights, "rows": rows}

    lit = (SignalReport("Green", "12", "RED"),
           SignalReport("Green", "62", "YELLOW"),
           SignalReport("Red", "15", "GREEN"),
           SignalReport("Red", "9", "SUPER_GREEN"))
    step(at("T1", "3"), at("T2", "65"))
    step(at("T1", "2"), at("T2", "65"), tickets=40, signals=lit)
    step(at("T1", "2"), at("T2", "66"), tickets=40,
         signals=(SignalReport("Green", "12", "GREEN"), *lit[1:]))
    print(json.dumps({"redraws": redraws}))
    del engine
    return 0


if __name__ == "__main__":
    sys.exit(main())
