"""The CTC Office process the central harness starts.

``track_overflow.py --module ctc-office --harness <server>`` runs this.
It holds the one CTC Office module, for the Green and Red Lines (the
Blue Line is out of scope, D023), shows the CTC Office window, and
steps the module once per ``STEP`` from the harness (D005, D006).
Closing the window hides it; only the harness ends the process.

The harness owns the clock (D005, D017). The window's own clock
(``ctc_ui.sim_clock``) and its clock link do not run here, and nor does
the test link (``ctc.socket_link``): the CTC test UI stands in for the
Track Controller only (D025), and the harness runs the Track
Controller itself. The window shows the time each step brings
(``ctc_ui.harness_clock``).

Each ``STEP``'s inputs are the module's own, in the JSON form of
``ctc.wire``: ``track_controller`` (occupancy, switches, crossings and
every wayside's readiness, from the Track Controllers) and
``track_model`` (ticket sales since the last step, from the Track
Model), already mapped by the harness
(``common/harness/wayside_edges.py``, ``track_edges.py``). The reply
is the module's outputs in the same form (``ctc.wire.to_wire``): the
suggestions, closed blocks and switch commands for the Track
Controller, ``clock_paused`` and ``clock_speedup`` for the harness, and
the one-time ``new_trains`` and ``retired_trains`` events for its
roster (D022).

Run, Pause and 1x / 10x pressed in the window set ``clock_paused`` and
``clock_speedup``. Nothing steps while the clock is paused, so each
press also goes to the harness at once, as ``STATE`` (R51). The clock
starts paused (D017).

Invalid inputs refuse the whole tick and change nothing
(``CtcOffice.step``); the harness logs the refusal and keeps the
module's last outputs. The module's time is each ``STEP``'s
``sim_time_s`` (D017), so a refused or missed tick does not put its
schedule behind the harness's time.

The reply goes out before the window redraws, and the window redraws
at most every ``WINDOW_REFRESH_MS`` while steps arrive. A dispatcher's
action redraws it at once, between ticks.

Test and demonstration options, never for a real run, stand in for the
dispatcher as ``--engineer-gains`` stands in for the engineer and
``--load-starters`` for the person who loads the PLC programs:

- ``--run-on-ready`` presses Run as soon as the process is ready;
- ``--speedup-at-tick N`` presses 10x after step ``N``, or before the
  first step with ``0``;
- ``--dispatch TRAIN:LINE:BLOCK`` dispatches a train from the yard to a
  block, once the line's waysides are ready (``CtcOffice.dispatch``
  refuses it before);
- ``--schedule FILE`` loads a schedule and runs it in automatic mode
  (D020).
"""

from __future__ import annotations

__all__ = [
    "MODULE_NAME",
    "WINDOW_REFRESH_MS",
    "CtcOfficeProcess",
    "Dispatch",
    "layout_files",
    "main",
]

import argparse
import signal
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtGui import QFont, QGuiApplication, QWindow
from PySide6.QtQml import QQmlApplicationEngine

from ctc.model import CtcError, ready_lines
from ctc.schedule import load_schedule
from ctc.scheduler import SIMULATION_START_S
from ctc.track_layout import load_layout
from ctc.wire import WireFormatError, inputs_from_wire, to_wire
from ctc_ui.ctc_host import SPEEDUP_FACTOR, CtcHost
from ctc_ui.harness_clock import HarnessClockBridge
from ctc_ui.track_map import TrackMapModel
from utils.module_link import ModuleLink, TickRejectedError
from utils.module_window import keep_windows_open

#: This module's name, as the harness knows it.
MODULE_NAME = "ctc-office"

#: Real milliseconds between window redraws while steps arrive.
WINDOW_REFRESH_MS = 200

#: The inputs a step may carry (``ctc.wire.inputs_from_wire``).
INPUT_KEYS = frozenset({"track_controller", "track_model"})

EXIT_QUIT = 0
EXIT_NO_WINDOW = 1
EXIT_HARNESS_LOST = 2

# The repository, or a built executable's bundle, laid out the same:
# the CTC Office's window, and the layout files it shares with the
# Track Model.
_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
_ENTRY_QML = _ROOT / "CTC-Office" / "ctc_ui" / "ui" / "Main.qml"
_LAYOUT_DIR = _ROOT / "TrackModel"


def layout_files() -> dict[str, Path]:
    """Return each line's layout file, found from source or a build."""
    return {
        "Green": _LAYOUT_DIR / "green_line.json",
        "Red": _LAYOUT_DIR / "red_line.json",
    }


