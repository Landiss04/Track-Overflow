"""Launcher for the Track Model test UI.

The test UI runs in its own process and window, separate from the Track
Model window, and reaches the module only through the test link. Run
from the repository root, after or before ``TrackModel/main.py``::

    python TrackModel/test_ui/main.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import cast

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication, QWindow
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

UI_DIR = Path(__file__).resolve().parent
MODULE_DIR = UI_DIR.parent
REPO_ROOT = MODULE_DIR.parent
for path in (str(REPO_ROOT), str(MODULE_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from test_ui.harness import TrackModelTestHarness  # noqa: E402
from ui.aspect_lock import install_window_scaling  # noqa: E402
from ui.theme import build_theme  # noqa: E402

ENTRY_QML = UI_DIR / "Main.qml"


def main() -> int:
    """Start the Qt event loop with the test window loaded."""
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Track Model Test UI")
    # The Basic style is the only one that honours custom control
    # templates; the native Windows style would ignore them.
    QQuickStyle.setStyle("Basic")

    engine = QQmlApplicationEngine()
    harness = TrackModelTestHarness()
    context = engine.rootContext()
    # build_theme() resolves font families, so it needs the app first.
    context.setContextProperty("theme", build_theme())
    context.setContextProperty("harness", harness)
    engine.load(QUrl.fromLocalFile(str(ENTRY_QML)))
    if not engine.rootObjects():
        print(f"Failed to load {ENTRY_QML}", file=sys.stderr)
        return 1

    window_scaling = install_window_scaling(  # noqa: F841  outlives window
        cast(QWindow, engine.rootObjects()[0])
    )
    exit_code = app.exec()
    harness.close()
    # Tear down QML before the harness it binds to.
    del engine
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
