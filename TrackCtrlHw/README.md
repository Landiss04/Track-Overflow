# Track Controller (hardware)

The hardware Track Controller runs **every wayside of one line**; the software
Track Controller runs the other line. Each wayside governs a territory loaded
from a database file and runs its own Boolean PLC program. The module knows the
blocks it governs, never the trains on them: everything it exchanges is keyed
by block. Nor does it know failures: a broken rail, a dead track circuit or a
power failure reaches it only as an occupied block, and it reports that block
to the CTC Office as occupied.

Two windows, each its own process:

| Window | Entry point | What it does |
| --- | --- | --- |
| Track Controller | `ui/main.py` | Hosts the module. Loads databases and PLC programs. Shows the territory, blocks, switches, signals, crossings and the reports to the CTC Office. |
| Test UI | `test_ui/main.py` | Stands in for the CTC Office, the Track Model and the clock. Drives the module over a local socket and reads back its outputs. Kept working for the whole project, final demonstration included. |

## Run

From the repository root, with the project virtual environment:

```
python TrackCtrlHw/launch.py              # both windows, each its own process
python TrackCtrlHw/launch.py --no-test-ui # the Track Controller window only
python TrackCtrlHw/ui/main.py             # either window on its own, any order
python TrackCtrlHw/test_ui/main.py
```

Then, in the Track Controller window, **Load database** and pick a file from
`data/waysides/`, and **New PLC** to load the matching program from `data/plc/`.
Load all three waysides to test switching between them. The test UI picks them
up by itself; select a wayside and block there, set inputs, and press **Send
inputs** or run the clock.

Tests (standard library `unittest`; pytest also collects them):

```
cd TrackCtrlHw
python -m unittest discover -s tests -t .
```

`test_link.py` starts a real second process and drives it over the socket.

## Layout

```
track_ctrl_hw/interface.py   boundary types and the TrackController Protocol
track_ctrl_hw/controller.py  HwTrackController: the module (one line)
track_ctrl_hw/wayside.py     one wayside: I/O image, scan, outputs, report
track_ctrl_hw/plc.py         the PLC language: compile, scan on two channels
track_ctrl_hw/territory.py   wayside database parsing
track_ctrl_hw/errors.py      TrackControllerError and its subclasses
track_ctrl_hw/display.py     units and wording for the UIs (imperial)
track_ctrl_hw/schematic.py   territory diagram layout
track_ctrl_hw/views.py       snapshot -> rows the Track Controller window shows
track_ctrl_hw/state.py       Track Controller window <-> QML bridge
track_ctrl_hw/rows_model.py  list model that updates table rows in place
track_ctrl_hw/link.py        test link: server (window) and client (test UI)
track_ctrl_hw/wire.py        JSON form of the boundary types, for the link
track_ctrl_hw/harness.py     the test UI's stand-ins and clock
data/waysides/               three Green line wayside databases
data/plc/                    a PLC program written for each
```

`interface`, `controller`, `wayside`, `plc`, `territory`, `errors`, `display`,
`schematic` and `views` do not import Qt. The module itself is plain Python.

## Integrating the module

### The contract

`track_ctrl_hw.interface.TrackController` is a `typing.Protocol`;
`track_ctrl_hw.controller.HwTrackController` implements it. Per decision D005
the module defines only its own boundary types, and the central harness maps
each neighbour's types into them and back. Nothing here imports
`common/interfaces.py` (D008).

```python
from track_ctrl_hw.controller import HwTrackController
from track_ctrl_hw.interface import TrackControllerInputs

controller = HwTrackController()        # waysides come from the UI's databases
outputs = controller.step(dt, TrackControllerInputs(time_s=..., ctc=..., track_model=...))
```

| Call | When | Notes |
| --- | --- | --- |
| `step(dt, inputs)` | Every tick | Scans every wayside once. `dt` must be finite and positive (D006 fixes it at 0.1 s). Inputs are validated **before** any state changes; `InvalidTimeStepError` / `InvalidInputError` on rejection. |
| `snapshot()` | For display | No side effects. |
| `load_territory(t)` | Track Controller UI | Adds a wayside, or replaces the one with the same ID. Refuses another line, or a block another wayside owns. |
| `load_program(id, source, file)` | Track Controller UI | Compiles and checks the program against that wayside's I/O. `PlcError.diagnostics` lists every problem. Takes effect at the next scan. |
| `reset()` | Test UI only | Never called by the central harness. |

