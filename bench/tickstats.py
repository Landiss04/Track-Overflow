"""Summarise one bench/per_module.py --per-tick-csv file.

    python bench\\tickstats.py ..\\trains_pi\\tick-track-physical-600s.csv [--budget 10] [--spike 50]

Shows how the run changes over time, which modules were the slowest of a tick,
and whether the big spikes hit one module or several at once (a stall of the
whole host looks like several; a Pi or link hiccup looks like one).
"""
import argparse
import csv
import math
import statistics
from collections import Counter

TRACK = "track-controller-hw"


def pct(values, q):
    values = sorted(values)
    return values[max(0, math.ceil(q / 100 * len(values)) - 1)] if values else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--budget", type=float, default=10.0)
    ap.add_argument("--spike", type=float, default=50.0)
    ap.add_argument("--slices", type=int, default=10)
    opts = ap.parse_args()

    with open(opts.csv, newline="") as stream:
        reader = csv.DictReader(stream)
        modules = [m for m in reader.fieldnames if m != "t_s"]
        rows = []
        for r in reader:
            rows.append((float(r["t_s"]), {m: (float(r[m]) if r[m] != "" else None) for m in modules}))
    n = len(rows)
    complete = [(t, v) for t, v in rows if all(x is not None for x in v.values())]
    print(f"{n} ticks over {rows[-1][0]:.0f} s ({n - len(complete)} without a reply from every module); budget {opts.budget:g} ms")

    tick = [(t, max(v.values()), max(v, key=v.get), v) for t, v in complete]
    track = [v[TRACK] for _, v in complete if TRACK in v]
    ticks_ms = [m for _, m, _, _ in tick]
    print(f"slowest module per tick: mean {statistics.mean(ticks_ms):.2f}  p50 {pct(ticks_ms, 50):.2f}  p95 {pct(ticks_ms, 95):.2f}  "
          f"p99 {pct(ticks_ms, 99):.2f}  max {max(ticks_ms):.1f}; over budget {100 * sum(m > opts.budget for m in ticks_ms) / len(ticks_ms):.1f}%")

    print(f"\nOver the run, in {opts.slices} equal parts ({TRACK} reply, ms):")
    print(f"  {'from s':>8}{'mean':>8}{'p50':>8}{'p95':>8}{'p99':>8}{'>budget':>9}  tick mean")
    size = max(1, len(complete) // opts.slices)
    for k in range(opts.slices):
        part = complete[k * size:(k + 1) * size if k < opts.slices - 1 else len(complete)]
        tr = [v[TRACK] for _, v in part]
        tm = [max(v.values()) for _, v in part]
        print(f"  {part[0][0]:>8.0f}{statistics.mean(tr):>8.2f}{pct(tr, 50):>8.2f}{pct(tr, 95):>8.2f}{pct(tr, 99):>8.2f}"
              f"{100 * sum(x > opts.budget for x in tr) / len(tr):>8.1f}%  {statistics.mean(tm):.2f}")

    print("\nSlowest module of each tick:")
    last = Counter(name for _, _, name, _ in tick)
    for name, count in last.most_common(5):
        print(f"  {name:<24}{100 * count / len(tick):>6.1f}%")
    not_track = [(t, m, name, v) for t, m, name, v in tick if name != TRACK and m > opts.budget]
    print(f"  ticks over budget where {TRACK} was NOT the slowest: {len(not_track)} "
          f"({100 * len(not_track) / len(tick):.1f}% of ticks)")

    print(f"\nSpikes (any module over {opts.spike:g} ms):")
    spikes = [(t, v) for t, v in complete if max(v.values()) > opts.spike]
    if not spikes:
        print("  none")
    for t, v in spikes[:15]:
        slow = ", ".join(f"{m} {x:.0f}" for m, x in sorted(v.items(), key=lambda kv: -kv[1]) if x > opts.budget)
        print(f"  t={t:7.1f} s  {slow}")
    if len(spikes) > 15:
        print(f"  ... and {len(spikes) - 15} more")


if __name__ == "__main__":
    main()
