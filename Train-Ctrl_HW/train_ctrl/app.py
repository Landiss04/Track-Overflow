"""Open the console and the bench.

main.py decides which windows; this builds the Qt application, the
backend QML reads as `controller`, and the windows themselves. The
bench on its own (run_bench) opens each line's console as trains are
spawned on it. Given a central harness's fleet, the harness spawns
and steps the trains and the console shows them. The self-check runs
one console and the bench on one backend (run).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QUrl, qInstallMessageHandler
from PySide6.QtGui import QFont, QGuiApplication, QWindow
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent, QQmlContext
# Imported for its side effect: it registers QQuickWindow, so the
# windows QML creates expose grabWindow() to the self-check.
from PySide6.QtQuick import QQuickWindow  # noqa: F401
import shiboken6

from ui.aspect_lock import install_window_scaling

from .fleet import TrainControllerFleet
from .backend import ConsoleBackend
from .bench import BenchBackend
from .console_theme import build_console_theme, check_shared_library
from .constants import VARIANT_LINES

# train_ctrl/app.py -> Train-Ctrl_HW/ui_parts
_UI_DIR = Path(__file__).resolve().parents[1] / "ui_parts"
_CONSOLE_QML = _UI_DIR / "ConsoleWindow.qml"
_TEST_QML = _UI_DIR / "TestWindow.qml"


def _start_app() -> tuple[QGuiApplication, dict[str, Any]]:
    # The application and the console theme, set up the same way for
    # every set of windows.
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    app.setApplicationName("Train Controller")
    theme = build_console_theme()
    base_font = QFont()
    base_font.setFamily(theme["ui_family"])
    base_font.setPixelSize(theme["size_body"])
    app.setFont(base_font)
    return app, theme


def run_bench() -> int:
    """Open the bench alone; spawning a train opens its line's console.

    Red Line trains open the HW Train Controller, Green Line trains the
    SW one, each on its own backend and titled as under the harness
    (REQUIREMENTS.md M13, OPEN_ISSUES.md #45). Closing a console hides
    it; the next spawn on its line shows it again.
    """
    app, theme = _start_app()
    if not check_shared_library():
        return 1
    engine = QQmlApplicationEngine()
    root = engine.rootContext()
    root.setContextProperty("theme", theme)
    # Per backend: its context, its window and the window's scaling,
    # kept so none is collected while the window is open.
    consoles: dict[int, tuple[QQmlContext, QWindow, Any]] = {}

    def open_console(backend: ConsoleBackend) -> None:
        if id(backend) not in consoles:
            context = QQmlContext(root, root)
            context.setContextProperty("controller", backend)
            component = QQmlComponent(
                engine, QUrl.fromLocalFile(str(_CONSOLE_QML)))
            window = component.create(context)
            if not isinstance(window, QWindow):
                print(component.errorString(), file=sys.stderr)
                return
            consoles[id(backend)] = (
                context, window, install_window_scaling(window))
        window = consoles[id(backend)][1]
        window.show()
        window.raise_()

    bench = BenchBackend(open_console)
    root.setContextProperty("controller", bench)
    engine.load(QUrl.fromLocalFile(str(_TEST_QML)))
    windows = engine.rootObjects()
    if len(windows) != 1 or not isinstance(windows[0], QWindow):
        print(f"Failed to load {_TEST_QML}", file=sys.stderr)
        return 1
    lock = install_window_scaling(windows[0])  # noqa: F841
    exit_code = app.exec()
    # The windows go first, then the engine, while the backends they
    # read as `controller` still exist: freed the other way round, every
    # binding reads a null controller on its way out.
    for _context, window, _lock in consoles.values():
        shiboken6.delete(window)
    shiboken6.delete(engine)
    consoles.clear()
    return exit_code


def run(console: bool, bench: bool, check: bool = False,
        shots: Path | None = None,
        fleet: TrainControllerFleet | None = None,
        variant: str = "HW") -> int:
    """Open the requested windows and run until they close.

    ``fleet`` is a central harness's TrainControllerFleet; without
    one the console owns its own. ``variant`` is "SW" or "HW": the
    console is titled for it and, under a harness, lists only its
    line's trains (SW Green, HW Red). With ``check`` it runs offscreen
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

    app, theme = _start_app()

    # Keep a Python reference so it is not garbage collected while
    # QML holds only a C++ pointer to it.
    backend = ConsoleBackend(
        fleet=fleet, variant=variant,
        line=VARIANT_LINES[variant] if fleet is not None else "")

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
