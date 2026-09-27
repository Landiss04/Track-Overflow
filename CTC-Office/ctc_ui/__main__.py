"""Application entry point for the CTC Office UI.

Run from the ``CTC-Office`` directory with ``python -m ctc_ui``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from ctc_ui.theme import build_theme

_MAIN_QML = Path(__file__).resolve().parent / "ui" / "Main.qml"


def main() -> int:
    """Create the app, load the QML views, and run the event loop."""
    app = QGuiApplication(sys.argv)
    app.setApplicationName("CTC Office")

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

    engine.load(QUrl.fromLocalFile(str(_MAIN_QML)))
    if not engine.rootObjects():
        print("Failed to load QML views.", file=sys.stderr)
        return 1

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
