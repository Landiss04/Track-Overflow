"""Per-module reply time at a given speed. Wraps measure.main; changes no repo file.
Run from the repo root: python bench/per_module.py <measure args>"""
import statistics, sys, time
from collections import Counter
from common.harness import core, measure

arrivals, last = {}, Counter()
orig = core.Harness._on_message
def patched(self, name, message):
    if message.get("op") != "STATE" and self._pending.get(name) == message.get("id"):
        arrivals.setdefault(name, []).append((time.perf_counter() - self._tick_started_s) * 1000)
        if len(self._pending) == 1:
            last[name] += 1
    return orig(self, name, message)
core.Harness._on_message = patched
code = measure.main(sys.argv[1:])
print("\nreply time from tick start, per module (ms)")
print(f"{'module':28} {'n':>6} {'mean':>7} {'p50':>7} {'p95':>7} {'p99':>7} {'max':>8} {'last to reply':>14}")
total = sum(last.values()) or 1
for name, v in sorted(arrivals.items(), key=lambda kv: -statistics.mean(kv[1])):
    s = sorted(v)
    q = lambda p: s[min(len(s) - 1, int(p * len(s)))]
    print(f"{name:28} {len(s):6} {statistics.mean(s):7.2f} {q(.5):7.2f} {q(.95):7.2f} {q(.99):7.2f} {s[-1]:8.2f} {100*last[name]/total:13.0f}%")
sys.exit(code)
