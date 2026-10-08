"""Track Model process: the module, its UI, and the test UI link.

Run from the repository root::

    python TrackModel/main.py

Then start the test UI, in either order::

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

MODULE_DIR = Path(__file__).resolve().parent
REPO_ROOT = MODULE_DIR.parent
for path in (str(REPO_ROOT), str(MODULE_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from test_link.link import LinkServer  # noqa: E402
from track_model.interface import TrackConfig  # noqa: E402
from track_model.model import TrackModel  # noqa: E402
from track_model.state import TrackModelState  # noqa: E402
from ui.aspect_lock import install_window_scaling  # noqa: E402
from ui.theme import build_theme  # noqa: E402

ENTRY_QML = MODULE_DIR / "ui" / "Main.qml"


def layout_paths() -> tuple[str, ...]:
    """Return every course line file next to this module."""
    return tuple(str(p) for p in sorted(MODULE_DIR.glob("*_line.json")))


def main() -> int:
    """Start the Track Model, its window and the link server."""
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Track Model")
    # The Basic style is the only one that honours custom control
    # templates; the native Windows style would ignore them.
    QQuickStyle.setStyle("Basic")

    model = TrackModel(TrackConfig(layout_paths()))
    server = LinkServer(model)
    state = TrackModelState(model, on_ui_action=server.notify_outputs)
    server.changed.connect(state.refresh)
    server.stepped.connect(state.mark_step)
    if not server.listen():
        print("Test UI link unavailable; running without it.",
              file=sys.stderr)

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    # build_theme() resolves font families, so it needs the app first.
    context.setContextProperty("theme", build_theme())
    context.setContextProperty("trackModel", state)
    engine.load(QUrl.fromLocalFile(str(ENTRY_QML)))
    if not engine.rootObjects():
        print(f"Failed to load {ENTRY_QML}", file=sys.stderr)
        return 1

    window_scaling = install_window_scaling(  # noqa: F841  outlives window
        cast(QWindow, engine.rootObjects()[0])
    )
    exit_code = app.exec()
    server.close()
    # Tear down QML before the state it binds to.
    del engine
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
