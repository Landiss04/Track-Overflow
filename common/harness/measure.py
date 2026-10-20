"""Measure the harness's real-time budget (G-CLK-6).

Runs the harness with a stub for each of the seven modules, or with
``--system`` the system as wired so far, the clock at 1x or 10x, for a
set number of real seconds. It reports how long the modules took to be
ready (G-LIFE-2) and whether the run kept up: ticks completed against
the ticks due, the speed achieved, the round trip of each tick from
the first ``STEP`` sent to the last reply, ticks slipped behind real
time, late replies, and the harness's share of one CPU core. At 10x a
tick falls due every 10 ms, so the round trip must stay well under
that.

With ``--system`` the wired modules run as themselves, with their
windows: in Phase 4 the CTC Office, the Track Controller SW, the Track
Model, the Train Model and the Train Controller SW, running the
Iteration 3 scenario. The Track Controller loads its starter programs
(``--load-starters``), the CTC Office presses Run (and 10x) and
dispatches G1 from the yard to DORMONT (``--dispatch``), and the Train
Controller plays the engineer (``--engineer-gains``), so the train is
released and moves for the whole measurement.

Run from the repository root::

    python -m common.harness.measure --seconds 10 --payload-bytes 1000
    python -m common.harness.measure --window --seconds 10
    python -m common.harness.measure --system
"""

from __future__ import annotations

__all__ = ["main"]

import argparse
import statistics
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt, QTimer

from common.harness.core import Harness
from common.harness.edges import SystemEdges
from common.harness.modules import (
    CTC_OFFICE,
    MODULE_NAMES,
    TRACK_CONTROLLER_SW,
    TRAIN_CONTROLLER_SW,
    TRAIN_MODEL,
    WIRED_MODULES,
    stub_specs,
    system_specs,
)
from utils.event_log import EventLog
from utils.system_clock import ALLOWED_SPEEDS, DEFAULT_TICK_S

EXIT_OK = 0
EXIT_FAILED = 1

# Real seconds the modules have to start before the measurement gives
# up.
STARTUP_LIMIT_S = 60.0
MILLISECONDS_PER_SECOND = 1000
PERCENT = 100

# Where the CTC Office sends the measured train, standing in for the
# dispatcher: far enough that it runs for the whole measurement.
DISPATCH = "G1:Green:73"

# Kp and Ki the Train Controller sets on the measured train, standing
# in for the engineer (D024).
ENGINEER_GAINS = ("400000", "8000")


