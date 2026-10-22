"""The Track Model process the central harness starts.

``track_overflow.py --module track-model --harness <server>`` runs
this. It holds the one Track Model, for the Green and Red Lines (the
Blue Line is not loaded, D023), shows the Track Model window, and steps
the model once per ``STEP`` from the harness (D005, D006). Closing the
window hides it; only the harness ends the process.

Each ``STEP``'s inputs are the Track Model's own, in the JSON form of
``track_model.wire``: the Track Controller's commands and each train's
report from its Train Model, already mapped by the harness, with
blocks in the Track Model's names (``"GREEN K-63"``). The step's
simulation time goes to the window, which shows it as the time of day
(D017). The reply is the Track Model's outputs, in the same form.

Invalid inputs refuse the whole tick, and the model changes nothing
(``TrackModel.step``); the harness logs the refusal and the Track
Model keeps its last outputs. What a person does in the window, such
as a failure Murphy injects or the ambient temperature, takes effect at
once and shows in the next reply.

The reply goes out before the window redraws, and the window redraws
at most every ``WINDOW_REFRESH_MS`` while steps arrive. Its tables are
large: redrawing them takes milliseconds on every tick, and up to a
second when a train appears or leaves, which would hold up every
reply at 10x.
"""

from __future__ import annotations

__all__ = ["LAYOUT_FILES", "TrackModelProcess", "layout_paths", "main"]

import argparse
import signal
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtGui import QGuiApplication, QWindow
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from track_model.interface import TrackConfig, TrackModelError
from track_model.model import TrackModel
from track_model.state import TrackModelState
from track_model.wire import decode_inputs, encode_outputs
from ui.aspect_lock import install_window_scaling
from ui.theme import build_theme
from utils.module_link import ModuleLink, TickRejectedError
from utils.module_window import keep_windows_open

#: This module's name, as the harness knows it.
MODULE_NAME = "track-model"

#: The layout files the system runs on (D023: Green and Red only).
LAYOUT_FILES = ("green_line.json", "red_line.json")

EXIT_QUIT = 0
EXIT_HARNESS_LOST = 2
EXIT_NO_WINDOW = 1

#: Real milliseconds between window redraws while steps arrive.
WINDOW_REFRESH_MS = 100

# The module's folder, holding its layout files and its window: in
# the repository, or in a built executable's bundle, laid out the same.
_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
_MODULE_DIR = _ROOT / "TrackModel"
_ENTRY_QML = _MODULE_DIR / "ui" / "Main.qml"


def layout_paths() -> tuple[str, ...]:
    """Return the paths of the layout files the system runs on."""
    return tuple(str(_MODULE_DIR / name) for name in LAYOUT_FILES)


class TrackModelProcess(QObject):
    """Drive a ``TrackModel`` from the harness."""

    #: The harness ended the process, or went away; the exit code.
    finished = Signal(int)

    def __init__(
        self,
        model: TrackModel,
        state: TrackModelState,
        server_name: str,
        parent: QObject | None = None,
    ) -> None:
        """Prepare to drive ``model``; ``start`` connects.

        Args:
            model: The Track Model.
            state: The window's view of it, refreshed after each step.
            server_name: The harness's local server.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._model = model
        self._state = state
        # The window redraws after a step's reply, not before it.
        self._redraw = QTimer(self)
        self._redraw.setSingleShot(True)
        self._redraw.setInterval(WINDOW_REFRESH_MS)
        self._redraw.timeout.connect(state.refresh)
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
        """Step the model once on ``inputs``; return its outputs.

        Raises:
            TickRejectedError: If the inputs are malformed or invalid.
                The model is unchanged.
        """
        try:
            outputs = self._model.step(dt, decode_inputs(inputs, sim_time_s))
        except TrackModelError as error:
            raise TickRejectedError(str(error)) from error
        self._state.mark_step()
        if not self._redraw.isActive():
            self._redraw.start()
        return encode_outputs(outputs)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Track Model process until the harness ends it.

    Args:
        argv: Options after ``--module track-model``.

    Returns:
        The exit code.
    """
    parser = argparse.ArgumentParser(
        prog="track_overflow.py --module track-model",
        description="The Track Model process the harness starts.",
    )
    parser.add_argument(
        "--harness", required=True, help="the harness's local server"
    )
    options = parser.parse_args(argv)
    # Only the harness ends a module (D005); Ctrl+C in the console is
    # the harness's to handle.
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    app = QGuiApplication(sys.argv[:1])
    app.setApplicationName("Track Model")
    # The Basic style is the only one that honours the window's custom
    # control templates (as TrackModel/main.py has it).
    QQuickStyle.setStyle("Basic")
    keep_windows_open(app)

    model = TrackModel(TrackConfig(layout_paths()))
    state = TrackModelState(model)
    process = TrackModelProcess(model, state, options.harness, parent=state)
    process.finished.connect(app.exit)

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    # build_theme() resolves font families, so it needs the app first.
    context.setContextProperty("theme", build_theme())
    context.setContextProperty("trackModel", state)
    engine.load(QUrl.fromLocalFile(str(_ENTRY_QML)))
    roots = engine.rootObjects()
    if not roots or not isinstance(roots[0], QWindow):
        print(f"Failed to load {_ENTRY_QML}", file=sys.stderr)
        return EXIT_NO_WINDOW
    window_scaling = install_window_scaling(  # noqa: F841  keep alive
        roots[0]
    )

    process.start()
    exit_code = app.exec()
    # Tear down QML before the state it binds to.
    del engine
    return exit_code
