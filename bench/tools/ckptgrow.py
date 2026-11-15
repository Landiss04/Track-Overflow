import os, sys, uuid, tempfile, time, pathlib, re
sys.path.insert(0, os.getcwd())
from common.hw_link import agent as a, protocol as p, bringup as b
frames = b.recording(pathlib.Path(sys.argv[1])); limit = int(sys.argv[2])
d = pathlib.Path(tempfile.mkdtemp()); j = d / "session.json"
srv = a.PiLinkServer("track-controller-hw", j, durable=False)
hello = p.message(p.HELLO, protocol=p.VERSION, module="track-controller-hw", session=uuid.uuid4().hex, agent_version="1", agent_hash=a.AGENT_HASH)
def feed(m): return list(srv._replies(p.frame(p.encode(m)) + b"\n"))
feed(hello)
seen = {}
for i, f in enumerate(frames[:limit]):
    feed(f)
    for q in d.glob("session.json.ckpt*"):
        m = re.search(r"ckpt(\d+)$", q.name)
        if not m:
            continue
        n = int(m.group(1))
        if n not in seen:
            seen[n] = q.stat().st_size
for n in sorted(seen):
    if n in (1, 2, 5, 10, 20, 30, 50, 75, 100): print("ckpt", n, "at step ~", n * 600, "bytes", seen[n])
print("checkpoints seen:", len(seen), "files left:", sorted(x.name for x in d.glob("session.json*")))
