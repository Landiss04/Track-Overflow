"""Application entry point for the Train Controller module."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from train_controller.aspect_lock import install_aspect_lock
from train_controller.theme import build_theme
from train_controller.train_controller_state import TrainControllerState

_MAIN_QML = Path(__file__).resolve().parent / "ui" / "Main.qml"


def main() -> int:
    """Create the app, load the cab view, and run the event loop."""
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Train Controller")

    theme = build_theme()
    font = QFont()
    font.setFamily(theme["ui_family"])
    font.setPixelSize(theme["size_body"])
    app.setFont(font)

    # Keep a Python-side reference so the object is not garbage
    # collected while QML holds only a C++ pointer to it.
    controller = TrainControllerState()

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    if context is None:
        print("Failed to obtain the QML root context.", file=sys.stderr)
        return 1

    context.setContextProperty("theme", theme)
    context.setContextProperty("controller", controller)

    engine.load(QUrl.fromLocalFile(str(_MAIN_QML)))
    if not engine.rootObjects():
        print("Failed to load QML views.", file=sys.stderr)
        return 1

    window = engine.rootObjects()[0]
    ratio = (
        window.property("referenceWidth"),
        window.property("referenceHeight"),
    )
    aspect_lock = install_aspect_lock(window, ratio)  # noqa: F841  keep alive

    controller.start()
    exit_code = app.exec()
    # Tear down QML before the context objects it binds to, so bindings
    # do not re-evaluate against deleted objects during shutdown.
    del engine
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