@dataclass(frozen=True)
class Dispatch:
    """A dispatch the test option gives, as the dispatcher would.

    Attributes:
        train_id: The train's ID, as the dispatcher enters it (R47).
        line: Its line, ``Green`` or ``Red`` (R50).
        block_id: The block to send it to.
    """

    train_id: str
    line: str
    block_id: str


class CtcOfficeProcess(QObject):
    """Drive the CTC Office from the harness."""

    #: The harness ended the process, or went away; the exit code.
    finished = Signal(int)

    def __init__(
        self,
        host: CtcHost,
        server_name: str,
        *,
        run_on_ready: bool = False,
        speedup_at_tick: int | None = None,
        dispatches: Sequence[Dispatch] = (),
        parent: QObject | None = None,
    ) -> None:
        """Prepare to drive ``host``'s module; ``start`` connects.

        Args:
            host: The window's host, which holds the module.
            server_name: The harness's local server.
            run_on_ready: Press Run once ready (tests only).
            speedup_at_tick: Press 10x after this step; 0 before the
                first (tests only).
            dispatches: Dispatches to give once each line is ready
                (tests only).
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._host = host
        self._run_on_ready = run_on_ready
        self._speedup_at_tick = speedup_at_tick
        self._dispatches = list(dispatches)
        self._announced = False
        host.start_at(SIMULATION_START_S)
        self._clock = HarnessClockBridge(
            host, SIMULATION_START_S, self._push_controls, self
        )
        # The window redraws after a step's reply, not before it.
        self._redraw = QTimer(self)
        self._redraw.setSingleShot(True)
        self._redraw.setInterval(WINDOW_REFRESH_MS)
        self._redraw.timeout.connect(host.refresh)
        self._link = ModuleLink(MODULE_NAME, server_name, self.step, self)
        self._link.quitRequested.connect(
            lambda: self.finished.emit(EXIT_QUIT)
        )
        self._link.harnessLost.connect(
            lambda: self.finished.emit(EXIT_HARNESS_LOST)
        )

    @property
    def clock(self) -> HarnessClockBridge:
        """The window's clock: the harness's time, Run and Pause."""
        return self._clock

    @property
    def pending_dispatches(self) -> tuple[Dispatch, ...]:
        """Test dispatches not given yet: their line is not ready."""
        return tuple(self._dispatches)

    def start(self) -> None:
        """Connect, and say ``READY`` once the event loop runs."""
        self._link.connect_to_harness()
        QTimer.singleShot(0, self._announce)

    def step(
        self,
        tick: int,
        dt: float,
        sim_time_s: float,
        inputs: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Step the module once on ``inputs``; return its outputs.

        Raises:
            TickRejectedError: If the inputs are malformed or invalid,
                or ``dt`` is not finite and positive. The module is
                unchanged.
        """
        unknown = set(inputs) - INPUT_KEYS
        if unknown:
            raise TickRejectedError(
                "inputs has the wrong keys: " + ", ".join(sorted(unknown))
            )
        try:
            decoded = inputs_from_wire(inputs)
        except (WireFormatError, TypeError, ValueError) as error:
            raise TickRejectedError(f"malformed inputs: {error}") from error
        try:
            outputs = self._host.step_at(dt, sim_time_s, decoded)
        except CtcError as error:
            raise TickRejectedError(str(error)) from error
        self._clock.show_time(sim_time_s)
        self._give_dispatches()
        if (
            self._speedup_at_tick is not None
            and tick >= self._speedup_at_tick
            and self._clock.speed != SPEEDUP_FACTOR
        ):
            # Pressed between ticks, after this reply, as a person
            # would: a STATE sent now would arrive before the reply.
            QTimer.singleShot(0, self._press_speedup)
        if not self._redraw.isActive():
            self._redraw.start()
        wire: dict[str, Any] = to_wire(outputs)
        return wire

    def _announce(self) -> None:
        # READY, then any press made before it, and the scripted ones.
        self._link.announce_ready()
        self._announced = True
        controls = self._clock.controls()
        if controls != {"clock_paused": True, "clock_speedup": False}:
            self._link.push_state(controls)
        if self._speedup_at_tick == 0:
            self._press_speedup()
        if self._run_on_ready:
            self._clock.resume()

    def _press_speedup(self) -> None:
        # 10x, as the dispatcher would press it.
        self._clock.setSpeed(SPEEDUP_FACTOR)

    def _push_controls(self, controls: dict[str, bool]) -> None:
        # A press reaches the harness at once (R51); one made before
        # READY waits for it, since READY must come first.
        if self._announced:
            self._link.push_state(controls)

    def _give_dispatches(self) -> None:
        # Each test dispatch once its line is ready, as the dispatcher
        # would give it; the module refuses one before (R44, R70).
        if not self._dispatches:
            return
        snapshot = self._host.module.snapshot()
        reports = snapshot.inputs
        ready = (
            ready_lines(reports.track_controller.waysides)
            if reports is not None else frozenset()
        )
        waiting = []
        for order in self._dispatches:
            if order.line not in ready:
                waiting.append(order)
                continue
            try:
                self._host.module.dispatch(
                    order.train_id, order.line, order.block_id
                )
            except CtcError as error:
                print(
                    f"[{MODULE_NAME}] dispatch of {order.train_id} "
                    f"refused: {error}",
                    file=sys.stderr,
                    flush=True,
                )
        self._dispatches = waiting


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CTC Office process until the harness ends it.

    Args:
        argv: Options after ``--module ctc-office``.

    Returns:
        The exit code.
    """
    options = _parse_args(argv)
    # Only the harness ends a module (D005); Ctrl+C in the console is
    # the harness's to handle.
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    # Imported here: the shared UI helpers need the application first.
    from ui.app_icon import install_app_icon
    from ui.aspect_lock import install_window_scaling
    from ui.theme import build_theme

    app = QGuiApplication(sys.argv[:1])
    app.setApplicationName("CTC Office")
    install_app_icon(app)
    keep_windows_open(app)
    theme = build_theme()
    font = QFont()
    font.setFamily(theme["ui_family"])
    font.setPixelSize(theme["size_body"])
    app.setFont(font)

    layout = load_layout(layout_files())
    host = CtcHost(layout=layout, serve_test_ui=False)
    if options.schedule is not None:
        try:
            host.module.load_schedule(load_schedule(options.schedule))
        except CtcError as error:
            print(f"Cannot load the schedule: {error}", file=sys.stderr)
            return EXIT_NO_WINDOW
    track_map = TrackMapModel(layout)
    process = CtcOfficeProcess(
        host,
        options.harness,
        run_on_ready=options.run_on_ready,
        speedup_at_tick=options.speedup_at_tick,
        dispatches=options.dispatch,
        parent=host,
    )
    process.finished.connect(app.exit)

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    context.setContextProperty("theme", theme)
    context.setContextProperty("trackMap", track_map)
    context.setContextProperty("ctc", host)
    context.setContextProperty("simClock", process.clock)
    engine.load(QUrl.fromLocalFile(str(_ENTRY_QML)))
    roots = engine.rootObjects()
    if not roots or not isinstance(roots[0], QWindow):
        print(f"Failed to load {_ENTRY_QML}", file=sys.stderr)
        return EXIT_NO_WINDOW
    window_scaling = install_window_scaling(  # noqa: F841  keep alive
        roots[0]
    )
    if options.schedule is not None:
        # The window opens in Automatic mode; a schedule runs in it.
        host.setAutomaticMode(True)

    process.start()
    exit_code = app.exec()
    # Tear down QML before the objects it binds to.
    del engine
    return exit_code


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    # The harness's server, and the test-only options.
    parser = argparse.ArgumentParser(
        prog="track_overflow.py --module ctc-office",
        description="The CTC Office process the harness starts.",
    )
    parser.add_argument(
        "--harness", required=True, help="the harness's local server"
    )
    tests = parser.add_argument_group(
        "tests and demonstrations only", "they stand in for the dispatcher"
    )
    tests.add_argument(
        "--run-on-ready",
        action="store_true",
        help="press Run as soon as the process is ready",
    )
    tests.add_argument(
        "--speedup-at-tick",
        type=_non_negative,
        help="press 10x after this step; 0 means before the first",
    )
    tests.add_argument(
        "--dispatch",
        type=_dispatch,
        action="append",
        default=[],
        metavar="TRAIN:LINE:BLOCK",
        help="dispatch a train from the yard to a block once its line "
        "is ready; may be repeated",
    )
    tests.add_argument(
        "--schedule",
        type=Path,
        help="load this schedule file and run it in automatic mode",
    )
    return parser.parse_args(argv)


def _non_negative(text: str) -> int:
    # A tick number.
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError(f"must not be negative: {text}")
    return value


def _dispatch(text: str) -> Dispatch:
    # TRAIN:LINE:BLOCK, such as G1:Green:65.
    parts = text.split(":")
    if len(parts) != 3 or not all(part.strip() for part in parts):
        raise argparse.ArgumentTypeError(
            f"expected TRAIN:LINE:BLOCK, got {text!r}"
        )
    return Dispatch(*(part.strip() for part in parts))
