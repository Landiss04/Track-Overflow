import itertools, json, os, random, sys
sys.path.insert(0, os.getcwd()); sys.path.insert(0, os.path.join(os.getcwd(), "TrackCtrlHw"))
from track_ctrl_hw import plc

rnd = random.Random(7)
NAMES = ["A", "B", "C", "D", "E", "F"]

def tree(depth):
    if depth == 0 or rnd.random() < 0.2:
        return plc.Constant(rnd.random() < 0.5) if rnd.random() < 0.15 else plc.Read(rnd.choice(NAMES + ["UNDEFINED"]))
    if rnd.random() < 0.25:
        return plc.Negate(tree(depth - 1))
    return plc.Combine(rnd.choice(("AND", "OR", "XOR")), tree(depth - 1), tree(depth - 1))

trees = checked = bad = 0
for _ in range(4000):
    t = tree(rnd.randint(1, 7)); trees += 1
    a, b = plc._walker(t), plc._flat_walker(t)
    for bits in itertools.product((False, True), repeat=len(NAMES)):
        values = dict(zip(NAMES, bits)); checked += 1
        bad += a(dict(values)) is not b(dict(values)) and a(dict(values)) != b(dict(values))
print(f"random trees: {trees} trees, {checked} input combinations, {bad} differences")

# The real Red programs from the recording: channel A old vs flat, random inputs.
rec = [json.loads(l) for _, l in zip(range(8), open(sys.argv[1]))]
progs, total, diff = [], 0, 0
from track_ctrl_hw.vital import vital_source
from track_ctrl_hw.wire import territory_from_wire
for e in rec:
    r = e.get("request", e)
    if r.get("op") == "ACTION" and r.get("action") == "load_territory":
        t = territory_from_wire(r["args"]["territory"]); progs.append(plc.compile_program(vital_source(t)))
    elif r.get("op") == "ACTION" and "source" in json.dumps(r.get("args", {})):
        src = r["args"].get("source")
        if isinstance(src, str): progs.append(plc.compile_program(src))
for prog in progs:
    old = tuple((s.target, plc._walker(s.tree)) for s in prog.statements)
    for _ in range(3000):
        inputs = {n: rnd.random() < 0.5 for n in prog.inputs}
        total += 1
        prog.__dict__["_walkers"] = old; x = prog.scan_a(inputs)
        prog.__dict__.pop("_walkers"); y = prog.scan_a(inputs)
        diff += x != y
print(f"real programs: {len(progs)} programs, {total} scans on random inputs, {diff} differences")
