"""Application entry point for the Train Model module."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from train_model.harness import TestHarnessState
from train_model.state import TrainModelState

# The design tokens are shared by every module's UI, so they live in the
# repository-level ui/ folder next to the shared QML components.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ui.aspect_lock import install_window_scaling  # noqa: E402
from ui.theme import build_theme  # noqa: E402

_MAIN_QML = Path(__file__).resolve().parent / "ui" / "Main.qml"


def main() -> int:
    """Create the app, load the QML views, and run the event loop."""
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Train Model")

    theme = build_theme()
    font = QFont()
    font.setFamily(theme["ui_family"])
    font.setPixelSize(theme["size_body"])
    app.setFont(font)

    # Keep Python-side references so the objects are not garbage
    # collected while QML holds only C++ pointers to them.
    train_model = TrainModelState()
    harness = TestHarnessState(train_model)

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    if context is None:
        print("Failed to obtain the QML root context.", file=sys.stderr)
        return 1

    context.setContextProperty("theme", theme)
    context.setContextProperty("trainModel", train_model)
    context.setContextProperty("harness", harness)

    engine.load(QUrl.fromLocalFile(str(_MAIN_QML)))
    if not engine.rootObjects():
        print("Failed to load QML views.", file=sys.stderr)
        return 1

    window = engine.rootObjects()[0]
    aspect_lock = install_window_scaling(window)  # noqa: F841  keep alive

    exit_code = app.exec()
    # Tear down QML before the context objects it binds to, so bindings
    # do not re-evaluate against deleted objects during shutdown.
    del engine
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
