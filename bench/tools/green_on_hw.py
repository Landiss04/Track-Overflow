"""Run a real Green train through the SW controller, replay its inputs on the HW core."""
import json, sys, time, statistics
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from common.harness.tests.test_harness_train_loop import _Loop, KP, KI, Dispatch, TO_GLENBURY
loop = _Loop()
rec = []
orig = loop.controller.step
def tap(tick, dt, now, inputs):
    out = orig(tick, dt, now, inputs)
    rec.append((tick, dt, now, json.loads(json.dumps(inputs)), json.loads(json.dumps(out))))
    return out
loop.controller.step = tap
for _ in range(int(sys.argv[1])):
    loop.step()
trains = {t for r in rec for t in r[3].get("trains", {})}
lines = {e.get("line") for r in rec for e in r[3].get("trains", {}).values()}
print("steps", len(rec), "trains", sorted(trains), "lines", lines)
json.dump(rec, open(sys.argv[2], "w"))
