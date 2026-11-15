import json, pickle, sys, time, statistics
from pathlib import Path
repo = Path(sys.argv[1]); sys.path[:0] = [str(repo), str(repo / "TrackCtrlHw")]
from common.hw_link.cores import TrackCore
from track_ctrl_hw.territory import load_territory_file
from track_ctrl_hw.wire import territory_to_wire
cap = json.load(open(Path(sys.argv[2])))["track"]
core = TrackCore(); data = repo / "TrackCtrlHw" / "data"
for path in sorted((data / "waysides").glob("red*.json")):
    t = load_territory_file(path)
    core.action("load_territory", {"territory": territory_to_wire(t)})
    prog = data / "plc" / (path.stem + ".plc")
    core.action("load_program", {"wayside_id": t.wayside_id, "source": prog.read_text(), "file_name": prog.name})
for i in range(1200):
    s = cap[i % len(cap)]
    core.step({"dt": s["dt"], "sim_time_s": 18000 + (i + 1) * 0.1, "inputs": s["inputs"]})
size = lambda o: len(pickle.dumps(o, protocol=pickle.HIGHEST_PROTOCOL))
def ms(o):
    xs = []
    for _ in range(30):
        a = time.perf_counter(); pickle.dumps(o, protocol=pickle.HIGHEST_PROTOCOL); xs.append((time.perf_counter() - a) * 1000)
    return statistics.median(xs)
print("whole core: %d bytes, %.2f ms median" % (size(core), ms(core)))
ctrl = core.controller
print("controller attrs:", {k: type(v).__name__ for k, v in vars(ctrl).items()})
tot = {}
for wid, w in ctrl._waysides.items():
    print("wayside", wid)
    for k, v in vars(w).items():
        n = size(v); tot[k] = tot.get(k, 0) + n
        print("   %-22s %-14s %8d bytes" % (k, type(v).__name__, n))
print("per-attribute totals over waysides:", dict(sorted(tot.items(), key=lambda kv: -kv[1])))
print("---- static/dynamic ----")
saved = {wid: (w._vital, w._program) for wid, w in ctrl._waysides.items()}
for w in ctrl._waysides.values(): w._vital = w._program = None
print("without compiled programs: %d bytes, %.2f ms median" % (size(core), ms(core)))
for wid, w in ctrl._waysides.items(): w._vital, w._program = saved[wid]
progs = [v for pair in saved.values() for v in pair]
print("compiled programs alone:   %d bytes, %.2f ms median" % (size(progs), ms(progs)))
print("program sources alone:     %d bytes" % size([p.source for p in progs]))
