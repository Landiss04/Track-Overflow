# Track Controller (Software) UI

PySide6 + QML front-end for the ECE1140 wayside Track Controller, covering the
**Program** tab (PLC authoring) and the **View** tab (wayside state), plus the
maintenance-mode manual switch dialog.

Unlike the Train Model stub, the logic behind this UI is real: the PLC language
parses and executes, the vital code attached to every program restricts the result, and the run /
commit workflow is enforced rather than mocked. The module has no world and
no clock of its own: whatever drives it, the central harness or the test UI,
steps it once per tick with `step(dt, inputs)` and reads back the outputs. The
boundary is `track_ctrl/interface.py`, and the Qt-free module behind it is
`track_ctrl/module.py`. Run alone, the test UI plays the clock, the CTC Office
and the Track Model; see **Test UI** below.

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

### Under the central harness

`python track_overflow.py`, from the repository root, starts the harness and this
module with the others (`common/harness/README.md`). The harness runs
`track_overflow.py --module track-controller-sw`, which is
`track_ctrl/module_process.py`:

- It holds the Green Line only, six waysides, `GTC-01` to `GTC-06` (R77; the HW
  variant runs the Red).
- It starts not ready. A person loads a PLC program on every wayside in the window:
  RUN then COMMIT on each, or **Load starters**. `--load-starters` on the harness
  command line commits the starter programs at launch instead, for tests and
  demonstrations. Until every wayside is ready, nothing is released, and the harness
  logs `WAYSIDES_NOT_READY` with the waysides and the reason.
- It steps once per `STEP`, on its own JSON forms (`track_ctrl/wire.py`). Bad input
  refuses the tick and changes nothing.
- The test link is not opened: the harness is the one driver.
- The header shows the harness's time. It shows the clock paused once no step has
  come for 1 s. The 10x badge stays hidden, since the harness does not send the speed.
- A scripted CTC Office in the harness sends the suggestions until the CTC Office is
  wired in (Phase 4).

## Test

```bash
cd TrackCtrlSW
QT_QPA_PLATFORM=offscreen .venv/Scripts/python -m unittest discover -s tests -v
```