All errors derive from `TrackControllerError`.

### Inputs (`TrackControllerInputs`)

Backend units only (`truth/conventions/units.md`). Track Model blocks are
`BlockKey(line, section, block_id)`, all strings. The CTC Office names a block
its own way, `BlockRef(line, block_id)`, written `Green:13`, with no section. A
switch, its signal and a crossing are each keyed by the block they are listed
on in the database. Inputs for blocks no wayside governs are ignored, so the
harness can send the whole line.

| Field | From | Type |
| --- | --- | --- |
| `time_s` | Clock | Simulation seconds since midnight |
| `ctc.closed_blocks` | CTC Office | `frozenset[BlockRef]`, the full set every tick |
| `ctc.switch_commands` | CTC Office | `{BlockRef of the switch: "normal" \| "reverse"}`; sent only in maintenance mode. The PLC program decides whether to obey |
| `ctc.suggestions` | CTC Office | `{BlockRef: Suggestion(speed_mps: int, authority_blocks: int)}`; a block not listed sends nothing. Speed 0 to 31 m/s: the program's speed input is 5 bits |
| `track_model.occupied_blocks` | Track Model | `frozenset[BlockKey]`; a train or a failure, the module cannot tell which |
| `track_model.switch_positions` | Track Model | Actual positions, `{switch block: position}` |
| `track_model.crossings_active` | Track Model | Actual state, `{crossing block: bool}` |
| `track_model.signal_aspects` | Track Model | Lamps actually lit, `{signal block: "red" \| "yellow" \| "green" \| "super_green"}` |

### Outputs (`TrackControllerOutputs`)

| Field | To | Type |
| --- | --- | --- |
| `track_model.track_circuits` | Track Model | `{block: TrackCircuitCommand(speed_mps: int, authority_blocks: int)}`, only for blocks with a suggestion |
| `track_model.switch_commands` | Track Model | `{switch block: position}` |
| `track_model.crossing_commands` | Track Model | `{crossing block: bool}`; true = lights on, gates down |
| `track_model.signal_commands` | Track Model | `{signal block: aspect}` |
| `ctc_reports` | CTC Office | One `CtcReport` per wayside, every tick |

A `CtcReport` is `wayside_id`, `sent_at_s`, and `blocks: dict[BlockKey,
BlockReport]` — the block key mapped to that block's `occupied`,
`switch_position`, `signal_aspect` and `crossing_active`. Switch, signal and
crossing fields are `None` where the block has none, and are the state the
Track Model reports, not the command. A failed block reports occupied.

### Edge mappings the harness will need, and where they do not line up yet

These are cross-module mismatches, recorded here so they are not lost. None is
decided.

1. **CTC suggestions are per train; this module is per block.** The CTC
   Office's `TrainSuggestion` (on `ctc-interfacing`) carries `train_id` and no
   block, and `signals/suggested-speed.md` and `suggested-authority.md` on
   `truth` key each value by train ID. The harness must know which block each
   train occupies to map it.
2. **The CTC Office expects train reports** (`TrainReport`: train ID, block,
   offset, speed). This module knows no trains and sends none. Train location and
   speed must come from elsewhere.
3. **Authority.** A count of blocks (D013, on `truth`). The CTC's current
   `TrainSuggestion` still carries `authority_block_id`.
4. **Signal aspects.** The software Track Controller uses ORANGE where this
   module uses YELLOW; REQ-INTF-009 requires the two to match.

### The test UI stays

The test UI is supported for the whole project, final demonstration included:
if integration is incomplete, the module is demonstrated through it. It drives
the module only through `step`, so the module never depends on it. `test_ui/`,
`track_ctrl_hw/link.py`, `track_ctrl_hw/wire.py` and
`track_ctrl_hw/harness.py` are its scaffolding; every interface change updates
them in the same commit.

One driver steps the module at a time. Integrated, the central harness calls
`HwTrackController.step` directly and hands the window the same instance with
`TrackControllerState(controller=...)`, so the window shows what the harness
drives. Standalone, `launch.py` runs the window and the test UI.

## Wayside database

The course layout file (`TrackModel/*.json`) cut to one wayside's blocks, with a
`wayside` field added:

