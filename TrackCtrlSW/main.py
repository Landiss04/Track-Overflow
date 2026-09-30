"""Application entry point for the Track Controller (Software) module."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import PySide6

# Qt loads its QML plugins with LoadLibrary at runtime. Python 3.8+
# restricts the DLL search path, so on Windows the plugins cannot find
# the Qt libraries sitting next to them unless that directory is added
# back explicitly. This has to happen before the QML engine is built.
if sys.platform == "win32":
    os.add_dll_directory(str(Path(PySide6.__file__).resolve().parent))

from PySide6.QtCore import QUrl  # noqa: E402  must follow the DLL fix
from PySide6.QtGui import QFont, QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402

from track_ctrl.state import TrackControllerState  # noqa: E402
from track_ctrl.theme import build_theme  # noqa: E402

_MAIN_QML = Path(__file__).resolve().parent / "ui" / "Main.qml"


def main() -> int:
    """Create the app, load the QML views, and run the event loop."""
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Track Controller")

    theme = build_theme()
    font = QFont()
    font.setFamily(theme["ui_family"])
    font.setPixelSize(theme["size_body"])
    app.setFont(font)

    # Keep a Python-side reference so the object is not garbage
    # collected while QML holds only a C++ pointer to it.
    state = TrackControllerState()

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    if context is None:
        print("Failed to obtain the QML root context.", file=sys.stderr)
        return 1

    context.setContextProperty("theme", theme)
    context.setContextProperty("wayside", state)

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
