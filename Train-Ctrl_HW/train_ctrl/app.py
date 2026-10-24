"""Open the console and the bench, wired to one backend.

main.py decides which windows; this builds the Qt application, the
backend QML reads as `controller`, and the windows themselves.
Standalone, the backend starts with an empty roster and the bench
spawns trains. Given a central harness's fleet, the harness spawns
and steps them and the console shows them.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QUrl, qInstallMessageHandler
from PySide6.QtGui import QFont, QGuiApplication, QWindow
from PySide6.QtQml import QQmlApplicationEngine
# Imported for its side effect: it registers QQuickWindow, so the
# windows QML creates expose grabWindow() to the self-check.
from PySide6.QtQuick import QQuickWindow  # noqa: F401

from ui.aspect_lock import install_window_scaling

from .fleet import TrainControllerFleet
from .backend import ConsoleBackend
from .console_theme import build_console_theme, check_shared_library

# train_ctrl/app.py -> Train-Ctrl_HW/ui_parts
_UI_DIR = Path(__file__).resolve().parents[1] / "ui_parts"
_CONSOLE_QML = _UI_DIR / "ConsoleWindow.qml"
_TEST_QML = _UI_DIR / "TestWindow.qml"


def run(console: bool, bench: bool, check: bool = False,
        shots: Path | None = None, 
        fleet: TrainControllerFleet | None = None) -> int:
    """Open the requested windows and run until they close.

    ``fleet`` is a central harness's TrainControllerFleet; without
    one the console owns its own. With ``check`` it runs offscreen
    instead, drives a session through both windows, and returns
    non-zero on any problem.
    """
    if check:
        # Must be set before QGuiApplication is constructed.
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    warnings: list[str] = []
    if check:
        qInstallMessageHandler(
            lambda kind, context, message: warnings.append(message))

    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    app.setApplicationName("Train Controller")

    theme = build_console_theme()
    base_font = QFont()
    base_font.setFamily(theme["ui_family"])
    base_font.setPixelSize(theme["size_body"])
    app.setFont(base_font)

    # Keep a Python reference so it is not garbage collected while
    # QML holds only a C++ pointer to it.
    backend = ConsoleBackend(fleet=fleet)

    if not check_shared_library():
        return 1
    # check.py is a development self-check and does not ship with the
    # integration, so the console imports it only when asked to run it.
    contract_ok = True
    if check:
        from check import check_snapshot_contract, run_check
        contract_ok = check_snapshot_contract(backend, _UI_DIR)

    engine = QQmlApplicationEngine()
    # Keep our own copy of QML errors so a failed load explains
    # itself on stderr even when a debugger swallows Qt's log.
    qml_errors: list[str] = []
    engine.warnings.connect(
        lambda issues: qml_errors.extend(i.toString() for i in issues))
    context = engine.rootContext()
    if context is None:
        print("Failed to obtain the QML root context.", file=sys.stderr)
        return 1
    context.setContextProperty("theme", theme)
    context.setContextProperty("controller", backend)

    wanted = [qml for qml, on in ((_CONSOLE_QML, console),
                                  (_TEST_QML, bench)) if on]
    for qml in wanted:
        engine.load(QUrl.fromLocalFile(str(qml)))
    if len(engine.rootObjects()) != len(wanted):
        print("Failed to load "
              + ", ".join(str(q) for q in wanted), file=sys.stderr)
        for issue in qml_errors:
            print(f"  {issue}", file=sys.stderr)
        return 1

    roots: list[QWindow] = []
    for w in engine.rootObjects():
        if not isinstance(w, QWindow):
            print(f"QML root {w!r} is not a Window.", file=sys.stderr)
            return 1
        roots.append(w)

    # Each window scales on its own; the locks stay alive with them.
    locks = [install_window_scaling(w) for w in roots]  # noqa: F841
    windows = {qml.stem: w for qml, w in zip(wanted, roots)}

    if check:
        code = run_check(
            app, windows["ConsoleWindow"], windows["TestWindow"],
            backend, warnings, shots,
        )
        code = code or (0 if contract_ok else 1)
        qInstallMessageHandler(None)
        del engine
        return code

    exit_code = app.exec()
    # Tear down QML before the objects it binds to, so bindings do not
    # re-evaluate against deleted objects during shutdown.
    del engine
    return exit_code