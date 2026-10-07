"""Render the Track Controller window to a PNG for visual review.

    python TrackCtrlHw/ui/capture.py out.png
    python TrackCtrlHw/ui/capture.py out.png --size 720 450
    python TrackCtrlHw/ui/capture.py out.png --demo --dialog plc

``--size`` checks the scaling guide's size checklist; without it the
window opens at the 1440 x 900 reference canvas. ``--demo`` loads the
three sample waysides and their programs and runs one scan of sample
inputs in this process, so the window has something to show without a
test UI. ``--dialog`` opens ``plc`` (PLC details) or ``report`` (last
report) before the capture. ``--zoom`` zooms the territory in by that
many steps.
"""

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QMetaObject, QObject, QTimer

from app import DATA_DIR, Window


def _demo(window: Window) -> None:
    from track_ctrl_hw.interface import (
        CtcInputs,
        Suggestion,
        TrackControllerInputs,
        TrackModelInputs,
    )

    state = window.state
    for number in (1, 2, 3):
        state.loadDatabase(
            str(DATA_DIR / "waysides" / f"green_wayside_{number}.json")
        )
        state.loadProgram(
            str(DATA_DIR / "plc" / f"green_wayside_{number}.plc")
        )
    state.selectWayside("1")
    snapshot = state.controller.snapshot()
    keys = {
        key.block_id: key
        for wayside in snapshot.waysides
        for key in wayside.territory.keys
    }
    switches = {
        switch.key: "normal"
        for wayside in snapshot.waysides
        for switch in wayside.territory.switches
    }
    inputs = TrackControllerInputs(
        time_s=14 * 3600 + 32 * 60 + 7,
        ctc=CtcInputs(
            closed_blocks=frozenset({keys["17"]}),
            suggestions={
                keys["4"]: Suggestion(12, 3),
                keys["8"]: Suggestion(12, 2),
                keys["14"]: Suggestion(19, 4),
            },
        ),
        track_model=TrackModelInputs(
            occupied_blocks=frozenset(
                {keys["4"], keys["8"], keys["9"], keys["14"]}
            ),
            failures={keys["20"]: "broken_rail"},
            switch_positions=switches,
            crossings_active={keys["19"]: False},
            signal_aspects={key: "green" for key in switches},
        ),
    )
    state.controller.step(0.1, inputs)
    state.refresh()


def main() -> int:
    """Load the window, grab one frame, write it to disk and exit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", nargs="?", default="track-controller.png")
    parser.add_argument("--size", nargs=2, type=int, metavar=("W", "H"))
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--dialog", choices=("plc", "report"))
    parser.add_argument("--zoom", type=int, default=0)
    args = parser.parse_args()

    window = Window(sys.argv[:1])
    if window.window is None:
        return 1
    if args.demo:
        _demo(window)
    if args.size:
        window.window.resize(*args.size)
    root = window.window
    if args.dialog:
        name = "plcDetails" if args.dialog == "plc" else "lastReport"
        dialog = root.findChild(QObject, name)
        if dialog is not None:
            QMetaObject.invokeMethod(dialog, "open")
    diagram = root.findChild(QObject, "territoryDiagram")
    for _ in range(args.zoom):
        if diagram is not None:
            QMetaObject.invokeMethod(diagram, "zoomIn")

    def grab() -> None:
        root.grabWindow().save(str(Path(args.out)))
        window.app.quit()

    # One second of event loop lets fonts, layouts and the Canvas settle.
    QTimer.singleShot(1000, grab)
    exit_code = window.app.exec()
    window.shutdown()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
