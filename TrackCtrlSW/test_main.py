"""Entry point for the Track Controller test UI.

A separate process from ``main.py``. Start the Track Controller first,
then run this; it connects to the controller's local stimulus link and
plays the CTC, the Track Model and the programmer. If the controller is
not running yet, this window waits and connects when it appears.
"""

from __future__ import annotations

import sys
from pathlib import Path

from track_ctrl.qtenv import add_qt_dll_directory

# Must run before the QML engine is built; see track_ctrl/qtenv.py.
add_qt_dll_directory()

from PySide6.QtCore import QUrl  # noqa: E402  must follow the DLL fix
from PySide6.QtGui import QFont, QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402

from track_ctrl.theme import build_theme  # noqa: E402
from track_ctrl_test.client import TestClientState  # noqa: E402

_MAIN_QML = Path(__file__).resolve().parent / "test_ui" / "TestMain.qml"


def main() -> int:
    """Create the app, load the test UI, and run the event loop."""
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Track Controller Test UI")

    theme = build_theme()
    font = QFont()
    font.setFamily(theme["ui_family"])
    font.setPixelSize(theme["size_body"])
    app.setFont(font)

    # Keep a Python-side reference so the object is not garbage
    # collected while QML holds only a C++ pointer to it.
    stimulus = TestClientState()

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    if context is None:
        print("Failed to obtain the QML root context.", file=sys.stderr)
        return 1

    context.setContextProperty("theme", theme)
    context.setContextProperty("stimulus", stimulus)

    engine.load(QUrl.fromLocalFile(str(_MAIN_QML)))
    if not engine.rootObjects():
        print("Failed to load QML views.", file=sys.stderr)
        return 1

    exit_code = app.exec()
    # Tear down QML before the context objects it binds to, so bindings
    # do not re-evaluate against deleted objects during shutdown.
    del engine
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
