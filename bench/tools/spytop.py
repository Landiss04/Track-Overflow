"""Compare py-spy raw (collapsed stack) profiles, one per replay.

    python3 spytop.py /tmp/spy-r1.txt /tmp/spy-r2.txt /tmp/spy-r3.txt --steps 3990

Each file is the output of `py-spy record -f raw`. Per function (file and line
numbers dropped) it shows self time and inclusive time as ms per step reply,
for every file, and the change from the first file to the last. --rate is the
sampling rate used (default 100/s); --steps is how many step replies each
replay answered. Samples lost to sampling errors are not counted, so the ms
figures can be a few percent low; the share columns are not affected.
"""
import argparse
import collections
import re
import sys


def load(path):
    self_, incl = collections.Counter(), collections.Counter()
    total = 0
    with open(path) as stream:
        for line in stream:
            line = line.rstrip("\n")
            if not line:
                continue
            stack, _, count = line.rpartition(" ")
            count = int(count)
            frames = [re.sub(r" \(.*\)$", "", f) + " " + re.sub(r"^.*\(([^:]*):.*$", r"\1", f)
                      if re.search(r" \(.*\)$", f) else f for f in stack.split(";")]
            frames = [x for x in frames if x.strip()]
            if not frames:
                continue
            total += count
            self_[frames[-1]] += count
            for name in set(frames):
                incl[name] += count
    return total, self_, incl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--rate", type=float, default=100.0)
    ap.add_argument("--steps", type=float, required=True)
    ap.add_argument("--top", type=int, default=14)
    opts = ap.parse_args()
    ms = 1000.0 / opts.rate / opts.steps  # ms per step per sample
    data = [load(p) for p in opts.files]
    names = [f"r{i + 1}" for i in range(len(data))]
    print("Total sampled time, ms per step reply: " + "  ".join(
        f"{n} {total * ms:.2f}" for n, (total, _, _) in zip(names, data)))
    for label, index in (("SELF time (the function's own lines)", 1), ("INCLUSIVE time (the function and what it calls)", 2)):
        keys = set()
        for d in data:
            keys.update(d[index])
        def key_value(k, d):
            return d[index][k] * ms
        ranked = sorted(keys, key=lambda k: -max(key_value(k, d) for d in data))[: opts.top]
        print(f"\n{label}, ms per step")
        print(f"  {'function':<58}" + "".join(f"{n:>8}" for n in names) + f"{'last-first':>12}")
        for k in ranked:
            vals = [key_value(k, d) for d in data]
            print(f"  {k[:58]:<58}" + "".join(f"{v:>8.3f}" for v in vals) + f"{vals[-1] - vals[0]:>+12.3f}")
        # Biggest movers, whatever their size.
        movers = sorted(keys, key=lambda k: -(key_value(k, data[-1]) - key_value(k, data[0])))[:5]
        print("  largest increases first to last: " + "; ".join(
            f"{k[:40]} {key_value(k, data[-1]) - key_value(k, data[0]):+.3f}" for k in movers))


if __name__ == "__main__":
    main()
