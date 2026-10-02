"""Entry point for the CTC Office test UI.

The test UI runs as its own process, separate from the CTC Office UI.
Start it from the ``CTC-Office`` directory with either::

    python ctc_ui/test_ui.py
    python -m ctc_ui.test_ui

It is for testing the CTC Office on its own: it stands in for the
Track Controller and the Track Model, the two modules the CTC talks
to, plus the dispatcher actions of the CTC UI. Once the modules are
integrated, the central harness connects them to the CTC through the
same boundary (``ctc/interface.py``) and this test UI is not used.

The CTC Office module runs inside this process, reached only through
``ctc.link.LocalLink``. A socket link to a CTC Office in its own process
can replace it later without changing the module or this UI.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import cast

from PySide6.QtCore import QUrl
from PySide6.QtGui import QFont, QGuiApplication, QWindow
from PySide6.QtQml import QQmlApplicationEngine

# The design tokens and window scaling are shared by every module's UI,
# so they live in the repository-level ui/ folder next to the shared QML
# components.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
# CTC-Office/, so the ``ctc`` module package imports however this file
# is started.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ui.app_icon import install_app_icon  # noqa: E402
from ui.aspect_lock import install_window_scaling  # noqa: E402
from ui.theme import build_theme  # noqa: E402

from ctc_ui.test_harness import CtcTestHarness  # noqa: E402

_TEST_MAIN_QML = (
    Path(__file__).resolve().parent / "ui" / "test" / "TestMain.qml"
)


def main() -> int:
    """Create the test UI app, load its window, and run the loop."""
    app = QGuiApplication(sys.argv)
    app.setApplicationName("CTC Office Test Harness")
    install_app_icon(app)

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
    # Keep a Python reference: QML holds only a C++ pointer to it.
    harness = CtcTestHarness()
    context.setContextProperty("harness", harness)

    engine.load(QUrl.fromLocalFile(str(_TEST_MAIN_QML)))
    if not engine.rootObjects():
        print("Failed to load the test UI.", file=sys.stderr)
        return 1

    # The root of a ScaledWindow is always a window. Keep a reference:
    # the lock's window procedure must outlive the window, or Windows
    # calls into freed memory.
    window_scaling = install_window_scaling(  # noqa: F841
        cast(QWindow, engine.rootObjects()[0]))

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
