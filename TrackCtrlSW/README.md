# Track Controller (Software) UI

PySide6 + QML front-end for the ECE1140 wayside Track Controller, covering the
**Program** tab (PLC authoring) and the **View** tab (wayside state), plus the
maintenance-mode manual switch dialog.

Unlike the Train Model stub, the logic behind this UI is real: the PLC language
parses and executes, the vital supervisor clamps the result, and the run /
commit workflow is enforced rather than mocked. What is stubbed is the world
around the module — the Track Model and the CTC are stood in for by
`track_ctrl/system.py` so the wayside has live inputs to react to.

QML owns all visuals; Python owns state and all file I/O. The two talk through
the QML context properties `theme` and `wayside`.

## Run

Two separate programs. Start the Track Controller first, then the test UI in a
second terminal:

```bash
cd TrackCtrlSW
.venv/Scripts/python main.py          # the Track Controller UI
```

```bash
cd TrackCtrlSW
.venv/Scripts/python test_main.py     # the test UI, its own process
```

The test UI waits and connects by itself if the controller is not up yet, and
reconnects if the controller restarts. `main.py --no-test-link` runs the
controller without listening for a test UI.

Offscreen smoke test (no display needed; clean = no output):

```bash
QT_QPA_PLATFORM=offscreen .venv/Scripts/python main.py
```

## Test

```bash
cd TrackCtrlSW
QT_QPA_PLATFORM=offscreen .venv/Scripts/python -m unittest discover -s tests -v
```

41 tests: the physical and user stimuli against the real PLC and safety layer,
refusal of bad input, and the link between the two processes over a real named
pipe (ownership of the inputs, refusals, malformed input).

## Type-check

```bash
cd TrackCtrlSW
.venv/Scripts/python -m mypy main.py test_main.py track_ctrl/ track_ctrl_test/
# no issues in 15 files
```

## Setup (if `.venv` is missing)

```bash
cd TrackCtrlSW
python -m venv .venv
.venv/Scripts/python -m pip install "PySide6==6.8.*" mypy
```

## Layout

```
main.py                   entry point: theme, state, QML engine
track_ctrl/layout.py      static blocks, sections, controller assignment
track_ctrl/plc.py         the boolean-only PLC language: parse, compile, scan
track_ctrl/vital.py       the fail-safe supervisor over every PLC result
track_ctrl/controller.py  one wayside: I/O decode, scan, commit history
track_ctrl/system.py      all lines and controllers, plus the simulation tick
track_ctrl/state.py       the QObject bridge QML binds to
track_ctrl/theme.py       build_theme() -> the design-token dict
ui/Main.qml               window shell, tab bar, header, view switcher
ui/ProgramView.qml        explorer, editor, terminal, live watch
ui/StatusView.qml         line -> controller -> blocks and outputs
ui/components/*.qml       Panel, BlockTile, CodeEditor, SwitchDialog, ...

track_ctrl/stimulus.py    the test link's vocabulary: physical and user ops,
                          snapshot builder (no Qt, no transport)
track_ctrl/link.py        named-pipe server inside the controller process
track_ctrl/qtenv.py       Windows Qt DLL fix shared by both entry points

test_main.py              entry point of the test UI (a separate process)
track_ctrl_test/client.py the test UI's client: connection, stimuli, view model
test_ui/TestMain.qml      the test UI window
test_ui/components/*.qml  ToggleSwitch, ToggleRow, NumberRow, PickerRow
tests/                    unittest suites (stimulus, link)
```

`state.py`, `theme.py`, `link.py` and the test client import Qt; the language,
the safety logic, the controller and the stimulus vocabulary do not, so they
are tested headlessly.

## Test UI

A second program that plays the CTC, the Track Model and the programmer against
a running controller, so the controller's own UI can be watched reacting. It
shares no memory with the controller: the only things in common are the wire
protocol in `track_ctrl/stimulus.py` and the design tokens.

Its three columns separate what each actor can do:

| Column | What it is | Effect |
|---|---|---|
| **Physical inputs** | The world the controller reacts to. Block occupancy, switch fault and moving flags (Track Model); block open/close, suggested speed, suggested authority, speed limit (CTC) | Written onto the target controller's input card. The PLC program sees them, so its outputs move. |
| **Controller outputs** | What the controller is driving, read back live | Display only. |
| **User inputs** | The programmer's hands. Select line or controller, Program/View tab, maintenance mode, the manual switch dialog, Edit / Run / Commit / New, open an iteration, load a `.plc` file | Press the same controls the programmer does in the controller UI, including being refused. They never touch the physical inputs. |

Physical inputs are addressed to a **target controller** chosen in the test UI's
header. That is independent of which controller the programmer has open, because
the world does not depend on what the programmer is looking at: you can stimulate
`GTC-05` while the programmer watches `GTC-01`.

