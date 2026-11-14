"""Estimate the 10x round trip with both Pis physical from two runs with one each.

    python bench/estimate_both.py --train-physical TRAIN_RUN.csv --track-physical TRACK_RUN.csv

Each CSV comes from `bench/per_module.py --per-tick-csv`. In the run with the Train
Pi physical, the Track Controller was a local simulator, and the other way round.
A tick's round trip is the time of its slowest module, so:

  A: take each tick of the Train-physical run and replace the Track column with a
     random value from the Track-physical run's Track column;
  B: take each tick of the Track-physical run and replace the Train column with a
     random value from the Train-physical run's Train column.

Everything else in a tick (the other five modules, and what the host was doing at
that moment) stays as measured. The replaced value is drawn independently of the
tick, which ignores any shared host load between the two modules. Ticks where a
module did not reply in time have no time to use and are counted, not hidden.
This is an estimate from two runs, not a measurement of both Pis together.
"""
import argparse
import csv
import random
import statistics
from collections import Counter

TRACK = "track-controller-hw"
TRAIN = "train-controller-hw"


def load(path):
    with open(path, newline="") as stream:
        reader = csv.DictReader(stream)
        modules = [name for name in reader.fieldnames if name != "t_s"]
        rows = [
            {m: (float(r[m]) if r[m] != "" else None) for m in modules}
            for r in reader
        ]
    return modules, rows


def percentile(sorted_values, percent):
    rank = max(1, round(percent / 100 * len(sorted_values)))
    return sorted_values[min(rank, len(sorted_values)) - 1]


def summarize(label, ticks, budget):
    """ticks: list of (round trip ms, name of the slowest module)."""
    times = sorted(t for t, _ in ticks)
    last = Counter(name for _, name in ticks)
    over = sum(1 for t in times if t > budget)
    shares = ", ".join(f"{n} {100 * c / len(ticks):.0f}%" for n, c in last.most_common(3))
    return (
        f"{label:<44}{len(times):>7}{statistics.mean(times):>8.2f}{percentile(times, 50):>8.2f}"
        f"{percentile(times, 95):>8.2f}{percentile(times, 99):>8.2f}{times[-1]:>8.2f}"
        f"{100 * over / len(times):>8.1f}%   {shares}"
    )


def own_ticks(rows):
    out, missing = [], 0
    for row in rows:
        if any(v is None for v in row.values()):
            missing += 1
            continue
        name = max(row, key=row.get)
        out.append((row[name], name))
    return out, missing


def replaced(rows, column, donor, rng):
    out, missing = [], 0
    for row in rows:
        mixed = dict(row)
        mixed[column] = rng.choice(donor)
        if any(v is None for k, v in mixed.items()):
            missing += 1
            continue
        name = max(mixed, key=mixed.get)
        out.append((mixed[name], name))
    return out, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-physical", required=True)
    ap.add_argument("--track-physical", required=True)
    ap.add_argument("--budget", type=float, default=10.0, help="ms per tick (10x: 10)")
    ap.add_argument("--seed", type=int, default=1)
    opts = ap.parse_args()
    rng = random.Random(opts.seed)

    mod_t, rows_t = load(opts.train_physical)
    mod_k, rows_k = load(opts.track_physical)
    for name, modules in (("train-physical", mod_t), ("track-physical", mod_k)):
        if TRACK not in modules or TRAIN not in modules:
            raise SystemExit(f"{name}: needs both {TRACK} and {TRAIN} columns")
    track_donor = [r[TRACK] for r in rows_k if r[TRACK] is not None]
    train_donor = [r[TRAIN] for r in rows_t if r[TRAIN] is not None]

    print(f"{'ms to the slowest module of a tick':<44}{'ticks':>7}{'mean':>8}{'p50':>8}{'p95':>8}{'p99':>8}{'max':>8}"
          f"{'>' + format(opts.budget, 'g') + ' ms':>9}   slowest module")
    results = []
    for label, (ticks, missing) in (
        ("run, Train Pi physical, Track simulated", own_ticks(rows_t)),
        ("run, Track Pi physical, Train simulated", own_ticks(rows_k)),
        ("estimate A: Train run, Track column from Track run", replaced(rows_t, TRACK, track_donor, rng)),
        ("estimate B: Track run, Train column from Train run", replaced(rows_k, TRAIN, train_donor, rng)),
    ):
        print(summarize(label, ticks, opts.budget) + (f"   [{missing} ticks without a reply skipped]" if missing else ""))
        results.append(ticks)
    print("\nThe two estimates disagree by more than the run-to-run spread if the modules share load; "
          "report both, not one.")


if __name__ == "__main__":
    main()