```json
{ "line": "Green", "wayside": "1",
  "blocks": [ { "block_number": 12, "section": "C", "length_m": 100,
                "speed_limit_kmh": 45, "infrastructure": { "switch": "12-13; 1-13" } } ] }
```

Read: block number, section, length, speed limit, `infrastructure.switch` and
`infrastructure.railway_crossing`. Everything else is ignored. A switch string
lists normal then reverse; `"57-yard"` style strings list only the diverging
route. **A signal stands at every switch and nowhere else**, named after the
switch's block (`SW-12`, `SIG-12`).

The three samples are exact cuts of `TrackModel/green_line.json`:

| File | Blocks | Equipment |
| --- | --- | --- |
| `green_wayside_1.json` | 1–20 (A–E) | SW-12 (reverse leg back to block 1), XING-19 |
| `green_wayside_2.json` | 21–35 (F–H) | SW-28 (reverse leg to block 150, outside) |
| `green_wayside_3.json` | 74–88 (M–O) | SW-76, SW-85 (legs to 101 and 100, outside) |

## PLC language

The grammar is the software Track Controller's, so one program file runs on
either variant (REQ-INTF-009). This implementation is written separately: the
variants share a language, not code. Full grammar in `track_ctrl_hw/plc.py`;
the names a program can use are in `track_ctrl_hw/wayside.py`:

```
VAR_IN  OCC_1..20 CLOSED_13 SWREV_12 CTCSW_12 CTCREV_12   // inputs
VAR_IN  SPD_3_0..4                                         // speed, bit 0 first
VAR_OUT AUTH_1..20 SW_12 SIG_12_R SIG_12_Y SIG_12_G SIG_12_SG XING_19
VAR_OUT CMD_3_0..4
SW_12 := OCC_1 AND NOT OCC_12 AND NOT OCC_13
```

`AUTH_n` decides whether block *n*'s track circuit passes the CTC Office's
authority (1) or sends 0 (0). Speed is a number, so it crosses into the program
as five bits, `SPD_n_0` (1 m/s) to `SPD_n_4` (16 m/s), and back out as
`CMD_n_0..4`; keeping it under the block's limit is the program's job. Each
statement is compiled twice by different algorithms (recursive
descent and a tree walk; shunting-yard and a stack machine), and both channels
run every scan. A disagreement is a latched channel fault until a new program is
loaded.

## Nothing above the program

The wayside houses its PLC program and decides nothing itself. There is no
vital layer: every protection is the program's to write, and the wayside drives
the program's outputs onto the track as they are. The sample programs show how:

- Separation: a train keeps its authority only while the blocks beside it, on
  the route the switches have set, are clear.
- Closures: `CLOSED_n` zeroes `AUTH_n`.
- Switch locking: a switch holds where it reports (`SWREV_n`) while its block or
  its point is occupied.
- Switch correspondence: `SW_n XOR SWREV_n` turns the signal red and zeroes
  `AUTH` on every block of the route over the switch.
- Crossings: active while a train is on the crossing's block or one beside it.
- Speed limits: `OVER_n` compares the five `SPD_n` bits with the block's limit,
  written into the program as constants; above it, the limit's own bits go out
  as `CMD_n`. Every `CMD_n` bit is ANDed with `AUTH_n`, so held authority sends
  no speed. Six statements a block, so programs run to a few hundred lines.

Signal outputs decode in a fixed order: red if `SIG_n_R` is 1 or none is,
otherwise the first of `_Y`, `_G`, `_SG` that is 1.

Outputs hold their fail-safe values (every signal red, every crossing active,
speed 0 and authority 0, switches where they are) only while no program runs:
none is loaded, a new one has not scanned yet, or the channels have disagreed.

The CTC Office sends no maintenance flag. Its switch commands reach the program
as `CTCSW_n` (a command is in effect) and `CTCREV_n` (it is reverse); the
sample programs obey them.

## Known gaps

- Authority is not truncated at an occupied block: that needs each train's
  direction, which a wayside that knows no trains does not have. The sample
  programs hold a train whose neighbour is occupied instead.
- With no memory between scans, a program can lock a switch only where it
  reports, not where it was last commanded.
- The test UI shows values in backend units (m/s, blocks); the Track Controller
  window shows imperial.
