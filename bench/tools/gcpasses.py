import os, sys, uuid, tempfile, time, pathlib, gc, statistics, collections
sys.path.insert(0, os.getcwd())
from common.hw_link import agent as a, protocol as p, bringup as b
frames = b.recording(pathlib.Path(sys.argv[1]))[: int(sys.argv[2])]
srv = a.PiLinkServer("track-controller-hw", pathlib.Path(tempfile.mkdtemp()) / "j.json", durable=False)
def feed(m): return list(srv._replies(p.frame(p.encode(m)) + b"\n"))
stat = {"t": 0.0, "n": collections.Counter(), "ms": collections.Counter(), "worst": 0.0}
def cb(phase, info):
    if phase == "start": stat["t"] = time.perf_counter()
    else:
        d = (time.perf_counter() - stat["t"]) * 1000
        g = info["generation"]; stat["n"][g] += 1; stat["ms"][g] += d; stat["worst"] = max(stat["worst"], d)
gc.callbacks.append(cb)
print("gc thresholds", gc.get_threshold(), sys.version.split()[0])
for n in range(1, 5):
    stat.update(n=collections.Counter(), ms=collections.Counter(), worst=0.0)
    feed(p.message(p.HELLO, protocol=p.VERSION, module="track-controller-hw", session=uuid.uuid4().hex, agent_version="1", agent_hash=a.AGENT_HASH))
    core = []
    for f in frames:
        for r, line in feed(f):
            if r["op"] == "OUTPUTS": core.append(r["metrics"]["core_step_s"] * 1000)
    total = sum(stat["ms"].values())
    print(f"pass {n}: core mean {statistics.mean(core):.3f} ms | gc runs gen0 {stat['n'][0]} gen1 {stat['n'][1]} gen2 {stat['n'][2]} | gc time total {total:.0f} ms (gen2 {stat['ms'][2]:.0f}) worst pause {stat['worst']:.1f} ms | per step {total/len(core):.3f} ms", flush=True)
