"""Window bootstrap shared by the Train Model and test UI processes."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QFont, QGuiApplication, QWindow
from PySide6.QtQml import QQmlApplicationEngine

# The design tokens are shared by every module's UI, so they live in the
# repository-level ui/ folder next to the shared QML components.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ui.aspect_lock import install_window_scaling  # noqa: E402
from ui.theme import build_theme  # noqa: E402

UI_DIR = Path(__file__).resolve().parents[1] / "ui"


def run_window(
    name: str,
    qml_file: str,
    build_context: Callable[[], dict[str, QObject]],
) -> int:
    """Create the app, load one QML window, and run the event loop.

    ``build_context`` runs once the application exists and returns the
    objects to expose to QML as context properties.
    """
    app = QGuiApplication(sys.argv)
    app.setApplicationName(name)

    theme = build_theme()
    font = QFont()
    font.setFamily(theme["ui_family"])
    font.setPixelSize(theme["size_body"])
    app.setFont(font)

    # Keep Python-side references so the objects are not garbage
    # collected while QML holds only C++ pointers to them.
    context_objects = build_context()

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    if context is None:
        print("Failed to obtain the QML root context.", file=sys.stderr)
        return 1

    context.setContextProperty("theme", theme)
    for key, value in context_objects.items():
        context.setContextProperty(key, value)

    engine.load(QUrl.fromLocalFile(str(UI_DIR / qml_file)))
    if not engine.rootObjects():
        print("Failed to load QML views.", file=sys.stderr)
        return 1

    window = engine.rootObjects()[0]
    if not isinstance(window, QWindow):
        print("QML root object is not a window.", file=sys.stderr)
        return 1
    aspect_lock = install_window_scaling(window)  # noqa: F841  keep alive

    exit_code = app.exec()
    # Tear down QML before the context objects it binds to, so bindings
    # do not re-evaluate against deleted objects during shutdown.
    del engine
    return exit_code
