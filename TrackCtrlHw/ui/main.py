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
REPO_ROOT = UI_DIR.parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ui.aspect_lock import install_window_scaling  # noqa: E402
from ui.theme import build_theme  # noqa: E402


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
    # build_theme() resolves font families, so it needs the application first.
    engine.rootContext().setContextProperty("theme", build_theme())
    engine.load(QUrl.fromLocalFile(str(ENTRY_QML)))

    if not engine.rootObjects():
        print(f"Failed to load {ENTRY_QML}", file=sys.stderr)
        return 1

    window_scaling = install_window_scaling(  # noqa: F841  must outlive window
        engine.rootObjects()[0]
    )

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
