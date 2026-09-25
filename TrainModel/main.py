"""Entry point for the Train Model UI (PyQt6 + QML).

Builds the design-token theme, instantiates the two stub state objects, and
loads the QML view layer. QML owns all visuals; this module owns state and
wires the context properties the views bind to.

Run with::

    python TrainModel/main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QFont
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtWidgets import QApplication

from train_model.harness import TestHarnessState
from train_model.state import TrainModelState
from train_model.theme import build_theme


def main() -> int:
    """Create the app, load the QML views, and run the event loop."""
    app = QApplication(sys.argv)

    theme = build_theme()
    app.setFont(QFont(str(theme["ui_family"]), pointSize=10))

    # Keep Python-side references so the objects are not garbage collected
    # while QML holds only C++ pointers to them.
    train_model = TrainModelState()
    harness = TestHarnessState()

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    if context is None:
        print("Failed to obtain the QML root context.", file=sys.stderr)
        return 1
    context.setContextProperty("theme", theme)
    context.setContextProperty("trainModel", train_model)
    context.setContextProperty("harness", harness)

    qml_dir = Path(__file__).resolve().parent / "ui"
    engine.load(QUrl.fromLocalFile(str(qml_dir / "Main.qml")))

    if not engine.rootObjects():
        print("Failed to load QML views.", file=sys.stderr)
        return 1

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
