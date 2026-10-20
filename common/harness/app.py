"""Run the central harness with a window, or a headless console.

No arguments open the operator window. ``--headless`` echoes events
and prints a status line every five seconds. Both run until Ctrl+C,
the time limit, or a confirmed window close. The CTC Office
presses Run when ready; the harness window has no clock controls.

The modules wired in so far run as themselves, each in its window
(Phase 4: the CTC Office, the Track Controller SW, the Track Model, the
Train Model and the Train Controller SW); the rest are stubs. The CTC
Office presses Run as soon as it is ready (``--run-on-ready``), as its
stub did before; the dispatcher can pause it in its window.

People start the run, as in the system itself. One loads a PLC program
on every wayside in the Track Controller's window (R44): RUN then
COMMIT on each, or Load starters. ``--load-starters`` commits the
starter programs at launch instead. The dispatcher dispatches a train
from the yard in the CTC Office's window; ``--dispatch
TRAIN:LINE:BLOCK`` gives that dispatch for a demonstration, once the
line is ready. And the train moves once an engineer sets its gains in
the Train Controller's console (D024). ``--stubs-only`` runs a stub for
every module instead, as in Phase 0.

The CSV goes to ``--log-dir``, defaulting to the user's application
data folder (``TrackOverflow/logs``), never the installation.
"""

from __future__ import annotations

__all__ = ["APPLICATION_NAME", "main"]

import argparse
import signal
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QStandardPaths, QTimer

from common.harness.core import Harness
from common.harness.edges import SystemEdges
from common.harness.modules import (
    CTC_OFFICE,
    TRACK_CONTROLLER_SW,
    stub_specs,
    system_specs,
)
from common.harness.supervisor import HarnessStartError
from utils.event_log import EventLog

APPLICATION_NAME = "TrackOverflow"

EXIT_OK = 0
EXIT_FAILED = 1

STATUS_INTERVAL_S = 5.0
# Python runs a signal handler only between Qt events, so a timer
# keeps them coming.
SIGNAL_POLL_MS = 200
MILLISECONDS_PER_SECOND = 1000


def main(argv: Sequence[str] | None = None) -> int:
    """Run until a confirmed close, Ctrl+C or ``--run-seconds``.

    Args:
        argv: Options; defaults to the command line.

    Returns:
        0 if every module ended cleanly, 1 otherwise.
    """
    options = _parse_args(argv)
    if options.headless:
        app = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])
    else:
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    app.setApplicationName(APPLICATION_NAME)
    log_dir = options.log_dir or _default_log_dir()
    ctc_options = ["--run-on-ready"]
    if options.speedup:
        ctc_options += ["--speedup-at-tick", "0"]
    if options.stubs_only:
        specs = stub_specs({CTC_OFFICE: ctc_options})
        edges = None
    else:
        wayside_options = ["--load-starters"] if options.load_starters else []
        for order in options.dispatch:
            ctc_options += ["--dispatch", order]
        specs = system_specs({
            CTC_OFFICE: ctc_options,
            TRACK_CONTROLLER_SW: wayside_options,
        })
        edges = SystemEdges()
    # A file of its own, even beside a run started in the same second.
    with EventLog.create(log_dir, datetime.now()) as log:
        harness = Harness(specs, log, edges)
        window = None
        if options.headless:
            status = _StatusLine(harness)
            harness.eventLogged.connect(status.print_event)
            harness.tickCompleted.connect(status.count_tick)
        else:
            from common.harness.console import HarnessConsole
            from common.harness.window import HarnessWindow

            console = HarnessConsole(harness)
            console.endRunRequested.connect(lambda: app.exit(EXIT_OK))
            try:
                window = HarnessWindow(app, console)
            except RuntimeError as error:
                print(str(error), file=sys.stderr)
                return EXIT_FAILED
        print(f"Event log: {log.path}", flush=True)
        try:
            harness.start()
        except HarnessStartError as error:
            print(f"Cannot start the harness: {error}", file=sys.stderr)
            if window is not None:
                window.close()
            return EXIT_FAILED

        def stop_and_quit() -> None:
            # From Ctrl+C or the run limit. Stopping twice is harmless.
            # Shutdown runs after leaving the UI loop, using the same
            # QUIT/wait/kill behavior as the headless console.
            app.exit(EXIT_OK)

        signal.signal(
            signal.SIGINT, lambda *_: QTimer.singleShot(0, stop_and_quit)
        )
        signal_timer = QTimer()
        signal_timer.timeout.connect(lambda: None)
        signal_timer.start(SIGNAL_POLL_MS)
        status_timer = QTimer()
        if options.headless:
            status_timer.timeout.connect(status.print_status)
            status_timer.start(
                round(STATUS_INTERVAL_S * MILLISECONDS_PER_SECOND)
            )
        if options.run_seconds is not None:
            QTimer.singleShot(
                round(options.run_seconds * MILLISECONDS_PER_SECOND),
                stop_and_quit,
            )
        app.exec()
        exit_codes = harness.stop()
        if window is not None:
            window.close()
    clean = all(code == 0 for code in exit_codes.values())
    return EXIT_OK if clean else EXIT_FAILED


