import json, sys
from pathlib import Path
repo = Path(sys.argv[1]); cap = json.load(open(sys.argv[2]))["track"]; steps = int(sys.argv[3]); out = Path(sys.argv[4])
sys.path[:0] = [str(repo), str(repo / "TrackCtrlHw")]
from common.hw_link import protocol as p
from track_ctrl_hw.territory import load_territory_file
from track_ctrl_hw.wire import territory_to_wire
from utils.harness_protocol import step_message
data = repo / "TrackCtrlHw" / "data"; rid = 1; lines = []
for path in sorted((data / "waysides").glob("red*.json")):
    t = load_territory_file(path)
    rid += 1; lines.append(p.message(p.ACTION, rid, action="load_territory", args={"territory": territory_to_wire(t)}))
    prog = data / "plc" / (path.stem + ".plc")
    rid += 1; lines.append(p.message(p.ACTION, rid, action="load_program", args={"wayside_id": t.wayside_id, "source": prog.read_text(), "file_name": prog.name}))
for i in range(steps):
    s = cap[i % len(cap)]; rid += 1
    lines.append(step_message(rid, i + 1, s["dt"], 18000 + (i + 1) * 0.1, s["inputs"]))
out.write_text("".join(json.dumps(x) + "\n" for x in lines))
print(out, len(lines), "requests")