The suites in `tests/`: the module boundary (`test_boundary`), the stand-in
world driving a controller through the real PLC and safety layer
(`test_world`), the programmer's inputs, the commit gate and the clock display
(`test_stimulus`), the link between the two processes over a real named
pipe (one test UI at a time, refusals, malformed input) (`test_link`), and the
process the harness starts (`test_module_process`).

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
track_ctrl/vital.py       generates the vital PLC code attached to every program
track_ctrl/controller.py  one wayside: I/O decode, scan, commit history
track_ctrl/interface.py   the boundary contract: keyed types and the Protocol
track_ctrl/module.py      SwTrackController: step(dt, inputs), snapshot(), no Qt
track_ctrl/wire.py        strict JSON forms of the boundary types, no Qt
track_ctrl/errors.py      TrackControllerError and its subclasses
track_ctrl/state.py       the QObject bridge QML binds to
track_ctrl/theme.py       build_theme() -> the design-token dict
ui/Main.qml               window shell, tab bar, header, view switcher
ui/ProgramView.qml        explorer, editor, terminal, live watch
ui/StatusView.qml         line -> controller -> blocks and outputs
ui/components/*.qml       Panel, BlockTile, CodeEditor, SwitchDialog, ...

track_ctrl/stimulus.py    the programmer's ops over the link and the snapshot
                          builder (no Qt, no transport)
track_ctrl/link.py        named-pipe server inside the controller process
track_ctrl/qtenv.py       Windows Qt DLL fix shared by both entry points

test_main.py              entry point of the test UI (a separate process)
track_ctrl_test/world.py  the stand-in CTC Office and Track Model (no Qt)
track_ctrl_test/client.py the test UI's client: clock, world, link, view model
test_ui/TestMain.qml      the test UI window
test_ui/components/*.qml  ToggleSwitch, ToggleRow, NumberRow, PickerRow
tests/                    unittest suites (boundary, world, stimulus, link)
```

`state.py`, `theme.py`, `link.py` and the test client import Qt; the language,
the safety logic, the controller, the module, the wire forms and the stand-in
world do not, so they are tested headlessly.

## Startup

The controller is vital, so it does not run until it has been started up. The
procedure is the programmer's, from the Track Controller UI:

1. **Load the line.** The UI opens with no track at all. **Load track...** loads
   a line onto the waysides it is built with.
2. **Write or load a PLC program on every wayside.** Open each wayside, write
   the program or **Load .plc file**, then RUN and COMMIT. A wayside with no
   program opens an empty editor, and NEW gives an empty one too: nothing is
   written or committed for you.

Until both are done the line is **not ready**: no wayside on it runs a program,
and a wayside running nothing transmits nothing. One unprogrammed wayside stalls
its whole line. The header shows **NOT READY**, with what is missing on hover. Loading a new line, or `reset()`, makes a ready module not
ready again.

Readiness is reported **per wayside, and so per line**: each wayside's
`CtcReport` carries its line, a `ready` flag (it has a program) and a `reason`
(`no PLC program`), so the CTC Office, and anyone debugging, can see exactly
which waysides are not ready. There is no module-level flag on the wire.
`TrackControllerOutputs.ready` is derived: true only when at least one wayside
reports and all of them are ready, and `.not_ready()` lists the ones that are
not. A wayside that is ready is still held while another is not, since the track
is only safe with every wayside running. The CTC Office must dispatch nothing and
send no speed or authority on a line until its waysides are ready; the stand-in
CTC in the test UI does exactly that.

## The module boundary

`interface.py` holds the module's own boundary types (D005); the harness maps
each edge to and from them and no other module's types appear. What the module
knows and does not:

- **Blocks.** A block is `BlockKey(line, block_id)`: block numbers repeat across
  lines. The section letter is left out while whether it belongs is disputed. A
  switch, its signal and a crossing are named by the block they are listed on.
  Speed and authority are per block, never per train.
- **No trains.** It learns only whether a block is occupied, never which train or
  how fast.
- **No failures.** A broken rail or a dead track circuit reaches it as an
  occupied block. There is no failure input.
- **No heaters.** The Track Model switches them from the temperature.

Each wayside's report carries its own `ready`: see **Startup**.

Inputs, every tick (`TrackControllerInputs`): from the CTC Office the closed
blocks, switch commands (line, switch, position) and a suggested speed and
authority per block; from the Track Model the occupied blocks and the actual switch,
crossing and signal states. Outputs (`TrackControllerOutputs`): to the Track
Model a track circuit per block, switch, crossing and signal commands; to the
CTC Office one `CtcReport` per wayside giving each block's occupancy and the
Track Model's own read-back of its switch, crossing and signal.

A switch whose actual position is not the one last commanded is mid-throw, and
the vital layer holds that block at speed 0. The read-back is otherwise passed
on, not acted on.

`step` checks the whole tick before it changes anything, and ignores blocks no
wayside governs. Every error derives from `TrackControllerError`.

## Test UI

A second program that plays everything around the controller: the **shared
clock**, the **CTC Office**, the **Track Model** and the programmer. Each tick of
its clock it builds the module's boundary inputs from its stand-in world, sends
them as one `step`, and gives the outputs that come back to the world as the
Track Model's read-back: a switch machine goes where it is told, a crossing and
a signal show what they were commanded. This is the call the central harness
will make, so the module is exercised the way it will be integrated. It shares no
memory with the controller: the only things in common are the boundary types,
their JSON in `track_ctrl/wire.py`, and the design tokens.

| Column | What it is | Effect |
|---|---|---|
| **Stimulus inputs** | Separate CTC and Track Model groups. Each group selects one block; Track Model sets occupancy, while CTC sets maintenance mode (which lets its switch commands through), switch state where present, block closure, suggested speed and suggested authority. | Change the stand-in world, so they change what the controller is given on the next tick. Maintenance mode is a system-wide CTC signal. |
| **Controller outputs** | Track circuits, switches, signals, crossings, train presence and vital overrides, read back live | Display only. |

Stimuli are addressed to a **target controller** chosen in the test UI's header.
A block the target does not own is refused. Each source has its own block
selector, and changing a control affects only that selected block (maintenance
mode remains system-wide).

The stand-in trains walk the lines with the clock. Only blocks whose occupancy
is explicitly edited are overridden; other blocks keep updating. By default the
CTC suggests the same speed and authority for every block. The clock starts
when the test UI connects and holds when it leaves; Pause stops simulated
movement and Run resumes it. A step is sent only after the last was answered, so
a slow controller is never buried: ticks that fall due meanwhile are owed, up to
50, and sent as the link frees. Standing alone, the controller idles at its
starter programs and shows `--:--:--`.

### The link

A local named pipe, `ece1140-track-controller-stimulus`, one JSON object per
line. It is not a network socket, so it stays inside REQ-DSN-003. A `step` is
answered with the module's `outputs`, anything else with an `ack`, and a refusal
with an `error`. A full `snapshot` is pushed after any change. **One test UI at
a time:** it plays the whole world, so a second connection is told `busy` and
closed.

```
-> {"id":7,"type":"step","dt":0.1,"inputs":{"time_s":18000.1,"ctc":{...},"track_model":{...}}}
<- {"type":"outputs","id":7,"outputs":{"track_model":{...},"ctc_reports":[...]}}
<- {"type":"snapshot", ...}

-> {"id":8,"type":"user","op":"set_tab","index":1}
<- {"type":"ack","id":8,"note":"user opened the View tab"}

-> {"id":9,"type":"clock","paused":false,"speed":10}
-> {"id":10,"type":"step","dt":-1,"inputs":{}}
<- {"type":"error","id":10,"message":"dt must be finite and positive"}
```

Every per-block value travels as a list of `{"block": {"line", "block_id"},
"value": ...}` entries. Decoding is strict: a missing or extra key, a wrong
type, a negative or fractional speed, or a block listed twice is refused. Speeds
on the wire are whole m/s and authorities whole blocks. The test UI takes mph, as
every screen does, and sends the whole m/s below it.

User ops, the programmer's hands: `select_line`, `select_controller`, `set_tab`,
`set_switch`, `release_switch`, `run`, `commit`, `new_file`, `open_file`,
`append_buffer`, `load_program`. There is deliberately no user op for
maintenance mode: it is not the programmer's. The `clock` message only tells the
header whether the sender's clock is held and how fast it runs; the clock is not
this module's.

Bad input is rejected at the boundary and changes nothing (REQ-NFR-003,
REQ-NFR-004): a bad `dt` or time, a negative or fractional speed or authority,
an unknown position or aspect, oversized text.

## How the module works

### The PLC language

Boolean only, per REQ-FUNC-066 — there is no arithmetic to overflow and no
state carried between scans except what the program writes to its own outputs.

```
// comment
VAR_IN   OCC_12 .. OCC_38        // range shorthand, letters or digits
VAR_OUT  AUTH_12..38 SW_12 XING_19

AHEAD    := OCC_13 OR OCC_14
SIG_12_R := OCC_12 OR CLOSED_12
AUTH_20  := NOT (OCC_19 OR OCC_21)
```

A program can only name what its own controller has. The inputs are `OCC_n`,
`CLOSED_n` and `FAIL_n` for each block it owns, `MAINT`, and `SWREV_s` for each
switch: HW's names, so one program runs on both variants. `FAIL_n` is always 0
here (this wayside is told of no failures; a failed block reads occupied), and
`SWREV_s` is the Track Model's read-back of switch `s`. A suggestion's numbers
never enter a user program; only the vital code sees the speed. The outputs are `AUTH_n` for each block, `SW_s` for each switch,
`SIG_s_R` / `_O` / `_G` / `_SG` for the signal at each switch, and `XING_c` for
each crossing. Block numbers are the track layout's own, and a switch, its signal
and a crossing are named by the block they are listed on. A starter program for
every wayside is generated from its territory, including waysides that own no
switch or crossing at all.

`FAIL_n` exists only so a program written for HW compiles. This wayside is told
of no failures (a failed block reads occupied), so it is always 0.

Every output a controller owns has to be driven, and every `VAR_IN` has to be
something the controller provides. `RUN` checks the program against the selected
controller, not just the language: a program written for another wayside
compiles and is then flagged line by line for the names this controller does not
have.

Operators are `AND`, `OR`, `XOR`, `NOT` and parentheses. A scan evaluates
assignments top to bottom exactly once, like a real scan cycle. Reading a name
that was never declared yields `0` and raises a warning — an undefined read must
never be able to produce a permissive output.

### Speed and authority are per block, in whole m/s

The CTC Office suggests a speed and an authority for each **block**, not for a
train: the blocks are fixed by the track layout, while which trains are on them
changes. Speeds are whole m/s and authorities are block counts, the system's
backend units (D013, `truth/conventions/units.md`). Nothing inside the module is
in mph.

Numbers never enter the user's PLC program. It answers with one bit per block,
`AUTH_n`: pass block *n*'s suggestion down its track circuit (1), or send speed 0
and authority 0 (0). The controller sends a track circuit only for blocks the CTC
suggested something for.

Only the screen shows mph. `display.py` converts at the display layer with the
factor from `units.md` (1 m/s = 2.236936 mph) and nowhere else. A speed typed in
the test UI in mph becomes a whole m/s **rounded down**, so a typed speed can only
become slower, never faster.

### The vital code

Every decision a wayside makes is PLC code: the OS only decodes inputs into bits
and encodes the final bits into typed outputs, and decides nothing. So the vital
supervision is PLC code too. `vital.py` generates it for each wayside from its
own territory and **attaches it to the end of every committed program**. One
scan runs the programmer's program, then the vital code, which reads the
program's outputs (`AUTH_n`, `SW_s`, `SIG_s_*`, `XING_c`) and the inputs and
writes the final `OUT_` bits. Only those leave the wayside. The Program tab
lists it as a read-only `vital.plc`.

It can only make an output *more* restrictive. It never extends an authority or
clears a crossing the program left armed. That one-way property is what makes a
wrong program produce a stopped railway rather than a collision:

| Rule | Effect |
|---|---|
| `signal_aspect` | A signal showing zero or several aspects falls back to RED |
| `signal_protects_block` | A signal on an occupied or closed block is RED |
| `switch_locked_under_train` | A switch on an occupied block stays where it is |
| `crossing_armed` | Occupancy on the approach forces the gates down |
| `closed_block` | A block the CTC closed gets speed 0 and authority 0 |
| `switch_moving` | A switch not where it was commanded zeroes its block |
| `aspect_speed_cap` | Yellow halves its block's speed, rounded down to whole m/s |
| `ctc_switch_command` | In maintenance, a switch follows the CTC's command |
| `manual_switch` | In maintenance, a hand-set switch is held (the CTC wins) |

The OS passes a block's speed, or half of it, or 0, as the bits say. The speed is
the CTC Office's suggestion **clamped to the block's posted limit by the vital
code**: the vital code reads the suggested speed as bits no user program can
declare (`SUGSPD_n_b`, whole m/s, least significant first) and writes
`OUT_SPD_n_b`, comparing against the limit in Boolean code, and RUN lists it as the
override `speed_clamped`. Zero speed for zero authority is still the CTC Office's
(truth `suggested-speed-stops-within-authority`). A wayside running no program, or
on a line that is not ready, runs nothing and transmits nothing, except that its
**crossings are armed** (lights on, gates down): that is their default state until
a program is running and says otherwise.

Overrides are worked out by comparing the program's outputs with the vital
code's, and shown in the UI with the rule and why, so the programmer can see
exactly where the track disagrees with the code on screen. That is display only.

### Run then commit

`RUN` compiles the editor buffer and scans it against a **copy** of the live
inputs. The committed program and the real outputs are untouched, so a broken
candidate cannot reach the track. `COMMIT` promotes it and logs it as a
read-only iteration.

`COMMIT` is refused until the buffer that was run is still the buffer on screen
**and that run produced no diagnostic at all** (`canCommit`). A warning blocks a
commit exactly as an error does: each warning means an output or input does
something other than the code says (an output stuck at 0, a name read as 0, an
assignment overridden), which on a vital controller is not cosmetic. Editing
after a run invalidates the verification. The rule is enforced in `state.py`,
and `TrackController.commit` refuses such a program as well, rather than being
left to the button's enabled state.

Reading a name that is neither a `VAR_IN` nor assigned on an earlier line is
caught by the compiler, statically, so it is reported whatever the inputs
happen to be; the scan's own undefined-read check remains as a backstop.

The five most recent committed iterations stay readable in the explorer. Opening
one shows it read-only, with `RUN` disabled.

## Shared simulation clock

The module has no clock. It is stepped once per tick of the system's one
clock, `utils.system_clock.SystemClock` (D017), and the tick's `time_s` and
`dt` arrive in the inputs. `dt` is fixed (D006): 10x changes how often ticks
come, never how long each is. The module shows the time of the last tick and
stamps its terminal and commits with it; before the first tick it shows
`--:--:--`.

- **Integrated**, the central harness owns the clock, and
  `track_ctrl/module_process.py` steps the controller once per `STEP` with the
  harness's time. The harness does not send the speed or the pause, so the
  header shows **Paused** once no step has come for 1 s, and never **10×**.
- **Standalone**, the test UI owns a `SystemClock` and a `ClockDriver`, ticks
  them in real time at 1x or 10x, and steps the controller over the link.

The CTC Office sets the speed and pauses the clock (D017), so the Track
Controller UI has no clock controls: its header shows the time, and **Paused**
and **10×** badges, told to it by the sender's `clock` message.

## Maintenance mode

Maintenance mode belongs to the CTC Office, and **the CTC sends no mode flag**:
it sends a switch command (line, switch, position) only while the dispatcher is
in maintenance mode, and withdraws it when that ends. So this module treats a
CTC switch command in effect on a switch it governs as maintenance mode, system
wide, and no command as automatic. The Track Controller UI **shows** it (a
read-only badge in the header, a banner on the View tab) and cannot change it.
A switch with a command follows the CTC Office's command, else the programmer's
hand-set position, else the program. The programmer's **Set switch manually**
dialog is enabled only while a CTC command is in effect. One consequence: a
dispatcher who is in maintenance but has not yet commanded a switch looks like
automatic mode here. Maintenance changes who drives the switches and nothing else:
speed and authority are not held. Ending maintenance releases every hand-set
switch and every CTC switch command.

## Track configuration

**Load track...** in the header reads a track layout file (`TrackModel/*.json`),
divides its blocks among the wayside controllers the line is built with, and
installs it. The dialog first reports the line, its blocks, switches and
crossings, and what loading would replace.

- A wayside owns a contiguous run of block numbers. That run need not match a
  section boundary, and a switch belongs to the wayside that owns the block it is
  listed on even when its legs lead into a neighbouring territory.
- **The number of waysides is fixed by the track**, like its blocks; the user
  cannot change it. Green has 6 and Red 5 (`WAYSIDE_COUNTS` in `layout.py`). A
  line with no entry there gets 2, the fewest D014 allows. The dialog shows the
  count but offers no control for it.
- A line of the same name is **replaced**, with its controllers and every program
  and committed iteration they hold, because the territories they governed no
  longer exist. The dialog says so before it loads. A line with a new name is
  added.
- A wayside database (the HW format, one wayside's blocks) is refused with a
  message, and so is a file that is not valid JSON, has a bad block or switch
  entry, or names a count outside what the line allows. Nothing changes when a
  file is refused.

Block ids are the layout's block numbers (`"12"`), so Green 12 and Red 12 are told
apart by their line. Controller ids are `GTC-01`, `RTC-01` and so on.

## View tab outputs

Speed and authority are per block, and a controller may own many blocks, so
nothing is listed one row per block or per device. Track circuits, switches,
signals and crossings, and the CTC's suggestions, each sit behind a drop-down
showing how many there are and the value of the one selected. The block grid
scrolls when a controller owns more blocks than fit.

## Design decisions and discrepancies

Where the implementation departs from the wireframes in `ref/ui/`, the reason is
recorded here.

1. **Blocks are numbered, sections are lettered.** The wireframe labels a
   controller's blocks `A`–`L`, conflating sections with blocks. The brief and
   the track data have sections `A`, `B`, … over blocks numbered `1`–`150`, so
   both are modelled: tiles read `F51` (section + number) and PLC signals use the
   number (`OCC_51`). Numbering the signals is also what lets a declaration span
   a run of blocks across a section boundary.
2. **Four aspects, four outputs.** Signals report Red, Yellow, Green and
   Super Green, as `_R`, `_Y`, `_G` and `_SG`, the names HW uses. The starter
   program uses Red, Yellow and Green and holds `_SG` at zero; a custom PLC can
   request Super Green. The wireframe draws only `LT_E_R` / `LT_E_G`. Each aspect
   is its own boolean so no single stuck bit can upgrade one aspect into a more
   permissive one, and the vital code enforces that exactly one is lit.
3. **The vital layer is PLC code, attached to every program.** The wireframes
   show raw PLC outputs going to track. Producing outputs "in a vital manner" is a
   stated requirement, and the wayside can have only the OS (decode and encode)
   and the PLC (every decision). So the vital supervision is generated PLC code
   that runs after the programmer's program in the same scan; see **The vital
   code**.
4. **Maintenance mode is the CTC's and holds nothing.** Switch control gives
   the CTC's command precedence over a programmer's hand-set position, then
   falls back to the PLC. The vital code neither holds authority in
   maintenance nor counts blocks ahead: a wayside knows neither the route nor
   the direction of travel, so authority is the CTC's to stop before a hazard
   (`arbitration/authority-stops-before-obstruction`). It still zeroes the
   authority of a block that is closed, or holds a switch that is not where it
   was commanded.
5. **Commit requires a clean run of the same buffer.** The wireframe shows RUN
   and COMMIT as peers. The described workflow is a safe debugger, so the
   dependency between them is enforced, and "clean" means no warnings either.
6. **The starter program is generated per controller.** Every wayside owns
   different blocks and devices, so `default_program_source()` writes a working
   program against that controller's own signal names rather than shipping one
   fixed sample that would not compile elsewhere.

   **Switches** are set for the train coming to them, from the track chart
   (each block's `next_blocks`, which every controller carries for its whole
   line) and what the wayside sees. A train comes to a switch's points from its
   fixed side (facing) and takes the one leg it may run on to, or comes off a
   leg (trailing) and needs that leg. The CTC Office counts authority only up to
   a switch not set for the route, trailing moves included, so the switch is set
   first:

   - facing: the train is on the fixed-side block and the points block is clear
     (`NOT OCC_p AND OCC_f`);
   - trailing, off a one-way leg: the train is on the leg (`OCC_l`). Where the
     leg is the block the switch is listed on, a train in it locks the switch,
     so the block before it occupied counts too, where that block is the
     wayside's own;
   - a way in through another wayside's block cannot be seen, so the switch
     stands for it while no train is seen: Green 28 stands reverse for a train
     coming off 150, and goes normal for a train on 27 about to enter 28.

   The program cannot see which way a train is heading (that needs a suggestion
   bit, which HW's language does not have), so a train on a leg is taken to be
   coming for the points.

   A switch is held where it stands (`SWREV_s`) while its points block is occupied,
   whichever block the switch is listed on (Green 12's points are 13, Green 76's
   are 77), and while trains come for both positions. In maintenance it is
   normal unless held, as before; the CTC Office's command or a hand-set position
   drives it then. The yard is not routed (D022): a train is retired stopped at
   the yard entry block, so switches 58 and 62 stay normal. With these, a Green
   train runs from the yard round the whole line back to 57
   (`common/harness/tests/test_harness_train_loop.py`, `ReturnToYardTest`, run
   with `TRACK_OVERFLOW_ROUND_TRIP=1`; today the Train Controller's engine
   detector stops the train at 93 first, see `INTEGRATION_DISCREPANCIES.md` E7).
   Where the layout gives no direction, or the points are another wayside's, the
   switch is held where it stands. On the Red Line, which runs both ways, the
   starter cannot tell a train's direction from occupancy, so its switches stay
   normal.
7. **The world and the clock live in the test UI.** The module is stepped from
   outside (D006), so the stand-in trains, the CTC's suggestions and the clock
   moved out of it into `track_ctrl_test/`. Integrating means the harness calls
   `step` where the test UI did; nothing in the module changes.
8. **The Track Controller UI cannot close or open blocks.** That is the CTC
   Office's permission; block tiles are read-only. Closures arrive as a physical
   input, from the CTC in the integrated system and from the test UI's CTC
   section standing alone.
9. **The layout is loaded; the wayside count is the track's.** The UI starts
   empty and **Load track...** installs the real Green or Red layout on the 6 or
   5 waysides it is built with. The user never chooses the count, since a
   physical line comes with its waysides. The generated synthetic network of the
   first version is gone.
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
13. **Maintenance mode is inferred, not sent.** The CTC removed the mode flag and
    sends only switch commands, so the module reads "a command in effect" as
    maintenance and feeds that to the PLC as `MAINT`. The test UI's CTC section
    keeps a maintenance switch, but all it does is let its commands through, as
    the real CTC does.
14. **A switch that will not follow is "moving".** The Track Model reports each
    switch's actual position, which the PLC reads as `SWREV_<switch>` (HW's
    name). The vital code compares it with the switch it is about to command: if
    they differ the switch is mid-throw and its block's authority is zeroed, even
    if the program ignores it. There is no `FAULT_<switch>`: the controller is
    told of no failures.
15. **The posted-limit clamp is vital PLC code.** Zero speed for zero authority
    is the CTC Office's (truth `suggested-speed-stops-within-authority`). The clamp
    to the posted limit was once a Python rule in the old supervisor, then the CTC
    Office's; since 2026-10-28 it is generated Boolean code in the vital program
    (a comparison against the limit for each block, on speed bits only the vital
    code can read), so only PLC code decides and a user program still never sees or
    sets a speed. The stand-in CTC in the test UI
    suggests under each block's limit. The per-controller speed-limit override is
    gone.
16. **A physical input is sent on the next step, not the next tick.** Editing
    the world in the test UI owes the controller one extra step straight away, so
    the effect shows in both windows without waiting up to a tick.
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
- **`FAIL_n` is always 0.** It is in the PLC image only so a program written for
  HW compiles; this wayside is told of no failures.
- **Signal and crossing read-back is only reported.** It goes to the CTC Office in
  each wayside's report and into the snapshot, but does not feed the vital code.
- **Block tiles show `TEST` as the train.** The boundary carries presence, not a
  train's identity.
- Only the light theme of the style guide is implemented.
- The controller has no hardware variation yet; this is the software one.
- Committed programs live in memory, so history does not survive a restart.
- Under the harness the module runs with the Track Model and a scripted CTC Office
  (Phase 3). The CTC Office joins in Phase 4 and the HW Track Controller in Phase 5;
  see `INTEGRATION_DISCREPANCIES.md` for every known mismatch.
- Under the starter program, two trains in adjacent blocks hold each other for good.
  The starter cannot tell direction; the CTC Office's authority is
  to keep trains apart.
- Under the starter program, a train about to enter Green 76 while another stands
  on 77 bound for 101 enters 76 with switch 76 reverse, and the switch then locks
  under it (the vital lock is on the block a switch is listed on, 76, not on its
  points, 77): it waits for good. The train coming to 76 is on 75, another
  wayside's block. The CTC Office's two-way zone (77 to 100) should keep
  scheduled runs from meeting there; see `INTEGRATION_DISCREPANCIES.md` E7.
18. **Lists reach QML as `{"rows": [...]}`.** A list property read from QML is a
    live reference: every `.length` or element access inside `filter` calls the
    Python getter again, once per element. A view that filtered a 30-row list in
    eight places made over two hundred getter calls per refresh, about 150 ms of
    the UI thread, enough to delay the test link by seconds. `list_property` in
    `models.py` nests the list in a map, which QML copies in one call. A refresh
    is now about 3 ms. Block tiles use a list model that updates only the rows
    that changed.
19. **Programs are checked against the controller, not only the language.** The
    compiler cannot know which names a wayside has, so `check_program` reports
    inputs and outputs the controller does not own and outputs it leaves undriven.
    Together with the warnings-block-commit rule, a program for the wrong wayside
    cannot be committed.
