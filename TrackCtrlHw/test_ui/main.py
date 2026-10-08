"""Launcher for the Track Controller test user interface.

The test UI runs in its own process and its own window, separate from
the Track Controller window in ``TrackCtrlHw/ui``. Run from the
repository root:

    python TrackCtrlHw/test_ui/main.py
"""

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle


UI_DIR = Path(__file__).resolve().parent
ENTRY_QML = UI_DIR / "Main.qml"
MODULE_ROOT = UI_DIR.parent
REPO_ROOT = UI_DIR.parents[1]

for path in (str(REPO_ROOT), str(MODULE_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from track_ctrl.test_harness import TrackCtrlTestHarness  # noqa: E402
from ui.aspect_lock import install_window_scaling  # noqa: E402
from ui.theme import build_theme  # noqa: E402


def main() -> int:
    """Start the Qt event loop with the test window loaded."""
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Track Controller Test UI")
    app.setOrganizationName("ECE1140 Team 3")

    # The Basic style is the only one that honours custom control
    # templates; the native Windows style would silently ignore them.
    QQuickStyle.setStyle("Basic")

    engine = QQmlApplicationEngine()
    harness = TrackCtrlTestHarness()
    context = engine.rootContext()
    # build_theme() resolves font families, so it needs the app first.
    context.setContextProperty("theme", build_theme())
    context.setContextProperty("harness", harness)
    engine.load(QUrl.fromLocalFile(str(ENTRY_QML)))

    if not engine.rootObjects():
        print(f"Failed to load {ENTRY_QML}", file=sys.stderr)
        return 1

    window_scaling = install_window_scaling(  # noqa: F841  outlives window
        engine.rootObjects()[0]
    )

    exit_code = app.exec()
    # Tear down QML before the harness it binds to, so bindings do not
    # re-evaluate against a deleted object during shutdown.
    del engine
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
