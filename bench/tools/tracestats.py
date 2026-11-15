"""Summarise a bringup --trace-csv file: what the round trips over 10 ms have in common.

    python tracestats.py ..\\trains_pi\\track-trace-180s.csv
"""
import csv
import math
import sys

LIMIT = 10.0


def pct(values, q):
    values = sorted(values)
    return values[max(0, math.ceil(q * len(values)) - 1)] if values else float("nan")


def group_line(name, rows):
    if not rows:
        return f"  {name:<44}{0:>8}"
    rtts = [r["rtt"] for r in rows]
    over = sum(1 for v in rtts if v > LIMIT)
    return (
        f"  {name:<44}{len(rows):>8}{over:>8}{100 * over / len(rows):>8.2f}%"
        f"{sum(rtts) / len(rtts):>9.2f}{pct(rtts, 0.99):>9.2f}{max(rtts):>9.2f}"
    )


def main(path):
    rows = []
    with open(path, newline="") as stream:
        for r in csv.DictReader(stream):
            rows.append(
                dict(
                    sample=int(r["sample"]),
                    op=r["op"],
                    rtt=float(r["rtt_ms"]),
                    core=float(r["core_ms"]) if r["core_ms"] else None,
                    late=float(r["send_late_ms"]),
                    before=int(r["views_before_send"]),
                    after=int(r["views_after_send"]),
                    resent=int(r["resent"]),
                )
            )
    steps = [r for r in rows if r["op"] == "OUTPUTS"]
    over = [r for r in steps if r["rtt"] > LIMIT]
    print(f"{len(rows)} rows, {len(steps)} step replies, {len(over)} step round trips over {LIMIT:.0f} ms")
    print(f"  {'':<44}{'rows':>8}{'>10ms':>8}{'share':>9}{'mean':>9}{'p99':>9}{'max':>9}")
    print("By VIEW position (step replies):")
    print(group_line("a VIEW arrived after the request was sent", [r for r in steps if r["after"] > 0]))
    print(group_line("a VIEW arrived only before it was sent", [r for r in steps if r["after"] == 0 and r["before"] > 0]))
    print(group_line("no VIEW near it", [r for r in steps if r["after"] == 0 and r["before"] == 0]))
    print("By how late the host sent it:")
    print(group_line("sent on time (< 1 ms late)", [r for r in steps if r["late"] < 1.0]))
    print(group_line("sent late (>= 1 ms)", [r for r in steps if r["late"] >= 1.0]))
    print("By Pi core step:")
    cored = [r for r in steps if r["core"] is not None]
    print(group_line("core step < 6 ms", [r for r in cored if r["core"] < 6.0]))
    print(group_line("core step >= 6 ms", [r for r in cored if r["core"] >= 6.0]))
    if steps:
        print("Across the run, in tenths of the step replies (mean ms; over-10 count):")
        size = max(1, len(steps) // 10)
        cores, rtts, overs = [], [], []
        for k in range(10):
            part = steps[k * size : (k + 1) * size if k < 9 else len(steps)]
            cs = [r["core"] for r in part if r["core"] is not None]
            cores.append(f"{sum(cs) / len(cs):.2f}" if cs else "-")
            rtts.append(f"{sum(r['rtt'] for r in part) / len(part):.2f}")
            overs.append(str(sum(1 for r in part if r["rtt"] > LIMIT)))
        print("  core step : " + " ".join(f"{v:>6}" for v in cores))
        print("  round trip: " + " ".join(f"{v:>6}" for v in rtts))
        print("  over 10 ms: " + " ".join(f"{v:>6}" for v in overs))
    if over:
        print("Of the round trips over the limit:")
        print(f"  VIEW arrived after the request was sent: {sum(1 for r in over if r['after'] > 0)}")
        print(f"  host sent it late (>= 1 ms):              {sum(1 for r in over if r['late'] >= 1.0)}")
        print(f"  core step >= 6 ms:                        {sum(1 for r in over if r['core'] is not None and r['core'] >= 6.0)}")
        print(f"  one of the first 10 samples:              {sum(1 for r in over if r['sample'] <= 10)}")
        print(f"  resent:                                   {sum(1 for r in over if r['resent'])}")
        print("Worst five: " + ", ".join(f"#{r['sample']} {r['rtt']:.1f} ms" for r in sorted(over, key=lambda r: -r['rtt'])[:5]))


if __name__ == "__main__":
    main(sys.argv[1])