class _Meter:
    """Time a harness run from its first tick for a set while."""

    def __init__(self, harness: Harness, seconds: float) -> None:
        """Watch ``harness`` for ``seconds`` from its first tick."""
        self._harness = harness
        self._seconds = seconds
        self.round_trips_s: list[float] = []
        self.late_replies = 0
        self.launched_s = time.perf_counter()
        self.ready_s: float | None = None
        self.started_s: float | None = None
        self.ended_s: float | None = None
        self._cpu_started_s = 0.0
        self.cpu_s = 0.0
        self._end_timer = QTimer()
        self._end_timer.setSingleShot(True)
        self._end_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._end_timer.timeout.connect(self._end)
        harness.tickCompleted.connect(self._on_tick)
        harness.eventLogged.connect(self._on_event)
        harness.allReady.connect(self._on_all_ready)

    @property
    def done(self) -> bool:
        """Whether the measured while is over."""
        return self.ended_s is not None

    @property
    def ticks(self) -> int:
        """Ticks completed within the measured while."""
        return len(self.round_trips_s)

    @property
    def wall_s(self) -> float:
        """Real seconds measured."""
        if self.started_s is None or self.ended_s is None:
            return 0.0
        return self.ended_s - self.started_s

    def _on_tick(self, _tick: int, round_trip_s: float) -> None:
        # The clock starts from the first tick's start, so the first
        # tick counts.
        if self.done:
            return
        if self.started_s is None:
            self.started_s = time.perf_counter() - round_trip_s
            self._cpu_started_s = time.process_time()
            self._end_timer.start(
                round(self._seconds * MILLISECONDS_PER_SECOND)
            )
        self.round_trips_s.append(round_trip_s)

    def _on_all_ready(self) -> None:
        # Every module process is up and has said READY.
        self.ready_s = time.perf_counter()

    def _on_event(self, _source: str, event: str, _detail: str) -> None:
        # Count the replies that ran past the timeout.
        if event == "REPLY_LATE" and not self.done:
            self.late_replies += 1

    def _end(self) -> None:
        # Close the measured while and leave the event loop.
        self.ended_s = time.perf_counter()
        self.cpu_s = time.process_time() - self._cpu_started_s
        QCoreApplication.exit(EXIT_OK)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the measurement and print the report.

    Returns:
        0 if the run kept up with the clock, 1 if it fell behind or
        failed.
    """
    options = _parse_args(argv)
    if options.window:
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    else:
        app = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])
    app.setApplicationName("TrackOverflow")
    stub_options = {
        name: ["--payload-bytes", str(options.payload_bytes)]
        for name in MODULE_NAMES
    }
    stub_options[CTC_OFFICE] += ["--run-on-ready"]
    if options.speed != 1:
        stub_options[CTC_OFFICE] += ["--speedup-at-tick", "0"]
    if options.system:
        module_options = {
            name: values
            for name, values in stub_options.items()
            if name not in WIRED_MODULES
        }
        module_options[CTC_OFFICE] = [
            "--run-on-ready", "--dispatch", DISPATCH,
        ]
        if options.speed != 1:
            module_options[CTC_OFFICE] += ["--speedup-at-tick", "0"]
        module_options[TRACK_CONTROLLER_SW] = ["--load-starters"]
        module_options[TRAIN_CONTROLLER_SW] = [
            "--engineer-gains", *ENGINEER_GAINS
        ]
        specs = system_specs(module_options)
        edges = SystemEdges()
    else:
        specs = stub_specs(stub_options)
        edges = None
    with tempfile.TemporaryDirectory() as folder:
        with EventLog(Path(folder) / "events.csv") as log:
            harness = Harness(specs, log, edges)
            window = None
            if options.window:
                from common.harness.console import HarnessConsole
                from common.harness.window import HarnessWindow

                console = HarnessConsole(harness)
                console.select_module(
                    TRAIN_MODEL if options.system else CTC_OFFICE
                )
                console.endRunRequested.connect(lambda: app.exit(EXIT_OK))
                window = HarnessWindow(app, console)
            meter = _Meter(harness, options.seconds)
            meter.launched_s = time.perf_counter()
            harness.start()
            # Give up if the modules never start ticking.
            QTimer.singleShot(
                round(
                    (STARTUP_LIMIT_S + options.seconds)
                    * MILLISECONDS_PER_SECOND
                ),
                lambda: app.exit(EXIT_FAILED),
            )
            app.exec()
            dropped_ticks = harness.dropped_ticks
            exit_codes = harness.stop()
            if window is not None:
                window.close()
    if not meter.done:
        print("The modules never started ticking.", file=sys.stderr)
        return EXIT_FAILED
    kept_up = _report(options, meter, dropped_ticks)
    clean = all(code == 0 for code in exit_codes.values())
    return EXIT_OK if kept_up and clean else EXIT_FAILED


def _report(
    options: argparse.Namespace, meter: _Meter, dropped_ticks: int
) -> bool:
    # Print the measurement; return whether the run kept up.
    tick_interval_s = DEFAULT_TICK_S / options.speed
    due_ticks = meter.wall_s / tick_interval_s
    achieved_speed = meter.ticks * DEFAULT_TICK_S / meter.wall_s
    round_trips_ms = sorted(
        value * MILLISECONDS_PER_SECOND for value in meter.round_trips_s
    )
    startup_s = (meter.ready_s or meter.launched_s) - meter.launched_s
    first_step_ms = (
        (meter.started_s or meter.launched_s)
        - (meter.ready_s or meter.launched_s)
    ) * MILLISECONDS_PER_SECOND
    what = (
        "The system as wired, one train," if options.system
        else "Seven stub modules"
    )
    lines = [
        f"{what} at {options.speed}x, "
        f"{options.payload_bytes} bytes of filler per stub reply",
        f"  front end:       {'window' if options.window else 'headless'}",
        f"  startup:         {startup_s:.2f} s until every module was ready",
        f"  measured:        {meter.wall_s:.2f} s real time",
        f"  ready to step:   {first_step_ms:.2f} ms until first STEP",
        f"  ticks:           {meter.ticks} of {due_ticks:.0f} due",
        f"  speed achieved:  {achieved_speed:.2f}x",
        "  round trip (ms): "
        f"mean {statistics.fmean(round_trips_ms):.2f}, "
        f"median {_percentile(round_trips_ms, 50):.2f}, "
        f"p95 {_percentile(round_trips_ms, 95):.2f}, "
        f"p99 {_percentile(round_trips_ms, 99):.2f}, "
        f"max {round_trips_ms[-1]:.2f}",
        f"  budget per tick: {tick_interval_s * MILLISECONDS_PER_SECOND:.0f}"
        " ms",
        f"  ticks slipped:   {dropped_ticks}",
        f"  late replies:    {meter.late_replies}",
        f"  harness CPU:     {meter.cpu_s / meter.wall_s * PERCENT:.0f}% "
        "of one core",
    ]
    print("\n".join(lines), flush=True)
    # Kept up: within one percent of the ticks due, and none lost.
    return (
        meter.ticks >= 0.99 * due_ticks
        and dropped_ticks == 0
        and meter.late_replies == 0
    )


def _percentile(sorted_values: list[float], percent: float) -> float:
    # Nearest-rank percentile of values already sorted.
    rank = max(1, round(percent / PERCENT * len(sorted_values)))
    return sorted_values[min(rank, len(sorted_values)) - 1]


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    # How long, how fast, and how big the replies are.
    parser = argparse.ArgumentParser(
        prog="python -m common.harness.measure",
        description="Measure the harness's real-time budget.",
    )
    parser.add_argument(
        "--window",
        action="store_true",
        help="include the operator window in the measured process",
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=10.0,
        help="real seconds to measure (default: 10)",
    )
    parser.add_argument(
        "--speed",
        type=int,
        choices=ALLOWED_SPEEDS,
        default=10,
        help="clock speed (default: 10)",
    )
    parser.add_argument(
        "--payload-bytes",
        type=int,
        default=0,
        help="filler added to every stub's reply (default: 0)",
    )
    parser.add_argument(
        "--system",
        action="store_true",
        help="run the modules wired so far as themselves",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
