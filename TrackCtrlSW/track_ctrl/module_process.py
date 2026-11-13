"""The Track Controller SW process the central harness starts.

``track_overflow.py --module track-controller-sw --harness <server>``
runs this. It holds the waysides of the Green Line, the line this
variant runs (R77; the HW variant runs the Red), shows the Track
Controller window, and scans every wayside once per ``STEP`` from the
harness (D005, D006). Closing the window hides it; only the harness
ends the process. The test link (``track_ctrl.link``) is not opened:
the harness is the module's one driver.

Each ``STEP``'s inputs are the module's own, in the JSON form of
``track_ctrl.wire`` without the time: the CTC Office's suggestions,
closed blocks and switch commands, and the Track Model's occupancy and
device read-back, already mapped by the harness
(``common/harness/wayside_edges.py``). The time is the step's
simulation time, unwrapped (D017), which the window shows as the time
of day. The reply is the module's outputs, in the same form.

Startup is a person's (R44): a PLC program committed on every wayside,
from the window (RUN then COMMIT on each, or Load starters). Until then
the module is not ready, says so in every wayside's report, and drives
only its fail-safe outputs; the clock runs on regardless.
``--load-starters`` commits the generated starter programs at launch
instead, for tests and demonstrations.

Invalid inputs refuse the whole tick and change nothing
(``SwTrackController.step``); the harness logs the refusal and keeps
the module's last outputs. The window redraws on its own timer, at
most every ``state.UI_REFRESH_MS``, never inside a step.

The harness tells a module nothing of the clock but the time of each
step, so the window's header shows the clock running while steps
arrive, and paused once none has come for ``CLOCK_IDLE_MS``. Its 10x
badge stays hidden: the speed is not known here.
"""

from __future__ import annotations

__all__ = ["MODULE_NAME", "TrackControllerProcess", "green_line", "main"]

import argparse
import signal
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from track_ctrl.qtenv import add_qt_dll_directory

# Must run before the QML engine is built; see track_ctrl/qtenv.py.
add_qt_dll_directory()

from PySide6.QtCore import QObject, QTimer, QUrl, Signal  # noqa: E402
from PySide6.QtGui import QFont, QGuiApplication, QWindow  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402

from track_ctrl.errors import TrackControllerError  # noqa: E402
from track_ctrl.layout import (  # noqa: E402
    LineLayout,
    default_layout_dir,
    load_layout_file,
)
from track_ctrl.state import TrackControllerState  # noqa: E402
from track_ctrl.theme import build_theme  # noqa: E402
from track_ctrl.wire import inputs_from_wire, outputs_to_wire  # noqa: E402
from utils.module_link import ModuleLink, TickRejectedError  # noqa: E402
from utils.module_window import keep_windows_open  # noqa: E402

#: This module's name, as the harness knows it.
MODULE_NAME = "track-controller-sw"

#: The layout of the one line this variant runs (R77).
GREEN_LAYOUT = "green_line.json"

#: Real milliseconds without a step after which the header shows the
#: clock paused. A step comes every 100 ms at 1x.
CLOCK_IDLE_MS = 1000

EXIT_QUIT = 0
EXIT_NO_WINDOW = 1
EXIT_HARNESS_LOST = 2

# The module's folder, holding its window: in the repository, or in a
# built executable's bundle, laid out the same.
_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
_ENTRY_QML = _ROOT / "TrackCtrlSW" / "ui" / "Main.qml"


def green_line() -> LineLayout:
    """Return the Green Line, divided among its default waysides.

    Raises:
        LayoutError: If the layout file is missing or malformed.
    """
    parsed = load_layout_file(default_layout_dir() / GREEN_LAYOUT)
    return parsed.divide()


class TrackControllerProcess(QObject):
    """Drive the Track Controller from the harness."""

    #: The harness ended the process, or went away; the exit code.
    finished = Signal(int)

    def __init__(
        self,
        state: TrackControllerState,
        server_name: str,
        parent: QObject | None = None,
    ) -> None:
        """Prepare to drive ``state``'s module; ``start`` connects.

        Args:
            state: The window's state, which holds the module.
            server_name: The harness's local server.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._state = state
        self._running = False
        # Steps stopping for a while is all that says the clock paused.
        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.setInterval(CLOCK_IDLE_MS)
        self._idle.timeout.connect(lambda: self._show_running(False))
        self._link = ModuleLink(MODULE_NAME, server_name, self.step, self)
        self._link.quitRequested.connect(
            lambda: self.finished.emit(EXIT_QUIT)
        )
        self._link.harnessLost.connect(
            lambda: self.finished.emit(EXIT_HARNESS_LOST)
        )

    def start(self) -> None:
        """Connect, and say ``READY`` once the event loop runs."""
        self._link.connect_to_harness()
        QTimer.singleShot(0, self._link.announce_ready)

    def step(
        self,
        tick: int,
        dt: float,
        sim_time_s: float,
        inputs: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Scan every wayside once on ``inputs``; return the outputs.

        Raises:
            TickRejectedError: If the inputs are malformed or invalid.
                The module is unchanged.
        """
        if "time_s" in inputs:
            # The time is the step's, never an input's to override.
            raise TickRejectedError("inputs has the wrong keys: time_s")
        try:
            decoded = inputs_from_wire({"time_s": sim_time_s, **inputs})
            outputs = self._state.step(dt, decoded)
        except TrackControllerError as error:
            raise TickRejectedError(str(error)) from error
        if not self._running:
            self._show_running(True)
        self._idle.start()
        return outputs_to_wire(outputs)

    def _show_running(self, running: bool) -> None:
        # The header's Paused badge, from whether steps arrive.
        self._running = running
        self._state.set_clock_status(not running, 1)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Track Controller process until the harness ends it.

    Args:
        argv: Options after ``--module track-controller-sw``.

    Returns:
        The exit code.
    """
    parser = argparse.ArgumentParser(
        prog="track_overflow.py --module track-controller-sw",
        description="The Track Controller SW process the harness starts.",
    )
    parser.add_argument(
        "--harness", required=True, help="the harness's local server"
    )
    parser.add_argument(
        "--load-starters",
        action="store_true",
        help="commit a starter program to every wayside at launch, "
        "instead of a person loading each (R44)",
    )
    options = parser.parse_args(argv)
    # Only the harness ends a module (D005); Ctrl+C in the console is
    # the harness's to handle.
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    from ui.aspect_lock import install_window_scaling

    app = QGuiApplication(sys.argv[:1])
    app.setApplicationName("Track Controller")
    keep_windows_open(app)
    theme = build_theme()
    font = QFont()
    font.setFamily(theme["ui_family"])
    font.setPixelSize(theme["size_body"])
    app.setFont(font)

    state = TrackControllerState(lines=(green_line(),))
    if options.load_starters:
        state.loadStarterPrograms()
    process = TrackControllerProcess(state, options.harness, parent=state)
    process.finished.connect(app.exit)

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    context.setContextProperty("theme", theme)
    context.setContextProperty("wayside", state)
    engine.load(QUrl.fromLocalFile(str(_ENTRY_QML)))
    roots = engine.rootObjects()
    if not roots or not isinstance(roots[0], QWindow):
        print(f"Failed to load {_ENTRY_QML}", file=sys.stderr)
        return EXIT_NO_WINDOW
    # Holds the window at 16:10 while it is dragged; keep it alive.
    window_scaling = install_window_scaling(  # noqa: F841
        roots[0]
    )

    process.start()
    exit_code = app.exec()
    # Tear down QML before the state it binds to.
    del engine
    return exit_code
