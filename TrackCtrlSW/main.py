"""Application entry point for the Track Controller (Software) module.

Run ``python main.py`` for the Track Controller UI. Run ``python
test_main.py`` in a second terminal for the test UI, which stimulates
this process as the CTC, the Track Model and the programmer.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from track_ctrl.qtenv import add_qt_dll_directory

# Must run before the QML engine is built; see track_ctrl/qtenv.py.
add_qt_dll_directory()

from PySide6.QtCore import QUrl  # noqa: E402  must follow the DLL fix
from PySide6.QtGui import QFont, QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402

from track_ctrl.link import StimulusServer  # noqa: E402
from track_ctrl.state import TrackControllerState  # noqa: E402
from track_ctrl.theme import build_theme  # noqa: E402

_MAIN_QML = Path(__file__).resolve().parent / "ui" / "Main.qml"


def main() -> int:
    """Create the app, load the QML views, and run the event loop."""
    parser = argparse.ArgumentParser(description="Track Controller (SW)")
    parser.add_argument(
        "--no-test-link",
        action="store_true",
        help="do not listen for the separate test UI",
    )
    options, qt_arguments = parser.parse_known_args()

    app = QGuiApplication([sys.argv[0], *qt_arguments])
    app.setApplicationName("Track Controller")

    theme = build_theme()
    font = QFont()
    font.setFamily(theme["ui_family"])
    font.setPixelSize(theme["size_body"])
    app.setFont(font)

    # Keep Python-side references so the objects are not garbage
    # collected while QML holds only C++ pointers to them.
    state = TrackControllerState()

    link: StimulusServer | None = None
    if not options.no_test_link:
        link = StimulusServer(state)
        if link.start():
            print(
                f"Test link listening on '{link.name}'. "
                "Run test_main.py to stimulate this controller.",
                file=sys.stderr,
            )
        else:
            print(
                f"Test link unavailable: {link.error_text()}",
                file=sys.stderr,
            )

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    if context is None:
        print("Failed to obtain the QML root context.", file=sys.stderr)
        return 1

    context.setContextProperty("theme", theme)
    context.setContextProperty("wayside", state)

    engine.load(QUrl.fromLocalFile(str(_MAIN_QML)))
    if not engine.rootObjects():
        print("Failed to load QML views.", file=sys.stderr)
        return 1

    exit_code = app.exec()
    if link is not None:
        link.stop()
    # Tear down QML before the context objects it binds to, so bindings
    # do not re-evaluate against deleted objects during shutdown.
    del engine
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
