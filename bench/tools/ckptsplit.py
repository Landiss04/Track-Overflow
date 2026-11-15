import os, sys, uuid, tempfile, time, pathlib, pickle
sys.path.insert(0, os.getcwd())
from common.hw_link import agent as a, protocol as p, bringup as b
frames = b.recording(pathlib.Path(sys.argv[1]))
srv = a.PiLinkServer("track-controller-hw", pathlib.Path(tempfile.mkdtemp()) / "j.json", durable=False)
hello = p.message(p.HELLO, protocol=p.VERSION, module="track-controller-hw", session=uuid.uuid4().hex, agent_version="1", agent_hash=a.AGENT_HASH)
def feed(m): return list(srv._replies(p.frame(p.encode(m)) + b"\n"))
feed(hello)
for i, f in enumerate(frames[:1500]):
    feed(f)
    if i + 1 in (600, 1500):
        core = len(pickle.dumps(srv.core, protocol=pickle.HIGHEST_PROTOCOL))
        cache = len(pickle.dumps(srv.cache, protocol=pickle.HIGHEST_PROTOCOL))
        both = len(pickle.dumps((srv.core, srv.cache), protocol=pickle.HIGHEST_PROTOCOL))
        t = time.perf_counter()
        for _ in range(20): pickle.dumps((srv.core, srv.cache), protocol=pickle.HIGHEST_PROTOCOL)
        ms = (time.perf_counter() - t) / 20 * 1000
        print(f"step {i+1}: core {core}  cache {cache}  both {both}  entries {len(srv.cache)}  pickle {ms:.2f} ms")
