"""Application entry point for the CTC Office UI.

Run from the ``CTC-Office`` directory with ``python -m ctc_ui``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

# The design tokens and window scaling are shared by every module's UI,
# so they live in the repository-level ui/ folder next to the shared QML
# components.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
# CTC-Office/, so the ``ctc`` module package imports however this file
# is started.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ui.app_icon import install_app_icon  # noqa: E402
from ui.aspect_lock import install_window_scaling  # noqa: E402
from ui.theme import build_theme  # noqa: E402

from ctc_ui.clock_link import ClockLinkServer  # noqa: E402
from ctc_ui.sim_clock import SimulationClockBridge  # noqa: E402
from ctc_ui.track_map import TrackMapModel  # noqa: E402

_MAIN_QML = Path(__file__).resolve().parent / "ui" / "Main.qml"


def main() -> int:
    """Create the app, load the QML views, and run the event loop."""
    app = QGuiApplication(sys.argv)
    app.setApplicationName("CTC Office")
    install_app_icon(app)

    theme = build_theme()
    font = QFont()
    font.setFamily(theme["ui_family"])
    font.setPixelSize(theme["size_body"])
    app.setFont(font)

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    if context is None:
        print("Failed to obtain the QML root context.", file=sys.stderr)
        return 1

    context.setContextProperty("theme", theme)
    # The track map is built once from the layout files at startup. Keep
    # a Python reference: QML holds only a C++ pointer to it.
    track_map = TrackMapModel()
    context.setContextProperty("trackMap", track_map)
    # The one simulation clock, driven in real time. Parented to the app
    # so it lives as long as the event loop.
    sim_clock = SimulationClockBridge(parent=app)
    context.setContextProperty("simClock", sim_clock)
    # Lets the test UI, in its own process, control the same clock. The
    # CTC runs normally if the link cannot start.
    clock_link = ClockLinkServer(sim_clock, parent=app)
    clock_link.listen()

    engine.load(QUrl.fromLocalFile(str(_MAIN_QML)))
    if not engine.rootObjects():
        print("Failed to load QML views.", file=sys.stderr)
        return 1

    # Keep a reference: the lock's window procedure must outlive the
    # window, or Windows calls into freed memory.
    window_scaling = install_window_scaling(  # noqa: F841
        engine.rootObjects()[0])

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
