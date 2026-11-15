import os, sys, uuid, tempfile, pathlib, gc, pickle, collections, resource
sys.path.insert(0, os.getcwd())
from common.hw_link import agent as a, protocol as p, bringup as b
frames = b.recording(pathlib.Path(sys.argv[1]))[: int(sys.argv[2])]
srv = a.PiLinkServer("track-controller-hw", pathlib.Path(tempfile.mkdtemp()) / "j.json", durable=False)
def feed(m): return list(srv._replies(p.frame(p.encode(m)) + b"\n"))
def snap(label):
    gc.collect()
    objs = len(gc.get_objects())
    core = len(pickle.dumps(srv.core, protocol=pickle.HIGHEST_PROTOCOL))
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
    print(f"{label:<22} gc objects {objs:>8}  core pickle {core:>7}  cache entries {len(srv.cache):>2}  max RSS {rss} MB", flush=True)
snap("start")
for n in range(1, 5):
    feed(p.message(p.HELLO, protocol=p.VERSION, module="track-controller-hw", session=uuid.uuid4().hex, agent_version="1", agent_hash=a.AGENT_HASH))
    for f in frames: feed(f)
    snap(f"after pass {n}")
# What kind of objects are added between pass 3 and pass 4?
gc.collect(); before = collections.Counter(type(o).__name__ for o in gc.get_objects())
feed(p.message(p.HELLO, protocol=p.VERSION, module="track-controller-hw", session=uuid.uuid4().hex, agent_version="1", agent_hash=a.AGENT_HASH))
for f in frames: feed(f)
gc.collect(); after = collections.Counter(type(o).__name__ for o in gc.get_objects())
print("object types that grew in pass 5:", [(k, after[k] - before[k]) for k in after if after[k] - before[k] > 50][:8])