While a test UI is connected, the controller's built-in stand-in trains and CTC
stop, so the test UI is the only source of physical input. The controller's
header shows a **Test link** badge so stimulated occupancy cannot be mistaken for
the stand-in simulation. When the last test UI disconnects, the stand-in resumes.

### The link

A local named pipe, `ece1140-track-controller-stimulus`, one JSON object per
line. It is not a network socket, so it stays inside REQ-DSN-003. Every request
gets an `ack` or an `error`, and a full `snapshot` is pushed after any change.

```
-> {"id":7,"type":"physical","op":"set_occupancy","controller":"GTC-01","block":"G013","value":true}
<- {"type":"ack","id":7,"note":"TEST GTC-01 occupancy G013 = 1"}
<- {"type":"snapshot", ...}

-> {"id":8,"type":"user","op":"set_tab","index":1}
-> {"id":9,"type":"physical","op":"set_suggested_speed","controller":"GTC-01","value":-5}
<- {"type":"error","id":9,"message":"suggested speed must be zero or more"}
```

Physical ops: `set_occupancy`, `clear_occupancy`, `set_block_closed`,
`set_switch_fault`, `set_switch_moving`, `set_suggested_speed`,
`set_suggested_authority`, `set_speed_limit`. User ops: `select_line`,
`select_controller`, `set_tab`, `set_maintenance`, `set_switch`,
`release_switch`, `run`, `commit`, `new_file`, `open_file`, `append_buffer`,
`load_program`.

Bad input is rejected at the controller's boundary and changes nothing
(REQ-NFR-003, REQ-NFR-004): unknown ids, a block owned by another controller,
non-boolean flags, NaN, infinity, negative numbers, a zero speed limit,
oversized text.

## How the module works

### The PLC language

Boolean only, per REQ-FUNC-066 — there is no arithmetic to overflow and no
state carried between scans except what the program writes to its own outputs.

```
// comment
VAR_IN   OCC_12 .. OCC_38        // range shorthand, letters or digits
VAR_IN   SUG_SPEED_0..3
VAR_OUT  SW_SW03 LT_LT03_R LT_LT03_G XING_XG03

BUSY     := OCC_20 OR OCC_21
LT_LT03_G := NOT BUSY
CMD_AUTH_0 := SUG_AUTH_0 AND NOT BUSY
```

Operators are `AND`, `OR`, `XOR`, `NOT` and parentheses. A scan evaluates
assignments top to bottom exactly once, like a real scan cycle. Reading a name
that was never declared yields `0` and raises a warning — an undefined read must
never be able to produce a permissive output.

### Numbers across a boolean boundary

The CTC sends suggested speed as a float and authority as a block count, but the
program only sees bits. The input card encodes both into 4-bit vectors and the
output card decodes them back (`controller.py`). This is the "decoded by OS" box
on the architecture diagram. **Both conversions round down**, so a rounding error
can only ever stop a train short.

### The vital supervisor

`vital.py` sits between the program's outputs and the output card and can only
make an output *more* restrictive. It never raises a speed, extends an authority
or clears a crossing the program left armed. That one-way property is what makes
a wrong program produce a stopped railway rather than a collision:

| Rule | Effect |
|---|---|
| `signal_aspect` | A signal showing zero or several aspects falls back to RED |
| `signal_protects_block` | A signal over an occupied or closed block is RED |
| `switch_locked_under_train` | A switch on an occupied block will not move |
| `crossing_armed` | Occupancy on the approach forces the gates down |
| `authority_truncated` | Authority is cut at the first occupied or closed block |
| `speed_limit` | Commanded speed is clamped to the posted limit |
| `aspect_speed_cap` | An ORANGE aspect halves the commanded speed |
| `maintenance_hold` / `manual_switch_hold` | Authority held at 0 |
| `no_authority` | Zero authority zeroes the commanded speed |
| `fail_safe` | No program, or a failed scan: stop, all red, all gates down |

Every override is reported to the UI with the rule that fired and why, so the
programmer can see exactly where the track disagrees with the code on screen
instead of being silently overruled.

### Run then commit

`RUN` compiles the editor buffer and scans it against a **copy** of the live
inputs. The committed program and the real outputs are untouched, so a broken
candidate cannot reach the track. `COMMIT` promotes it and logs it as a
read-only iteration.

`COMMIT` is refused until the buffer that was run is still the buffer on screen
(`canCommit`). Editing after a run invalidates the verification. Committing
something that has not just been watched execute is the one thing the workflow
exists to prevent, so the rule is enforced in `state.py` rather than left to the
button's enabled state.

The five most recent committed iterations stay readable in the explorer. Opening
one shows it read-only, with `RUN` disabled.

## Design decisions and discrepancies

Where the implementation departs from the wireframes in `ref/ui/`, the reason is
recorded here.

1. **Blocks are numbered, sections are lettered.** The wireframe labels a
   controller's blocks `A`–`L`, conflating sections with blocks. The brief and
   the track data have sections `A`, `B`, … over blocks numbered `1`–`150`, so
   both are modelled: tiles read `F51` (section + number) and PLC signals use the
   number (`OCC_51`). Numbering the signals is also what lets a declaration span
   a run of blocks across a section boundary.
