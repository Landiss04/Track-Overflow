"""Start-up shared by the Track Controller window's entry points.

``main.py`` runs the window; ``capture.py`` renders it to a PNG. Both
build it here, so what is captured is exactly what runs.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

UI_DIR = Path(__file__).resolve().parent
ENTRY_QML = UI_DIR / "Main.qml"
MODULE_ROOT = UI_DIR.parent
REPO_ROOT = UI_DIR.parents[1]
DATA_DIR = MODULE_ROOT / "data"

for _path in (str(REPO_ROOT), str(MODULE_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from track_ctrl_hw.state import TrackControllerState  # noqa: E402
from ui.aspect_lock import install_window_scaling  # noqa: E402
from ui.theme import build_theme  # noqa: E402


class Window:
    """The application, its QML engine, the module and the window."""

    def __init__(self, argv: list[str]) -> None:
        self.app = QGuiApplication(argv)
        self.app.setApplicationName("Track Controller")
        self.app.setOrganizationName("ECE1140 Team 3")
        # The Basic style is the only one that honours custom control
        # templates; the native Windows style ignores them.
        QQuickStyle.setStyle("Basic")
        # build_theme() resolves font families, so it needs the app.
        theme = build_theme()
        font = QFont()
        font.setFamily(theme["ui_family"])
        font.setPixelSize(theme["size_body"])
        self.app.setFont(font)

        # Python must hold the state: QML keeps only a C++ pointer.
        self.state = TrackControllerState()
        self.engine = QQmlApplicationEngine()
        self.engine.addImportPath(str(UI_DIR))
        context = self.engine.rootContext()
        context.setContextProperty("theme", theme)
        context.setContextProperty("trackController", self.state)
        context.setContextProperty(
            "databaseFolder",
            QUrl.fromLocalFile(str(DATA_DIR / "waysides")),
        )
        context.setContextProperty(
            "programFolder", QUrl.fromLocalFile(str(DATA_DIR / "plc"))
        )
        self.engine.load(QUrl.fromLocalFile(str(ENTRY_QML)))
        roots = self.engine.rootObjects()
        self.window = roots[0] if roots else None
        # Must outlive the window, or Windows calls into freed memory.
        self.scaling = (
            install_window_scaling(self.window) if self.window else None
        )

    def shutdown(self) -> None:
        """Close the link, then tear QML down before the state it binds."""
        self.state.close()
        del self.engine
