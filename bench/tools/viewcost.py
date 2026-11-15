import os, sys, uuid, tempfile, time, pathlib, statistics
sys.path.insert(0, os.getcwd())
from common.hw_link import agent as a, protocol as p, bringup as b
frames = b.recording(pathlib.Path(sys.argv[1]))
srv = a.PiLinkServer("track-controller-hw", pathlib.Path(tempfile.mkdtemp()) / "j.json", durable=False)
hello = p.message(p.HELLO, protocol=p.VERSION, module="track-controller-hw", session=uuid.uuid4().hex, agent_version="1", agent_hash=a.AGENT_HASH)
def feed(m): return list(srv._replies(p.frame(p.encode(m)) + b"\n"))
feed(hello)
for f in frames[:1100]: feed(f)
v, e, fr = [], [], []
for _ in range(60):
    t = time.perf_counter(); view = srv.core.view(); v.append((time.perf_counter() - t) * 1000)
    t = time.perf_counter(); line = p.encode(p.message(p.VIEW, tick=1, view=view)); e.append((time.perf_counter() - t) * 1000)
    t = time.perf_counter(); p.frame(line); fr.append((time.perf_counter() - t) * 1000)
m = lambda x: round(statistics.median(x), 2)
print(f"core.view() {m(v)} ms   encode {m(e)} ms   frame/CRC {m(fr)} ms   total {m(v)+m(e)+m(fr):.2f} ms   line {len(line)} bytes")