2. **Four aspects, four outputs.** The brief calls for red, orange, green and
   super green; the wireframe draws only `LT_E_R` / `LT_E_G`. Each aspect is its
   own boolean so no single stuck bit can upgrade one aspect into a more
   permissive one, and `vital` enforces that exactly one is lit.
3. **The vital layer is an addition.** The wireframes show raw PLC outputs going
   to track. Producing outputs "in a vital manner" is a stated requirement, so
   the supervisor and its override reporting were designed here, not copied.
4. **Maintenance mode holds authority at zero.** Taking a switch by hand, or
   entering maintenance at all, drops the controller's commanded authority to 0.
   This is the conservative reading of a vital architecture; if the team wants
   maintenance to keep issuing authority, the rule is two branches in
   `vital.supervise`.
5. **Commit requires a clean run of the same buffer.** The wireframe shows RUN
   and COMMIT as peers. The described workflow is a safe debugger, so the
   dependency between them is enforced.
6. **The starter program is generated per controller.** Every wayside owns
   different blocks and devices, so `default_program_source()` writes a working
   program against that controller's own signal names rather than shipping one
   fixed sample that would not compile elsewhere.
7. **Trains and the CTC are stand-ins.** `system.py` walks a few trains along
   each line and issues a constant suggested speed and authority. Replacing it
   with the real inter-module interface means changing one class.
8. **Block closure is driven from this UI.** Closing a block is the CTC's job.
   Until that module exists, clicking a block tile toggles it, so the
   `authority_truncated` rule can be demonstrated.
9. **Controller counts are configurable, not fixed.** `build_default_system()`
   sets Green to 6 waysides and Red to 5 to match the wireframe;
   `build_line(..., controller_count=N)` takes any number and partitions the
   line evenly.
10. **Editor highlighting is in the gutter, not the text.** The language is
    small enough that the useful signal is which lines the compiler rejected, so
    failed lines are marked in the gutter and listed in the Parser pane rather
    than syntax-coloured inline.
11. **`os.add_dll_directory` in `main.py`.** Qt loads its QML plugins with
    `LoadLibrary` at runtime, and Python 3.8+ restricts the DLL search path, so
    on Windows the plugins cannot find the Qt libraries beside them. Without
    this the QML engine fails with "Cannot load library qtquick2plugin.dll".
12. **mypy suppression is scoped to the two Qt bridge modules.** PySide6's
    bundled stubs type `Property()` only in its non-decorator form, so every
    `@Property(...)` in `state.py` and `track_ctrl_test/client.py` is reported as
    a bad call. `call-arg` and `arg-type` are disabled for those two modules in
    `mypy.ini`; every other layer stays fully checked.
13. **Maintenance mode is a user input, not a physical one.** The reference test
    UI lists `MAINT_HOLD` among the PLC inputs. Here it sits under user inputs,
    because it is the programmer's top-bar button; the controller still feeds it
    to the PLC as `MAINT_HOLD`, so it changes the program's behaviour either way.
14. **Switch fault and moving are real inputs.** The PLC reads `FAULT_<switch>`
    and `MOVING_<switch>`, and the starter program uses them. The vital layer also
    enforces them independently, so a program that ignores them is still held: a
    faulted switch drops its signal to RED and cuts authority at its block, and a
    moving switch zeroes the commanded speed.
15. **The speed-limit field replaces the posted limit; it does not only lower
    it.** The reference calls it static initial configuration. It is applied as
    the limit for the controller's blocks while set, and `0` returns to each
    block's own limit. Everything else the vital layer does can only restrict;
    this one is configuration, not a program output.
16. **Outputs recompute immediately.** Each physical input rescans the target
    controller straight away rather than waiting for the next tick, matching the
    reference's "no scan delay", so the effect is visible in both windows at once.
17. **Client sockets are created from Python.** `link.py` subclasses
    `QLocalServer` and overrides `incomingConnection`. The stock server builds
    each client socket in C++, and PySide can hand back a dead wrapper when a
    later socket reuses the address ("Internal C++ object already deleted"), which
    left about one connection in forty unserved when many servers were created in
    one process. Python-created sockets do not have the problem.

## Known gaps

- **Track heaters are not implemented.** The reference test UI has a heater
  status input and a heater command output. The controller has no heater in its
  layout, PLC image or outputs, and the module architecture diagram lists none,
  so there is nothing for those controls to act on and they were left out rather
  than shown dead.
- **Suggested speed and authority are per controller, in MPH and blocks.** The
  reference gives five segments each, with authority in feet.
- Only the light theme of the style guide is implemented.
- The controller has no hardware variation yet; this is the software one.
- Committed programs live in memory, so history does not survive a restart.
- The header's simulation clock is wall-clock time; it is not yet driven by the
  shared simulation clock of REQ-INTF-010.
