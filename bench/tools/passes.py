import os, sys, uuid, tempfile, time, pathlib, statistics, gc
sys.path.insert(0, os.getcwd())
from common.hw_link import agent as a, protocol as p, bringup as b
frames = b.recording(pathlib.Path(sys.argv[1]))[: int(sys.argv[2])]
passes = int(sys.argv[3])
srv = a.PiLinkServer("track-controller-hw", pathlib.Path(tempfile.mkdtemp()) / "j.json", durable=False)
def feed(m): return list(srv._replies(p.frame(p.encode(m)) + b"\n"))
for n in range(1, passes + 1):
    hello = p.message(p.HELLO, protocol=p.VERSION, module="track-controller-hw", session=uuid.uuid4().hex, agent_version="1", agent_hash=a.AGENT_HASH)
    feed(hello)
    core, wall = [], []
    for f in frames:
        t = time.perf_counter()
        for r, line in feed(f):
            if r["op"] == "OUTPUTS": core.append(r["metrics"]["core_step_s"] * 1000)
        wall.append((time.perf_counter() - t) * 1000)
    third = len(core) // 3
    print(f"pass {n}: steps {len(core)}  core mean {statistics.mean(core):.3f} ms  p99 {sorted(core)[int(.99*len(core))]:.3f}  first third {statistics.mean(core[:third]):.3f}  last third {statistics.mean(core[-third:]):.3f}  waysides in view {len(feed(frames[-1])[0][0].get('view',{}) or {}) if False else ''}", flush=True)
