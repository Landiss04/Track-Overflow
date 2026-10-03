"""Render the Track Controller window to a PNG for visual review.

    python TrackCtrlHw/ui/capture.py out.png
    python TrackCtrlHw/ui/capture.py out.png 720 450

The optional width and height check the scaling guide's size checklist;
without them the window opens at the 1440 x 900 reference canvas.
"""

import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
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
    """Load the window, grab one frame, write it to disk and exit."""
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "track-controller.png")

    app = QGuiApplication(sys.argv)
    QQuickStyle.setStyle("Basic")

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(UI_DIR))
    engine.rootContext().setContextProperty("theme", build_theme())
    engine.load(QUrl.fromLocalFile(str(ENTRY_QML)))

    roots = engine.rootObjects()
    if not roots:
        return 1
    window = roots[0]
    window_scaling = install_window_scaling(window)  # noqa: F841  keep alive
    if len(sys.argv) > 3:
        window.resize(int(sys.argv[2]), int(sys.argv[3]))

    def grab() -> None:
        window.grabWindow().save(str(out))
        app.quit()

    # One second of event loop lets fonts, layouts and the Canvas settle.
    QTimer.singleShot(1000, grab)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
