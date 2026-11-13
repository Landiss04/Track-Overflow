"""Run QML checks in a fresh GUI process, separate from QCore tests.

Also checks, from its arguments alone, who presses Run in each kind of
run (R83).
"""

from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from common.harness import app
from common.harness.modules import CTC_OFFICE

STUB_RUN_SECONDS = 1
SYSTEM_RUN_SECONDS = 8


class HarnessWindowTest(unittest.TestCase):
    """Exercise the real window without QCore singleton clashes."""

    def test_offscreen_window_faults_and_confirmation(self) -> None:
        """Check rendering, faults and keyboard confirmation."""
        result = subprocess.run(
            [sys.executable, "-m", "common.harness.tests.window_probe"],
            cwd=Path(__file__).resolve().parents[3],
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
            capture_output=True,
            text=True,
            timeout=40,
            check=False,
        )
        self.assertEqual(result.returncode, 0,
                         result.stdout + result.stderr)

    def test_cli_modes_keep_options_and_exit_cleanly(self) -> None:
        """Honor log, speed and time-limit options in both modes."""
        repo = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as folder:
            for mode in ("window", "headless", "system"):
                with self.subTest(mode=mode):
                    log_dir = Path(folder) / mode
                    # The time limit counts from launch. Seven real
                    # modules take about two seconds to be ready, so
                    # the system run gets several more for its first
                    # ticks; stubs are ready at once.
                    run_seconds = (SYSTEM_RUN_SECONDS if mode == "system"
                                   else STUB_RUN_SECONDS)
                    args = [sys.executable, "track_overflow.py",
                            "--speedup", "--run-seconds", str(run_seconds),
                            "--log-dir", str(log_dir)]
                    if mode == "system":
                        # A person loads the PLC programs (R44) and the
                        # dispatcher presses Run and sends a train; here
                        # the Track Controller commits its starters and
                        # the CTC Office presses Run and dispatches G1.
                        args += ["--test-pi", "process", "--auto-run", "--load-starters",
                                 "--dispatch", "G1:Green:65"]
                    else:
                        # The stub CTC Office has no window, so it
                        # presses Run itself.
                        args.append("--stubs-only")
                    if mode == "headless":
                        args.append("--headless")
                    result = subprocess.run(
                        args, cwd=repo, capture_output=True, text=True,
                        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
                        timeout=run_seconds + 30, check=False,
                    )
                    self.assertEqual(result.returncode, 0,
                                     result.stdout + result.stderr)
                    self.assertEqual(result.stderr, "")
                    with next(log_dir.glob("*.csv")).open(
                        newline="", encoding="utf-8"
                    ) as file:
                        rows = list(csv.DictReader(file))
                    self.assertEqual(rows[-1]["event"], "HARNESS_STOPPED")
                    self.assertGreater(int(rows[-1]["tick"]), 0)
                    if mode == "system":
                        events = [row["event"] for row in rows]
                        self.assertIn("WAYSIDES_READY", events)
                        self.assertIn("TRAIN_ADDED", events)
                    exits = [row for row in rows
                             if row["event"] == "MODULE_EXITED"]
                    self.assertEqual(len(exits), 7)
                    self.assertEqual(
                        {row["detail"] for row in exits}, {"exit code 0"}
                    )
                    self.assertEqual(
                        "MODULE_STARTED" in result.stdout,
                        mode == "headless",
                    )


class AutoRunTest(unittest.TestCase):
    """Who presses Run, from the options the CTC Office is given (R83)."""

    @staticmethod
    def ctc_args(*argv: str) -> tuple[str, ...]:
        """The CTC Office's arguments for a harness command line."""
        specs, _edges = app._specs(app._parse_args(argv))
        return next(spec.args for spec in specs if spec.name == CTC_OFFICE)

    def test_a_window_run_waits_for_the_dispatcher(self) -> None:
        # Not even with the options that stand in for other people.
        for argv in ((), ("--speedup", "--load-starters",
                          "--dispatch", "G1:Green:65")):
            with self.subTest(argv=argv):
                args = self.ctc_args(*argv)
                self.assertEqual(args[:2], ("--module", CTC_OFFICE))
                self.assertNotIn("--run-on-ready", args)

    def test_auto_run_presses_run_in_a_window_run(self) -> None:
        self.assertIn("--run-on-ready", self.ctc_args("--auto-run"))

    def test_a_headless_run_presses_run(self) -> None:
        self.assertIn("--run-on-ready", self.ctc_args("--headless"))

    def test_a_stubs_only_run_presses_run(self) -> None:
        # Its stub CTC Office has no window to press Run in.
        args = self.ctc_args("--stubs-only")
        self.assertEqual(args[:2], ("--module", "stub"))
        self.assertIn("--run-on-ready", args)

    def test_the_other_options_pass_through(self) -> None:
        self.assertEqual(
            self.ctc_args("--speedup", "--dispatch", "G1:Green:65"),
            ("--module", CTC_OFFICE, "--speedup-at-tick", "0",
             "--dispatch", "G1:Green:65"),
        )


if __name__ == "__main__":
    unittest.main()
