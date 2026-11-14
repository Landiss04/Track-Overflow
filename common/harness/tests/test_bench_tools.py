"""The per-tick CSV from bench/per_module.py and the two-run estimate."""

from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ENV = dict(os.environ, QT_QPA_PLATFORM="offscreen")


def _write(path, columns, rows):
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["t_s", *columns])
        for index, row in enumerate(rows):
            writer.writerow([f"{index * 0.01:.4f}", *row])


def _estimate(train_run, track_run):
    return subprocess.run(
        [sys.executable, str(ROOT / "bench/estimate_both.py"),
         "--train-physical", str(train_run), "--track-physical", str(track_run)],
        capture_output=True, text=True, timeout=30, check=True,
    ).stdout


def test_estimate_takes_the_slower_pi_of_the_two_runs(tmp_path):
    columns = ["ctc-office", "track-controller-hw", "train-controller-hw"]
    # Train physical (8 ms), Track simulated (2 ms); then Track physical (9 ms), Train simulated (1 ms).
    _write(tmp_path / "train.csv", columns, [[3, 2, 8]] * 5)
    _write(tmp_path / "track.csv", columns, [[3, 9, 1]] * 5)
    lines = _estimate(tmp_path / "train.csv", tmp_path / "track.csv").splitlines()
    rows = {line.split("  ")[0]: line for line in lines if line.startswith(("run,", "estimate"))}
    own_train = next(v for k, v in rows.items() if k.startswith("run, Train"))
    own_track = next(v for k, v in rows.items() if k.startswith("run, Track"))
    est_a = next(v for k, v in rows.items() if k.startswith("estimate A"))
    est_b = next(v for k, v in rows.items() if k.startswith("estimate B"))
    assert "8.00" in own_train and "train-controller-hw 100%" in own_train
    assert "9.00" in own_track and "track-controller-hw 100%" in own_track
    # Both estimates: the Track Pi's 9 ms is the slowest module of every tick.
    for line in (est_a, est_b):
        assert "9.00" in line and "track-controller-hw 100%" in line
        assert " 0.0%" in line  # none over the 10 ms budget


def test_estimate_counts_ticks_without_a_reply_and_the_budget(tmp_path):
    columns = ["track-controller-hw", "train-controller-hw"]
    _write(tmp_path / "train.csv", columns, [[2, 12], [2, 12], ["", 12]])
    _write(tmp_path / "track.csv", columns, [[4, 1], [4, 1], [4, 1]])
    output = _estimate(tmp_path / "train.csv", tmp_path / "track.csv")
    assert "1 ticks without a reply skipped" in output
    assert "100.0%" in output  # the 12 ms Train replies are all over a 10 ms tick


def test_per_module_writes_one_aligned_row_per_tick(tmp_path):
    target = tmp_path / "ticks.csv"
    result = subprocess.run(
        [sys.executable, str(ROOT / "bench/per_module.py"), "--system",
         "--track-controller-pi", "process", "--train-controller-pi", "process",
         "--seconds", "3", "--per-tick-csv", str(target)],
        capture_output=True, text=True, timeout=120, env=ENV, cwd=tmp_path,
    )
    assert f"per-tick replies written to {target}" in result.stdout, result.stderr[-400:]
    with target.open(newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
    assert {"t_s", "track-controller-hw", "train-controller-hw", "ctc-office"} <= set(reader.fieldnames)
    assert len(rows) > 200
    times = [float(row["t_s"]) for row in rows]
    assert times == sorted(times) and times[0] == 0.0
    answered = [row for row in rows if all(row[m] != "" for m in reader.fieldnames if m != "t_s")]
    assert len(answered) > 0.9 * len(rows)
