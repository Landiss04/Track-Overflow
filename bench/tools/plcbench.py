"""PLC benchmark: several sessions of one recording in one process, no USB.

Run on the Pi from /opt/track-overflow, as the service does:

    cd /opt/track-overflow
    PYTHONOPTIMIZE=1 PYTHONDONTWRITEBYTECODE=1 python3 ~/plcbench.py ~/Downloads/track-red-4k.jsonl --sessions 4
    ... --variant collect      (gc.collect() before every new session)
    ... --variant flat         (channel A run as one generated expression per statement)
    ... --variant flat --verify --sessions 1   (checks flat gives the same answers)

Each session is a new HELLO session id, so the agent builds a new core exactly
as it does when the host starts a run. It prints, per session, the Pi core step
(as the agent measures it) and how long channel A (the closure tree) and
channel B (the postfix code) take per step. Nothing in the repository or the
service is changed; the flat variant is a patch made in this process only.
"""
import argparse
import gc
import json
import os
import statistics
import sys
import tempfile
import time
import uuid
from functools import cached_property
from pathlib import Path

sys.path.insert(0, os.getcwd())

from common.hw_link import agent as a  # noqa: E402
from common.hw_link import cores  # noqa: E402,F401  (puts track_ctrl_hw on the path)
from common.hw_link import protocol as p  # noqa: E402
from track_ctrl_hw import plc  # noqa: E402


def recording(path):
    frames = []
    with open(path) as stream:
        for line in stream:
            entry = json.loads(line)
            request = entry.get("request", entry)
            if request.get("op") in (p.ACTION, "STEP"):
                p.validate(request)
                frames.append(request)
    return frames


def expression(node):
    """The same logic as plc._walker, as the text of one Python expression."""
    if isinstance(node, plc.Constant):
        return repr(node.value)
    if isinstance(node, plc.Read):
        return f"v.get({node.name!r}, False)"
    if isinstance(node, plc.Negate):
        return f"(not {expression(node.operand)})"
    left, right = expression(node.left), expression(node.right)
    if node.operator == "AND":
        return f"({left} and {right})"
    if node.operator == "OR":
        return f"({left} or {right})"
    return f"({left} != {right})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("recording")
    ap.add_argument("--sessions", type=int, default=4)
    ap.add_argument("--variant", choices=("baseline", "collect", "flat"), default="baseline")
    ap.add_argument("--verify", action="store_true",
                    help="with --variant flat: compare every channel A answer with the closure tree's (timings then mean nothing)")
    opts = ap.parse_args()
    if opts.verify and opts.variant != "flat":
        ap.error("--verify needs --variant flat")

    frames = recording(opts.recording)
    steps = sum(1 for f in frames if f["op"] == "STEP")
    clock = {"a": 0.0, "b": 0.0, "mismatch": 0, "checked": 0}

    original_walkers = plc.Program.__dict__["_walkers"]
    orig_a, orig_b = plc.Program.scan_a, plc.Program.scan_b

    def run_a(self, inputs, walkers):
        values = {name: inputs[name] for name in self.inputs}
        for target, walk in walkers:
            values[target] = walk(values)
        return {name: values.get(name, False) for name in self.outputs}

    if opts.variant == "flat":
        def flat_walkers(self):
            built = []
            for statement in self.statements:
                try:
                    built.append((statement.target, eval("lambda v: " + expression(statement.tree))))
                except (SyntaxError, RecursionError, MemoryError):
                    built.append((statement.target, plc._walker(statement.tree)))
            return tuple(built)

        flat = cached_property(flat_walkers)
        flat.__set_name__(plc.Program, "_walkers")
        plc.Program._walkers = flat
        slow = cached_property(original_walkers.func)
        slow.__set_name__(plc.Program, "_slow_walkers")
        plc.Program._slow_walkers = slow

    def timed_a(self, inputs):
        t = time.perf_counter()
        result = orig_a(self, inputs)
        clock["a"] += time.perf_counter() - t
        if opts.verify:
            reference = run_a(self, inputs, self._slow_walkers)
            clock["checked"] += 1
            clock["mismatch"] += reference != result
        return result

    def timed_b(self, inputs):
        t = time.perf_counter()
        result = orig_b(self, inputs)
        clock["b"] += time.perf_counter() - t
        return result

    plc.Program.scan_a, plc.Program.scan_b = timed_a, timed_b

    srv = a.PiLinkServer(
        "track-controller-hw", Path(tempfile.mkdtemp()) / "j.json", durable=False
    )

    def feed(message):
        return list(srv._replies(p.frame(p.encode(message)) + b"\n"))

    print(f"python {sys.version.split()[0]}  variant {opts.variant}  frames {len(frames)} "
          f"({steps} steps)  PYTHONOPTIMIZE={os.environ.get('PYTHONOPTIMIZE', '')}")
    print(f"{'session':>8}{'core ms':>9}{'p99':>8}{'chan A':>9}{'chan B':>9}{'rest':>8}   (ms per step)")
    for n in range(1, opts.sessions + 1):
        if opts.variant == "collect":
            gc.collect()
        clock.update(a=0.0, b=0.0)
        feed(p.message(p.HELLO, protocol=p.VERSION, module="track-controller-hw",
                       session=uuid.uuid4().hex, agent_version="1",
                       agent_hash=a.AGENT_HASH))
        core = []
        for frame in frames:
            for reply, _ in srv._replies(p.frame(p.encode(frame)) + b"\n"):
                if reply["op"] == "OUTPUTS":
                    core.append(reply["metrics"]["core_step_s"] * 1000)
        mean = statistics.mean(core)
        p99 = sorted(core)[int(0.99 * len(core))]
        ca, cb = clock["a"] * 1000 / len(core), clock["b"] * 1000 / len(core)
        print(f"{n:>8}{mean:>9.3f}{p99:>8.2f}{ca:>9.3f}{cb:>9.3f}{mean - ca - cb:>8.3f}", flush=True)
    if opts.verify:
        print(f"verify: {clock['checked']} channel A scans compared, {clock['mismatch']} differed")


if __name__ == "__main__":
    main()
