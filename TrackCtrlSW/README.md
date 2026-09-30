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

```bash
cd TrackCtrlSW
.venv/Scripts/python main.py
```

Offscreen smoke test (no display needed; clean = no output):

```bash
QT_QPA_PLATFORM=offscreen .venv/Scripts/python main.py
```

## Type-check

```bash
cd TrackCtrlSW
.venv/Scripts/python -m mypy main.py track_ctrl/    # no issues in 9 files
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
```

Only `state.py` and `theme.py` import Qt, so the language and the safety logic
can be tested headlessly.

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
12. **mypy suppression is scoped to `state.py`.** PySide6's bundled stubs type
    `Property()` only in its non-decorator form, so every `@Property(...)` in the
    bridge is reported as a bad call. `call-arg` and `arg-type` are disabled for
    that one module in `mypy.ini`; the layout, PLC, vital, controller and system
    layers stay fully checked.

## Known gaps

- Only the light theme of the style guide is implemented.
- The controller has no hardware variation yet; this is the software one.
- Committed programs live in memory, so history does not survive a restart.
- The header's simulation clock is wall-clock time; it is not yet driven by the
  shared simulation clock of REQ-INTF-010.
