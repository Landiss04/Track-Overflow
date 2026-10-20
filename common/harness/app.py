"""Run the central harness from the command line.

``python track_overflow.py`` lands here. The harness starts every
module and runs until Ctrl+C or ``--run-seconds``.

The modules wired in so far run as themselves (Phase 1: the Train
Model and the Train Controller SW, each in its window); the rest are
stubs. The CTC Office's stub presses Run as soon as it is ready and
releases train G1 onto the Green Line on the first tick. The Train
Model runs G1 over a fixed track feed with a stop at GLENBURY
(``track_feed.GREEN_STATION_STOP``). G1 moves once an engineer sets
its gains in the Train Controller's console (D024). ``--stubs-only``
runs a stub for every module instead, as in Phase 0.

The event log goes to ``--log-dir``, by default the user's local
application data folder (``TrackOverflow/logs``), never into the
installation. Every logged event is echoed to the console, with a line
of status every few seconds.
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
from common.harness.modules import CTC_OFFICE, stub_specs, system_specs
from common.harness.supervisor import HarnessStartError
from common.harness.track_feed import GREEN_STATION_STOP, FixedTrackFeed
from utils.event_log import EventLog, log_file_name

APPLICATION_NAME = "TrackOverflow"

#: The train the CTC Office's stub releases on the first tick.
FIRST_TRAIN = "G1"

EXIT_OK = 0
EXIT_FAILED = 1

STATUS_INTERVAL_S = 5.0
# Python runs a signal handler only between Qt events, so a timer
# keeps them coming.
SIGNAL_POLL_MS = 200
MILLISECONDS_PER_SECOND = 1000


def main(argv: Sequence[str] | None = None) -> int:
    """Run the harness until Ctrl+C or ``--run-seconds``.

    Args:
        argv: Options; defaults to the command line.

    Returns:
        0 if every module ended cleanly, 1 otherwise.
    """
    options = _parse_args(argv)
    app = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])
    app.setApplicationName(APPLICATION_NAME)
    log_dir = options.log_dir or _default_log_dir()
    log_path = log_dir / log_file_name(datetime.now())
    ctc_options = ["--run-on-ready"]
    if options.speedup:
        ctc_options += ["--speedup-at-tick", "0"]
    if options.stubs_only:
        specs = stub_specs({CTC_OFFICE: ctc_options})
        edges = None
    else:
        ctc_options += ["--release-train", f"{FIRST_TRAIN}:Green@1"]
        specs = system_specs({CTC_OFFICE: ctc_options})
        edges = SystemEdges(FixedTrackFeed(GREEN_STATION_STOP))
    with EventLog(log_path) as log:
        harness = Harness(specs, log, edges)
        status = _StatusLine(harness)
        harness.eventLogged.connect(status.print_event)
        harness.tickCompleted.connect(status.count_tick)
        print(f"Event log: {log_path}", flush=True)
        try:
            harness.start()
        except HarnessStartError as error:
            print(f"Cannot start the harness: {error}", file=sys.stderr)
            return EXIT_FAILED

        def stop_and_quit() -> None:
            # From Ctrl+C or the run limit. Stopping twice is harmless.
            harness.stop()
            app.quit()

        signal.signal(
            signal.SIGINT, lambda *_: QTimer.singleShot(0, stop_and_quit)
        )
        signal_timer = QTimer()
        signal_timer.timeout.connect(lambda: None)
        signal_timer.start(SIGNAL_POLL_MS)
        status_timer = QTimer()
        status_timer.timeout.connect(status.print_status)
        status_timer.start(round(STATUS_INTERVAL_S * MILLISECONDS_PER_SECOND))
        if options.run_seconds is not None:
            QTimer.singleShot(
                round(options.run_seconds * MILLISECONDS_PER_SECOND),
                stop_and_quit,
            )
        app.exec()
        exit_codes = harness.stop()
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
