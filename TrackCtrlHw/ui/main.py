"""Launcher for the Track Controller QML user interface.

Run from the repository root:

    python TrackCtrlHw/ui/main.py
"""

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle


UI_DIR = Path(__file__).resolve().parent
ENTRY_QML = UI_DIR / "Main.qml"


def main() -> int:
    """Start the Qt event loop with the Track Controller window loaded."""
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Track Controller")
    app.setOrganizationName("ECE1140 Team 3")

    # The Basic style is the only one that honours custom control templates;
    # the native Windows style would silently ignore them.
    QQuickStyle.setStyle("Basic")

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(UI_DIR))
    engine.load(QUrl.fromLocalFile(str(ENTRY_QML)))

    if not engine.rootObjects():
        print(f"Failed to load {ENTRY_QML}", file=sys.stderr)
        return 1

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
