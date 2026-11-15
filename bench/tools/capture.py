"""Record the STEP inputs a real Red run sends to both Pi cores."""
import json, sys, time
from pathlib import Path
root = Path(sys.argv[1]); out = Path(sys.argv[2]); limit = float(sys.argv[3])
sys.path.insert(0, str(root))
from common.harness.tests.test_harness_red_loop import RedLoop
from track_ctrl_hw.wire import inputs_to_wire
loop = RedLoop()
rec = {"track": [], "train": []}
orig_hw, orig_tr = loop.hw.step, loop.red_controller.step
def hw(dt, inputs):
    rec["track"].append({"dt": dt, "inputs": inputs_to_wire(inputs)})
    return orig_hw(dt, inputs)
def tr(tick, dt, now, inputs):
    rec["train"].append({"tick": tick, "dt": dt, "sim_time_s": now, "inputs": inputs})
    return orig_tr(tick, dt, now, inputs)
loop.hw.step, loop.red_controller.step = hw, tr
ok = loop.run_until(loop.red_stopped, limit_s=limit)
print("reached stop:", ok, "ticks", loop.tick, len(rec["track"]), len(rec["train"]))
json.dump(rec, out.open("w"))
