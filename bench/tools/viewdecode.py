import os, sys, uuid, tempfile, time, pathlib, statistics
sys.path.insert(0, os.getcwd())
from common.hw_link import agent as a, protocol as p, bringup as b
frames = b.recording(pathlib.Path(sys.argv[1]))
srv = a.PiLinkServer("track-controller-hw", pathlib.Path(tempfile.mkdtemp()) / "j.json", durable=False)
hello = p.message(p.HELLO, protocol=p.VERSION, module="track-controller-hw", session=uuid.uuid4().hex, agent_version="1", agent_hash=a.AGENT_HASH)
def feed(m): return list(srv._replies(p.frame(p.encode(m)) + b"\n"))
feed(hello)
views, steps = [], []
for f in frames[:1200]:
    for r, line in feed(f):
        (views if r["op"] == "VIEW" else steps).append(line.rstrip(b"\n"))
def t(lines):
    out = []
    for line in lines:
        s = time.perf_counter(); p.decode(p.unframe(line)); out.append((time.perf_counter() - s) * 1000)
    return statistics.median(out), max(out)
print("VIEW decode+check ms (median, max):", [round(x, 2) for x in t(views)], len(views), "lines")
print("STEP decode+check ms (median, max):", [round(x, 2) for x in t(steps[2:60])])
