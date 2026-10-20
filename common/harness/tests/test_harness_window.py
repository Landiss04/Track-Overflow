"""Run QML checks in a fresh GUI process, separate from QCore tests."""

from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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
                    args = [sys.executable, "track_overflow.py",
                            "--speedup", "--run-seconds",
                            "2" if mode == "system" else "1",
                            "--log-dir", str(log_dir)]
                    if mode == "system":
                        # A person loads the PLC programs (R44) and the
                        # dispatcher sends a train; here the Track
                        # Controller commits its starters and the CTC
                        # Office dispatches G1.
                        args += ["--load-starters",
                                 "--dispatch", "G1:Green:65"]
                    else:
                        args.append("--stubs-only")
                    if mode == "headless":
                        args.append("--headless")
                    result = subprocess.run(
                        args, cwd=repo, capture_output=True, text=True,
                        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
                        timeout=20, check=False,
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


if __name__ == "__main__":
    unittest.main()
