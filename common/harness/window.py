"""Load the harness window from source or a PyInstaller data bundle."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow

from common.harness.console import HarnessConsole
from ui.app_icon import install_app_icon
from ui.aspect_lock import install_window_scaling
from ui.theme import build_theme


def resource_path(relative: str) -> Path:
    """Return a source or frozen resource at the same relative path."""
    root = Path(getattr(
        sys, "_MEIPASS", Path(__file__).resolve().parents[2]
    ))
    return root / relative


class HarnessWindow:
    """Keep QML and its context alive until the run ends."""

    def __init__(
        self, app: QGuiApplication, console: HarnessConsole
    ) -> None:
        """Install the shared theme, icon, scaling and operator view.

        Raises:
            RuntimeError: If the QML window cannot load.
        """
        install_app_icon(app)
        self.theme = build_theme()
        font = QFont(self.theme["ui_family"])
        font.setPixelSize(self.theme["size_body"])
        app.setFont(font)
        self.engine = QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty("theme", self.theme)
        self.engine.rootContext().setContextProperty("backend", console)
        self.engine.load(QUrl.fromLocalFile(str(resource_path(
            "common/harness/ui/Main.qml"
        ))))
        if not self.engine.rootObjects():
            raise RuntimeError("Cannot load the central harness window")
        self.root = self.engine.rootObjects()[0]
        if not isinstance(self.root, QQuickWindow):
            raise RuntimeError("The harness QML root must be a window")
        self.scaling = install_window_scaling(self.root)

    def close(self) -> None:
        """Destroy QML while its Python context objects still exist."""
        self.root.hide()
        # Delete now to avoid context binding warnings at exit.
        import shiboken6

        shiboken6.delete(self.engine)
