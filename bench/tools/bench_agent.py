"""Sandbox benchmark: real agent over a pty, STEPs paced at 10 ms.

usage: bench_agent.py <repo> <track|train> <seconds> [label]
Not a Pi: numbers are x86-sandbox only. Prints one JSON line.
"""
import json, os, pty, subprocess, sys, tempfile, time, statistics, termios, tty
from pathlib import Path

repo, board, seconds = Path(sys.argv[1]), sys.argv[2], float(sys.argv[3])
label = sys.argv[4] if len(sys.argv) > 4 else ""
sys.path.insert(0, str(repo))
from common.hw_link import protocol as p
capture = json.load(open(Path(__file__).with_name("capture.json")))
module = {"track": "track-controller-hw", "train": "train-controller-hw"}[board]
steps = capture[board]
master, slave = pty.openpty()
tty.setraw(master)
tmp = Path(tempfile.mkdtemp(prefix="bench-"))
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
agent = subprocess.Popen(
    [sys.executable, "-m", "common.hw_link.agent", "--module", module,
     "--device", os.ttyname(slave), "--journal", str(tmp / "j.jsonl")]
    + (["--log", os.environ["AGENT_LOG"]] if "AGENT_LOG" in os.environ else []),
    cwd=repo, env=env)
buf = b""
def read_lines(timeout):
    global buf
    import select
    end = time.perf_counter() + timeout
    while b"\n" not in buf:
        left = end - time.perf_counter()
        if left <= 0 or not select.select([master], [], [], left)[0]:
            return None
        buf += os.read(master, 65536)
    line, buf = buf.split(b"\n", 1)
    return line
def send(msg):
    os.write(master, b"\n" + p.frame(p.encode(msg)))
def wait_for(op, rid, timeout=30):
    end = time.perf_counter() + timeout
    while time.perf_counter() < end:
        line = read_lines(end - time.perf_counter())
        if line is None: break
        if not line.strip(): continue
        m = json.loads(p.unframe(line))
        if m["op"] in (op, "REJECTED") and m["id"] == rid:
            return m
    raise TimeoutError(op)
rid = 0
def nid():
    global rid; rid += 1; return rid
time.sleep(1.5)  # agent import
send(p.message(p.HELLO, nid(), protocol=p.VERSION, module=module,
               session="bench", agent_version="host-1", agent_hash="host"))
wait_for(p.HELLO, rid)
if board == "track":
    data = repo / "TrackCtrlHw" / "data"
    sys.path.insert(0, str(repo / "TrackCtrlHw"))
    from track_ctrl_hw.territory import load_territory_file
    from track_ctrl_hw.wire import territory_to_wire
    for path in sorted((data / "waysides").glob("red*.json")):
        t = load_territory_file(path)
        send(p.message(p.ACTION, nid(), action="load_territory",
                       args={"territory": territory_to_wire(t)}))
        r = wait_for(p.ACK, rid)
        prog = data / "plc" / (path.stem + ".plc")
        send(p.message(p.ACTION, nid(), action="load_program", args={
            "wayside_id": t.wayside_id, "source": prog.read_text(),
            "file_name": prog.name}))
        r = wait_for(p.ACK, rid); assert r["op"] == "ACK", r
else:
    send(p.message(p.ACTION, nid(), action="test_engineer_gains",
                   args={"kp": 3000.0, "ki": 300.0}))
    wait_for(p.ACK, rid)

DT = 0.01
rtts, core, slipped, late, ck = [], [], 0, 0, []
tick = 0
t0 = time.perf_counter()
n = int(seconds / DT)
for i in range(n):
    due = t0 + i * DT
    now = time.perf_counter()
    if now < due:
        time.sleep(max(0, due - now - 0.0005))
        while time.perf_counter() < due: pass
    else:
        late += 1
    s = steps[i % len(steps)]
    tick += 1
    req = {"op": "STEP", "id": nid(), "tick": tick,
           "dt": s["dt"], "sim_time_s": 1000.0 + tick * s["dt"],
           "inputs": s["inputs"]}
    t1 = time.perf_counter()
    send(req)
    m = wait_for("OUTPUTS", rid)
    t2 = time.perf_counter()
    assert m["op"] == "OUTPUTS", m
    rtts.append((t2 - t1) * 1000); core.append(m["metrics"]["core_step_s"] * 1000)
    if t2 - t1 > DT: slipped += 1
    if tick % 600 == 0: ck.append(round((t2 - t1) * 1000, 2))
agent.terminate(); agent.wait()
def stat(x):
    x = sorted(x); q = lambda f: x[min(len(x)-1, int(len(x)*f))]
    return dict(mean=round(statistics.fmean(x),3), p95=round(q(.95),3),
                p99=round(q(.99),3), max=round(x[-1],3))
print(json.dumps(dict(label=label, board=board, steps=n, rtt_ms=stat(rtts),
      core_ms=stat(core), slipped=slipped, late_sends=late, ckpt_rtt_ms=ck)))