class _StatusLine:
    """Echo events, and sum up the run every few seconds."""

    def __init__(self, harness: Harness) -> None:
        """Watch ``harness``."""
        self._harness = harness
        self._ticks = 0
        self._total_s = 0.0
        self._max_s = 0.0

    def print_event(self, source: str, event: str, detail: str) -> None:
        """Print one logged event."""
        clock = self._harness.clock
        line = f"{clock.format_time_of_day()} tick {clock.tick_count:>6} "
        line += f"{source:<20} {event}"
        if detail:
            line += f": {detail}"
        print(line, flush=True)

    def count_tick(self, _tick: int, round_trip_s: float) -> None:
        """Add one tick's round trip to the next status line."""
        self._ticks += 1
        self._total_s += round_trip_s
        self._max_s = max(self._max_s, round_trip_s)

    def print_status(self) -> None:
        """Print the clock, readiness and recent round trips."""
        harness = self._harness
        clock = harness.clock
        state = "PAUSED" if clock.is_paused else "RUNNING"
        line = (
            f"{clock.format_time_of_day()} {state} {clock.speed}x, "
            f"tick {clock.tick_count}, "
            f"{len(harness.ready_modules)} ready"
        )
        if self._ticks:
            mean_ms = self._total_s / self._ticks * MILLISECONDS_PER_SECOND
            max_ms = self._max_s * MILLISECONDS_PER_SECOND
            line += (
                f", {self._ticks} ticks, round trip mean {mean_ms:.1f} ms,"
                f" max {max_ms:.1f} ms"
            )
        if harness.dropped_ticks:
            line += f", {harness.dropped_ticks} ticks dropped"
        print(line, flush=True)
        self._ticks = 0
        self._total_s = 0.0
        self._max_s = 0.0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    # The harness's options.
    parser = argparse.ArgumentParser(
        prog="track_overflow.py",
        description="Run the Track Overflow harness and its modules.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="use console output without opening a window",
    )
    parser.add_argument(
        "--dispatch",
        action="append",
        default=[],
        metavar="TRAIN:LINE:BLOCK",
        help="dispatch a train from the yard to a block in the CTC "
        "Office once its line is ready, for a demonstration; may be "
        "repeated",
    )
    parser.add_argument(
        "--load-starters",
        action="store_true",
        help="commit the Track Controller's starter PLC programs at "
        "launch, instead of loading them in its window",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        help="folder for the event log (default: the user's local "
        "application data folder)",
    )
    parser.add_argument(
        "--run-seconds",
        type=float,
        help="stop after this many real seconds",
    )
    parser.add_argument(
        "--speedup",
        action="store_true",
        help="run at 10x from the start",
    )
    parser.add_argument(
        "--stubs-only",
        action="store_true",
        help="run a stub for every module, as in Phase 0",
    )
    return parser.parse_args(argv)


def _default_log_dir() -> Path:
    # The user's local application data folder, which the built
    # executable can always write to.
    location = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppLocalDataLocation
    )
    return (Path(location) if location else Path.cwd()) / "logs"
