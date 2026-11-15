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
def step(c, i):
    s = cap[i % len(cap)]
    return c.step({"dt": s["dt"], "sim_time_s": 18000 + (i + 1) * 0.1, "inputs": s["inputs"]})
for i in range(600): step(core, i)
a = time.perf_counter(); blob = pickle.dumps(core, protocol=pickle.HIGHEST_PROTOCOL); t_dump = (time.perf_counter() - a) * 1000
a = time.perf_counter(); restored = pickle.loads(blob); t_load = (time.perf_counter() - a) * 1000
print("checkpoint %d bytes, dump %.2f ms, restore %.1f ms" % (len(blob), t_dump, t_load))
for wid, w in core.controller._waysides.items():
    r = restored.controller._waysides[wid]
    print(wid, "vital equal", w._vital == r._vital, "program equal", w._program == r._program)
print("view equal at restore:", pack_eq := (core.view() == restored.view()))
same = True; first = None
for i in range(600, 1800):
    x = step(core, i); a = time.perf_counter(); y = step(restored, i); d = (time.perf_counter() - a) * 1000
    if first is None: first = d
    if x != y: same = False; print("DIFF at", i); break
print("1200 steps after restore identical:", same, "| first step after restore %.2f ms" % first)
print("view equal at end:", core.view() == restored.view())
va, vb = core.view(), restored.view()
def walk(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a.keys() | b.keys(): walk(a.get(k), b.get(k), path + "/" + str(k))
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)): walk(x, y, path + "[%d]" % i)
    elif a != b: print("  differs:", path, repr(a)[:60], repr(b)[:60])
walk(va, vb)
