import json, sys, tempfile, time, statistics
from pathlib import Path
root = Path(sys.argv[1]); sys.path.insert(0, str(root))
from common.hw_link import protocol as p
from common.hw_link.agent import PiLinkServer
cap = json.load(open(Path(sys.argv[2])))["train"]
srv = PiLinkServer("train-controller-hw", Path(tempfile.mkdtemp()) / "j", durable=False)
srv.handle(p.message(p.HELLO,0,0,protocol=p.VERSION,module="train-controller-hw",session="s",agent_version="x",agent_hash="x"))
srv.handle(p.message(p.ACTION,1,0,action="test_engineer_gains",args={"kp":400000.0,"ki":8000.0}))
lines = [p.frame(p.encode({"op":"STEP","id":i+2,"tick":i+1,"dt":cap[i%len(cap)]["dt"],"sim_time_s":18000+(i+1)*0.1,"inputs":cap[i%len(cap)]["inputs"]})) for i in range(20000)]
xs = []
for ln in lines:
    a = time.perf_counter()
    for _ in srv._replies(ln): pass
    xs.append((time.perf_counter() - a) * 1e6)
srv.close(); xs.sort()
print("%s us mean %.1f p50 %.1f p99 %.1f" % (sys.argv[3], statistics.fmean(xs), xs[len(xs)//2], xs[int(len(xs)*.99)]))
