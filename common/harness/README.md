# Central harness

The harness is the one process that owns the simulation clock and drives every module
(D005, D017). It starts each module as a process of its own and sends every module, on
every tick, `dt`, the simulation time, and its inputs. It then waits for every reply
before the next tick. The design, and the R and G numbers cited in the code, are in
[`documents/system-integration-design.md`](../../documents/system-integration-design.md).

Phase 0 built the harness, its protocol, and a stub process standing in for each of the
seven modules. Phase 1 wired in the Train Model and the Train Controller SW, Phase 2 the
Track Model, Phase 3 the Track Controller SW, on the Green Line only (R77), and Phase 4
the CTC Office. The CTC Office dispatches a Green Line train from the yard, and the
train runs on its suggestions through the Track Controller. The other two modules are
still stubs: the Track Controller HW and the Train Controller HW.

## Run it

From the repository root, in the project's virtual environment:

```
python track_overflow.py                     # Phase 4 system, 1x
python track_overflow.py --speedup           # 10x
python track_overflow.py --auto-run          # press Run by itself (tests, demonstrations)
python track_overflow.py --load-starters     # commit the starter PLC programs at launch
python track_overflow.py --dispatch G1:Green:65   # dispatch once the line is ready
python track_overflow.py --run-seconds 30    # stop by itself
python track_overflow.py --log-dir logs      # event log folder
python track_overflow.py --stubs-only        # a stub for every module, as in Phase 0
```

No arguments open the operator window. Add `--headless` to echo every event to the
console, with a status line every 5 s. Ctrl+C ends the run in either mode. The clock
starts paused. In a window run the dispatcher presses Run in the CTC Office's window
(D017; R83, Kevin Schillinger's decision of 2026-10-21 on Q-P4-1). A headless run has
the CTC Office press Run as soon as it is ready (`--run-on-ready`, below), and so does a
`--stubs-only` run, whose stub CTC Office has no window. `--auto-run` does the same in a
window run, for tests and demonstrations only, as `--load-starters` and `--dispatch`
are. The dispatcher can pause the run in the CTC Office's window either way.

A run needs three people, or the options that stand in for them: one loads the PLC
programs, one dispatches a train, and one sets the train's gains.

1. The harness starts seven module processes: the CTC Office, the Track Controller SW,
   the Track Model, the Train Model and the Train Controller SW as themselves, each in
   its window, and stubs for the two HW variants.
2. The clock starts paused (D017). The dispatcher presses Run in the CTC Office's
   window, or the CTC Office presses it once ready in a headless or `--auto-run` run
   (R83). The harness reads Run, Pause and 1x / 10x from its outputs and its `STATE`
   (R3, R51).
3. The Track Controller runs the Green Line's six waysides, `GTC-01` to `GTC-06`. It
   starts not ready (R44, R70). A person loads a PLC program on every wayside in its
   window: RUN then COMMIT on each, or **Load starters**. `--load-starters` commits the
   generated starter programs at launch instead, for tests and demonstrations.
4. Until then the clock runs and nothing is released. The harness logs
   `WAYSIDES_NOT_READY` with the waysides and the reason, and `WAYSIDES_READY` once every
   wayside on the line is ready. The CTC Office sends nothing for the line and refuses a
   dispatch on it.
5. The dispatcher dispatches a train from the yard in the CTC Office's window.
   `--dispatch TRAIN:LINE:BLOCK` gives that dispatch once the line is ready instead, for
   tests and demonstrations; it may be repeated.
6. The CTC Office releases the train itself and reports it once in `new_trains` (D022,
   R46). The Track Model places it on the yard exit block (Green 63) a tick later. It
   joins the Train Model a tick after that, and the Train Controller a tick after that.
7. The train waits there until an engineer sets its gains in the Train Controller's
   console (D024).
8. The CTC Office finds the train at 63 and follows it from occupancy. It suggests a
   speed and an authority for the train's block, and for the next block with one block
   less (R49). The Track Controller passes them down each block's track circuit through
   its PLC program. With `--dispatch G1:Green:65`, G1 stops at GLENBURY (block 65,
   platform on the right) with its doors open.

A module window that is closed only hides; the process ends when the harness does.

## Files

| File | What it holds |
|---|---|
| `../../track_overflow.py` | The one executable. No arguments start the harness; `--module <name>` starts one module. |
| `app.py` | Window/headless selection, status line and Ctrl+C handling. |
| `console.py`, `window.py`, `ui/` | Display snapshots, QML bootstrap and operator window. |
| `core.py` | `Harness`: the tick loop, timeouts, rejections, the CTC Office's clock controls, and the event log. |
| `pacer.py` | `TickPacer`: ticks the clock in real time, one tick in flight at a time. |
| `supervisor.py` | `ModuleSupervisor`: starts the module processes, accepts their links, and ends them. |
| `modules.py` | Module names, the edge map (`PRODUCERS`), which modules are wired in (`WIRED_MODULES`), and how a module process is started. |
| `edges.py` | `SystemEdges`: builds every module's inputs, with real edges into the wired modules. |
| `roster.py` | The trains in service, from the CTC Office's `new_trains` and `retired_trains` (D022). |
| `train_edges.py` | The edges between the Train Model and the Train Controller. |
| `track_edges.py` | The edges between the Track Model and the trains, the Track Model's block names, and the Track Model's ticket sales to the CTC Office (`track_model_to_ctc`, `TicketSales`). |
| `wayside_edges.py` | The edges into and out of the Track Controller: from the CTC Office, from and to the Track Model, and to the CTC Office. Also `line_ready`, and `merge_ctc_inputs`, which joins the Track Controllers' reports. |
| `track_devices.py` | Each switch's ID (the Track Controller's name), its point (the Track Model's name), and the block of its light, read from the layout files. |
| `stub_module.py` | The stand-in module process, with scripted faults. The CTC Office's stub also releases and retires trains on cue. |
| `stub_edges.py` | Inputs for a stub: its producers' outputs whole. |
| `measure.py` | The real-time budget measurement (G-CLK-6). |
| `ctc_edges.py`, `track_model_edges.py` | Edge mappings written before the process model. `track_model_edges.py` maps through the superseded catalog (R11); the running system uses `track_edges.py` instead. |
| `../../utils/harness_protocol.py` | The wire protocol, shared by both ends. |
| `../../utils/module_link.py` | `ModuleLink`: a module's end of the link. |
| `../../utils/module_window.py` | Makes a module process's windows hide instead of closing. |
| `../../utils/event_log.py` | The CSV event log. |
| `../../CTC-Office/ctc/module_process.py` | The CTC Office process the harness starts, with `wire.py`, its types as JSON, and `ctc_ui/harness_clock.py`, the window's clock face on the harness's time. |
| `../../TrackCtrlSW/track_ctrl/module_process.py` | The Track Controller SW process the harness starts, with `wire.py`, its types as JSON. |
| `../../TrackModel/track_model/module_process.py` | The Track Model process the harness starts, with `wire.py`, its types as JSON. |
| `../../TrainModel/train_model/module_process.py` | The Train Model process the harness starts, with `wire.py`, its types as JSON. |
| `../../Train-Ctrl_HW/train_ctrl/module_process.py` | The Train Controller process the harness starts. |

## One tick

1. The pacer ticks the clock once the tick is due and the last one is over.
2. The harness builds each module's inputs from the outputs every module gave on the
   tick before, and sends every module a `STEP` at once.
3. Each module steps and replies with `OUTPUTS`, or `REJECTED` with a reason.
4. Once every reply is in, those outputs become the inputs of the next tick.

What happens when something goes wrong:

| Case | What the harness does |
|---|---|
| A module rejects a tick | It logs `TICK_REJECTED`. The module keeps its previous outputs, and the run goes on (R19). |
| A reply is later than 1 s | It logs `REPLY_LATE`, names the module (`modulesLate`), and pauses the clock. The clock resumes once the reply comes. |
| A line does not decode: not JSON, a number that is not finite or is past the range of a double, or text that is not valid Unicode | It logs `PROTOCOL_ERROR` and skips the line. The reply it held never arrives, so after 1 s the clock pauses and names the module, as for `REPLY_LATE`. |
| A line is longer than the limit (8 MiB) | It logs `PROTOCOL_ERROR` for that line and reads on from its newline. The link stays open, and the lines after it are read. |
| A module ends or drops its link | It logs the exit and holds the clock for the rest of the run. Modules are never restarted mid-run. |
| A reply comes twice, for no request, or with the awaited request ID but another tick | It logs `UNEXPECTED_REPLY` and ignores it. Every request is answered once. |
| A module's inputs cannot be sent as JSON, such as an infinity an edge computed | It logs `INPUTS_FAILED` for that module, which misses the tick. The other modules still get theirs. |
| The run falls behind real time | Owed ticks run back to back, up to 100. Past that the backlog is dropped and logged as `TIME_SLIPPED`. No module misses a tick; simulation time runs slower than real time. Ticks still owed when the run ends are dropped without a `TIME_SLIPPED`. |
| A pause with ticks owed | At most the next tick stays owed, so the run resumes without a burst. |

The clock runs only while every module is ready, none is late or down, and the CTC
Office asks it to run. Its `clock_paused` and `clock_speedup` are read from its outputs,
and while the clock is paused, from its `STATE` messages.

## Protocol

Newline-delimited JSON, one object per line, over a Qt local socket: a named pipe on
Windows and a socket file elsewhere. Every message carries `op`, an integer request `id`
and the `tick`. Numbers are finite and within the range of a double, and text is valid
Unicode, written as raw UTF-8. Both ends refuse a line that breaks either: `1e999` is
valid JSON text but would read as infinity. The full description is the docstring of
`utils/harness_protocol.py`.

| Direction | `op` | Fields |
|---|---|---|
| harness → module | `STEP` | `dt`, `sim_time_s` (unwrapped, at the end of the step), `inputs` |
| harness → module | `QUIT` | none |
| harness → module | `SHOW` | none; reopen a window, no reply or step |
| module → harness | `READY` | `module`, `protocol` (the version, now 1) |
| module → harness | `OUTPUTS` | `outputs`; `id` and `tick` of the `STEP` it answers |
| module → harness | `REJECTED` | `reason`; `id` and `tick` of the `STEP` it answers |
| module → harness | `STATE` | `state`, a change made between ticks |

The harness listens on a server named `track-overflow-<pid>-<random>`, open only to the
same user, and passes the name to each module as `--harness <name>`. A connection's
first message must be `READY` naming an expected module that is not yet connected.
Anything else is refused and logged.

## Trains and edges

The edges (`edges.py`) build each module's inputs from the outputs every module gave on
the tick before. They see each tick's new outputs once, when the tick is over
(`Edges.tick_completed`), and that is where the CTC Office's train events take effect,
exactly once.

- **Roster.** A train in the CTC Office's `new_trains` joins the modules a tick apart,
  each once the module it needs input from has it: the Track Model first, which places
  it on its line's yard exit block (Green 63, Red 9; D022); its Train Model once the
  Track Model feeds it; its line's Train Controller (Green: SW, Red: HW, D021) once the
  Train Model reports it. A train in `retired_trains` leaves all three, and the Track
  Model clears its block. The harness logs `TRAIN_ADDED` and `TRAIN_REMOVED`, and refuses
  a malformed ID or a line other than Green or Red.
- **Block names.** The Track Model names a block its own way (`GREEN K-63`); every other
  module by line and number (`Green`, `63`). `track_edges.BlockNames` learns the Track
  Model's names from the blocks its outputs list, and the edges translate both ways.
- **Train Model → Track Model.** Each train's `track` outputs become its report: block,
  offset, speed, block-changed flag and capacity, with `doors_open` when either door is
  open (`signals/door-state`). Until the Train Model reports a block for a new train,
  the harness sends `placement_report`: at rest at the start of the yard exit block.
- **Track Model → Train Model.** Each train's feed becomes its `track` input, field for
  field, with the block named by its number. A beacon passes unchanged: the Train Model
  checks its payload (`utils/beacon_codec.py`) and rejects a train whose beacon is
  malformed, so only that train misses the tick.
- **Track Model → Train Controller.** The light a train saw as it entered a block with a
  signal (`signal_seen`), sent on that tick only, with `SUPER_GREEN` spelled the Train
  Controller's way. The Train Controller keeps the last light it was given. Truth's
  `signal-aspect-ahead` asks for the next light ahead on every tick; the Track Model
  reports it only on entry so far.
- **Train Controller ↔ Train Model.** As in Phase 1 (`train_edges.py`). Until a train's
  first commands arrive, the Train Model gets `INERT_COMMANDS`: no power, the service
  brake on, doors shut.
- **The CTC Office.** It runs as itself (`CTC-Office/ctc/module_process.py`), stepped
  once per `STEP` on its own JSON forms (`ctc.wire`), with no clock, socket link or
  clock link of its own (D005, D017, D025). Its outputs are its suggestions, closed
  blocks and switch commands for the Track Controller, `clock_paused` and
  `clock_speedup` for the harness, and the one-time `new_trains` and `retired_trains`
  for the roster. Run, Pause and 1x / 10x in its window go to the harness at once as
  `STATE`, not only while paused (R51). It refuses a malformed tick and changes nothing.
  Its window redraws at most every 200 ms, after the reply. It takes its time from each
  `STEP`'s `sim_time_s`, so a refused or missed tick does not leave its schedule behind
  (`4cc873b`). Its **Return to yard** button, in the Selected train panel, orders a
  manual train to its line's yard entry block (Green 57, Red 9); the CTC Office retires
  it in `retired_trains` once it has stopped there with authority 0 (R66, D022).
- **The CTC Office's test options.** They stand in for the dispatcher, as
  `--load-starters` stands in for the person who loads the PLC programs and
  `--engineer-gains` for the engineer. `app.py` passes `--run-on-ready` for a headless,
  `--stubs-only` or `--auto-run` run (R83), never otherwise, and the others only when
  asked:
  - `--run-on-ready` presses Run as soon as the process is ready;
  - `--speedup-at-tick N` presses 10x after step `N`, or before the first step with 0
    (`app.py --speedup` passes 0);
  - `--dispatch TRAIN:LINE:BLOCK` dispatches a train from the yard to a block once the
    line's waysides are ready; `app.py --dispatch` passes it on;
  - `--schedule FILE` loads a schedule and runs it in automatic mode (D020).
- **CTC Office → Track Controller.** `wayside_edges.ctc_to_track_controller`, from the
  CTC Office's outputs. The train ID stops here (R48). Of two suggestions for one block,
  the lower speed and the lower authority win, each on its own.
- **Track Controller ↔ Track Model.** `track_controller_to_track_model` and
  `track_model_to_track_controller`. Commanded speed and authority go per block. A
  switch changes names on the way (`track_devices`): the Track Controller names it by the
  block it is listed on (truth `identifiers`), the Track Model by its point. A light goes
  through its switch: the Track Controller names it by the switch, the Track Model by the
  block it stands on. Green: 12/13/14, 28/28/27, 58/57/56, 62/63/64, 76/77/78, 85/85/84
  (switch/point/light). A failed block reads occupied on the way back (R33). No heater
  commands go to the Track Model (D026).
- **Track Controller → CTC Office.** `track_controller_to_ctc` makes the CTC Office's
  `track_controller` input: occupancy, switches, crossings and each wayside's readiness.
  A failed block reaches it as occupied, with nothing else said (R69). Every wired Track
  Controller's report is joined, list by list (`wayside_edges.merge_ctc_inputs`), so the
  HW variant's Red reports can join the SW variant's Green ones in Phase 5.
- **Track Model → CTC Office.** `track_edges.track_model_to_ctc` makes the CTC Office's
  `track_model` input: ticket sales per station since the last report (R52). A station
  that sold none is left out; a count that is not a whole number is an error.
  `track_edges.TicketSales` passes each sale on exactly once: sales wait until the CTC
  Office replies with outputs to the tick they were sent on, so a refused or missed tick
  is sent again with the next, and a Track Model's repeated last outputs are never
  counted twice.
- **Readiness.** A line is ready once a wayside on it has reported and every wayside on it
  is ready (`line_ready`). The harness logs `WAYSIDES_NOT_READY` and `WAYSIDES_READY` when
  a line's readiness changes, from the Track Controller's own outputs on the tick they
  come. Readiness never holds the clock (R71).
- **Left the track.** A train the Track Model stops feeding has run into the yard. The
  harness logs `TRAIN_LEFT_TRACK` and drops it from every input, but leaves it on the
  roster: retiring trains is the CTC Office's (D022).
- **Rejections.** The Train Model steps each train on its own. A train whose inputs it
  refuses misses the tick, and the harness logs `TICK_REJECTED` with the train's ID. The
  Track Model refuses a whole tick if any input is invalid, and keeps its last outputs.

Every train's inputs and outputs for the Train Model and the Train Controller travel
under `trains`, keyed by train ID. Each module names its own fields: the Train Model as
in `train_model/interface.py`, the Train Controller as its `read_inputs` keys and
`TrainModelCommands` fields, the Track Model as in `track_model/interface.py`
(`track_model/wire.py`).

A command comes back in a report two ticks after it is sent: the Train Model acts on it
on the next tick, and its report reaches the Train Controller the tick after. The Train
Controller allows for that (`echo_ticks`). Otherwise the report of its own emergency
brake would read as a passenger pull and undo the driver's release.

The Track Model's window redraws at most every 100 ms, after the reply to a step, so its
tables never hold up a tick.

### Train Model review reconciliation (2026-10-20)

The [Train Model SDD v0.2](../../documents/Railway_Sim_SDD_Train_Model.md) records
accepted design; [module follow-up](../../TrainModel/docs/open-issues.md) records
source-inspected status. The working tree now includes independent brake states
and summed forces, complete beacon payload validation, harness-time display and
15-tick per-train drift checks, and next-station/platform display without arrival.
These are concurrent implementation edits, not test results from this doc review.

Each supplied timestamp is unwrapped end-of-tick time. A train’s epoch is its first
timestamp minus dt; on harness ticks divisible by 15 compare epoch plus accepted
model elapsed time with supplied time, including rejected trains, using `1e-6 s`
absolute tolerance. Display follows harness time independently. Never reset physics
time or the epoch to hide drift. The standalone utility’s 30-tick check is separate.

The harness maps module-owned types directly (D005/D008); `common/interfaces.py`
is stale. Phase 2 wires the Track Model process through the direct edges in
`track_edges.py`. Track Model owns station eligibility for boarding; Train Model checks
rest, doors, valid count and capacity without a station gate. Position offset
references the train’s front. Controller one-shot `passenger_brake_release` clears
only the passenger latch; a held controller emergency command remains active.

Existing tests are local developer verification utilities.

## Event log

One CSV file per run, written by the harness (R80). Its columns are `wall_time`,
`sim_time_s`, `time_of_day`, `tick`, `source`, `event`, `detail`. It is named
`events-YYYYMMDD-HHMMSS.csv` from the launch time. The file is created exclusively, so a
second run started in the same second gets `events-YYYYMMDD-HHMMSS-2.csv`, a third `-3`,
and so on; no run overwrites another's log. The harness prints the path it got. By
default it is in the user's local application data folder:

- Windows: `%LOCALAPPDATA%\TrackOverflow\logs`.
- Linux: `~/.local/share/TrackOverflow/logs`.

Every row is flushed as it is written. Text that is not valid Unicode is escaped rather
than written raw. The events are listed in the docstring of `core.py`.

## Wiring in a real module

A module joins the harness in place of its stub, as the Train Model and the Train
Controller did in Phase 1, the Track Model in Phase 2, the Track Controller SW in
Phase 3 and the CTC Office in Phase 4 (their `module_process.py` files are worked
examples). Its process:

1. Runs under `track_overflow.py --module <name>`. `<name>` is the module's name in
   `modules.py`. Add a runner for it to `_MODULES` in `track_overflow.py`.
2. Creates a `ModuleLink(name, harness_name, step)` and calls `connect_to_harness()`.
   `step(tick, dt, sim_time_s, inputs)` steps the module once and returns its outputs.
   Raising `TickRejectedError` refuses the tick and leaves the module's state unchanged.
3. Calls `announce_ready()` once it can step. For the Track Controllers that comes after
   loading, which a person does in the window.
4. Quits on `quitRequested`, and on `harnessLost`. Hides its window instead of closing it
   (`utils/module_window.py`), since only the harness ends a module. Ignores Ctrl+C, which
   the harness handles.
5. The CTC Office only: calls `push_state({"clock_paused": ..., "clock_speedup": ...})`
   when the dispatcher presses Run, Pause or the speed toggle. The harness needs it
   while the clock is paused; the CTC Office sends it on every press, after `READY`.

In the harness, the module joins `WIRED_MODULES` in `modules.py`, so `system_specs` runs
it as itself, and `SystemEdges` gains the edges into it: mapping functions from its
producers' types to its own (D005).

## Tests

From the repository root:

```
python -m pytest common/harness/tests utils/tests
python -m unittest discover -s common/harness/tests
```

The Phase 0 end-to-end tests start the harness four times, with seven stub processes
each. They check ticks, time, the one-tick input latency, readiness, speed, pause and
resume, rejection, a duplicate reply, refused connections, a late reply, a crash, and
stopping while a module is still loading. They take about 5 s.

Phases 1 to 4 add three layers of tests:

- `test_harness_edges.py`: the roster, the edges, the Track Model's block names and the
  switch places, as plain objects; the readiness events, the CTC Office's inputs, the
  Track Controller's `ctc` input from the CTC Office's outputs, ticket sales passed on
  once across accepted and refused ticks, and `merge_ctc_inputs`. The switch places are
  checked against both modules' own layout readers on Green and Red, and each edge's
  output is fed to the receiving module's own decoder (`track_ctrl.wire`,
  `track_model.wire`, `ctc.wire`). The real Track Model's stations pass the CTC Office's
  own validator.
- `test_harness_train_loop.py`: the five module processes' step functions, the CTC
  Office's included, in one process, wired through `SystemEdges` with the harness's
  one-tick delay, every message through JSON. It runs the whole default route:
  readiness, the CTC Office's release and the order the modules take the train, the CTC
  Office's view of the train block by block, the GLENBURY stop and the dwell behind the
  door interlock, boarding, switch and light read-back by both names, crossings, a
  broken rail ahead, and the stop at DORMONT; and the driver's release of the emergency
  brake, with and without a passenger pull. It takes about 13 s. `ReturnToYardTest` (5
  tests, about 140 s) runs a scheduled Green run round the line to the yard entry block
  57 and its retirement, only with `TRACK_OVERFLOW_ROUND_TRIP=1`. It initially exposed
  a false engine-failure latch at Green 93 (Q-P4-8), fixed in `460579b`. The full
  round trip now passes with the detector enabled: five tests passed in 38.95 s in
  the orchestrator's targeted check of 2026-10-21 (the earlier environment took about
  140 s). The extra steady-fall detector criterion still awaits Kevin's acceptance;
  its known limits are recorded in `documents/integration-handover-phase-4.md`
  section 6. This is not a whole-suite rerun or a new timing-budget measurement.
- `test_harness_system.py`: the real CTC Office, Track Controller SW, Track Model, Train
  Model and Train Controller processes and two stubs, with the starter programs loaded.
  It runs the Iteration 3 scenario: G1 dispatched from the yard to GLENBURY, placed at
  the yard exit, the blocks in order, stopped at GLENBURY with its doors open, no fault,
  and a clean shutdown; and a run with no programs loaded, in which nothing is
  released. About 8 s.

`--engineer-gains KP KI` on the Train Controller's process plays the engineer in these
tests, `--load-starters` on the Track Controller's loads the programs, and the CTC
Office's `--run-on-ready` and `--dispatch` play the dispatcher. A real window run passes none
of these unless `--auto-run`, `--load-starters` or `--dispatch` is given on the harness
command line; a headless run passes `--run-on-ready`. `AutoRunTest` in
`test_harness_window.py` checks the CTC Office's arguments for each kind of run. The
CTC window's own Run reaches the harness as `STATE`:
`CTC-Office/tests/test_module_process.py`,
`test_run_pause_and_speed_go_to_the_harness_at_once`.

Faults in the link have tests of their own. `test_harness_faults.py` drives the harness
with fake modules in the same process that send raw bytes: a number that overflows,
invalid Unicode, a line past the limit with valid lines after it, a reply with the
right ID and the wrong tick, and inputs that cannot be sent. `utils/tests/
test_protocol_faults.py` covers the same at the protocol, and `test_event_log_names.py`
the log's file names, six processes launched in the same second among them.
`test_harness_window_state.py` runs `window_state_probe.py` in its own GUI process: a
focused **Show window** button keeps focus while module statuses change, and a selected
event that rolls off the list clears the selection and closes the inspector.

The modules' own sides are tested in `CTC-Office/tests/test_module_process.py`,
`TrackCtrlSW/tests/test_module_process.py`, `TrackModel/tests/test_module_process.py`,
`TrainModel/tests/test_module_process.py` and `Train-Ctrl_HW/tests/test_harness_driven.py`.

After Phase 4 and the fault fixes, at `b65fd26`, offscreen, in a Linux cloud container
(Python 3.13, PySide6 6.11.2):

| Suite | Result |
|---|---|
| `python -m pytest -q common/harness/tests` | 150 passed, 495 subtests (48 s) |
| `python -m unittest discover -s common/harness/tests` | 150 OK |
| `python -m pytest -q utils/tests` | 82 passed, 37 subtests |
| `CTC-Office`: `python -m unittest discover tests` | 244 OK |
| `TrackCtrlSW`: `python -m unittest discover -s tests` | 194 OK |

After the work of 2026-10-21 (return to yard, the CTC Office on the harness's clock, the
starter's switches, and the overspeed test), offscreen, in the same container:

| Suite | Result |
|---|---|
| `python -m pytest -q common/harness/tests` | 150 passed, 5 skipped (`ReturnToYardTest`), 495 subtests (65 s) |
| `CTC-Office`: `python -m unittest discover tests` | 259 OK |
| `TrackCtrlSW`: `python -m unittest discover -s tests` | 213 OK |
| `Train-Ctrl_HW/tests` (the Train Controller under the harness) | 12 passed |

`test_harness_window.py` runs system mode for 8 s. Seven real modules take about 2 s to
be ready, and with 2 s about one run in three stopped before `ALL_READY`.

## Measuring the budget

```
python -m common.harness.measure --seconds 10 --payload-bytes 10000
```

This runs seven stubs at 10x and reports the round trip of each tick against the 10 ms
budget. `--system` runs the system as wired instead, with the Track Controller's
starter programs loaded, the CTC Office dispatching G1 to DORMONT (`--dispatch
G1:Green:73`), and the Train Controller playing the engineer, so the train is released
and runs for the whole measurement. The results are in section 5 of the design
document.

## Operator window

The window is titled **Track Overflow — Central Harness**. Its Qt application name
remains `TrackOverflow`, preserving the default log folder. It uses the shared
Daylight Ops QML theme, logo, `ModuleHeader` and `ScaledWindow`.

```sh
python track_overflow.py
python track_overflow.py --speedup --run-seconds 30 --log-dir /tmp/run-logs
python track_overflow.py --headless --speedup --run-seconds 30
python track_overflow.py --headless --stubs-only --run-seconds 30
```

The default is now the Phase 4 system: five real modules and two stubs. Add
`--load-starters` to commit the Track Controller's starter programs at launch, and
`--dispatch TRAIN:LINE:BLOCK` to have the CTC Office dispatch a train once the line is
ready.
`--stubs-only` restores seven stubs. `--headless` suppresses the harness window;
the real modules retain their own windows. For local verification without a display, set `QT_QPA_PLATFORM=offscreen`.

Both modes accept the same log, speed and duration options. The harness window has
no clock controls: the CTC Office owns Run, Pause and speed. It shows 24-hour simulated
time, tick, speed, running/paused state and the hold reason. Startup progress and
timeouts identify the modules still loading. Each process shows its PID, lifecycle
state and exit description. A late reply holds the clock and names the late module;
a disconnected or exited module holds the run as before.
The module list scrolls when timeout names take extra room. Tab reaches the list
even before any Show window action is enabled, with a visible focus ring and native
arrow-key scrolling. Focusing a Show window action keeps it in view. The module rows
update in place, so a focused **Show window** action keeps focus while any module's
status changes.

Events retain their simulation timestamp, tick, source, name and detail. Faults carry
a `FAULT` text label as well as the danger palette. The virtualized list keeps at most
3,000 events, while the CSV remains the complete record. Select an event or use the
arrow keys to read and copy its detail; **Read history** stops automatic following,
and **Follow latest** resumes it. When the list drops its oldest events at the cap, the
selection stays on its event; if the selected event is itself dropped, the selection is
cleared and the inspector closes. The log path is selectable at the bottom.

Run health shows the mean and maximum round trip over the last five real seconds,
plus the harness's cumulative slipped-tick count. No ticks in that interval displays
an em dash. Slipped ticks retain the pacer's existing meaning: simulated time fell
behind wall time; module tick numbers are never skipped.

### Operator decisions, confirmed by Kevin on 2026-10-20

- Closing this window asks for confirmation, initially focusing **Keep running**.
  Escape cancels. **End run** leaves the event loop, then uses the existing shutdown:
  send `QUIT`, wait up to five seconds, kill any remaining modules. Ctrl+C and
  `--run-seconds` use that same shutdown without a dialog.
- Every module has a **Show window** action, enabled while its link is ready or late.
  It sends the additive protocol-v1 `SHOW` message with the normal `id=0` and current
  tick, without requesting a reply or changing the simulation. `ModuleLink` emits
  `showRequested`, connected centrally to `utils.module_window`. GUI modules
  restore their main windows, preserving transient dialogs as hidden. Core-only
  stubs ignore it without importing GUI bindings. Closing module windows still
  only hides them. The Phase 1 module implementations need no edits.
- The selected module's outputs are read-only, opaque JSON, pretty-printed at most
  twice per second and truncated at 8,000 characters. No module-specific field is
  interpreted by the view. Switching modules hides the old text until the next
  inspector refresh, so outputs cannot be attributed to the wrong selection.
- The title is **Track Overflow — Central Harness**.

These decisions are proposed in the four `20261020-0927-harness-*.md` files under
`truth/_inbox/claude/quirky-fermi-sickg4/`. They await human promotion; this README
does not replace the authoritative `truth` branch.

### UI boundary and refresh budget

`HarnessConsole` talks only to `Harness`. Read-only core properties expose process
statuses, startup-timeout names, log path and hold reason; `show_window()` is the
sole per-module window action. The view never reaches into the supervisor or a
module implementation. Existing tick, timeout and shutdown rules are unchanged.

The console's 100 ms timer publishes a snapshot and appends one event batch.
Tick callbacks only collect timings; event callbacks only collect timestamped rows.
The pending queue and displayed list are both bounded to 3,000 rows. QML uses
`ListView` virtualization for the event history, rather than constructing thousands
of delegates. Output formatting uses incremental JSON encoding and stops at the
display limit. Blocking module shutdown happens after leaving the GUI event loop.

`window.resource_path()` is the single QML path resolver, using the repository root
from source and `sys._MEIPASS` in a frozen build. The bootstrap installs the shared
icon and scaling helper and destroys QML before its Python context objects.
Native controls inherit a Daylight Ops palette from the root window.

### Validation

```sh
QT_QPA_PLATFORM=offscreen python -m pytest common/harness/tests utils/tests
QT_QPA_PLATFORM=offscreen python -m unittest discover -s common/harness/tests
python -m common.harness.measure --seconds 10 --payload-bytes 10000
python -m common.harness.measure --window --seconds 10 --payload-bytes 10000
```

The window measurement selects the CTC Office in the output inspector, including
its twice-per-second formatting cost. With `--system --window`, it selects the real
Train Model instead and exercises the three real module processes with their windows.

The console tests run seven stubs with delayed readiness, a rejected tick, a reply
over one second late and a scripted nonzero exit. They verify intermediate paused
states, startup-timeout names, PID/exit reporting, event timestamps, fault labels,
buffer bounds, timing expiry, output throttling and source/frozen resource paths.
An isolated GUI-process test loads the real QML, exercises the same faults, renders
the window, checks warnings and cancels/confirms closing with the keyboard. Isolation
is necessary because other suites create a `QCoreApplication` at import time.

For a one-folder build, keep all generated output outside the repository:

```sh
PYINSTALLER_CONFIG_DIR=/tmp/harness-build/cache \
python -m PyInstaller --noconfirm --onedir --name track-overflow \
  --distpath /tmp/harness-build/dist --workpath /tmp/harness-build/work \
  --specpath /tmp/harness-build \
  --paths "$PWD/TrackModel" --paths "$PWD/TrainModel" --paths "$PWD/Train-Ctrl_HW" \
  --paths "$PWD/TrackCtrlSW" --paths "$PWD/CTC-Office" \
  --add-data "$PWD/common/harness/ui:common/harness/ui" \
  --add-data "$PWD/ui:ui" \
  --add-data "$PWD/TrackModel/ui:TrackModel/ui" \
  --add-data "$PWD/TrackModel/green_line.json:TrackModel" \
  --add-data "$PWD/TrackModel/red_line.json:TrackModel" \
  --add-data "$PWD/TrackCtrlSW/ui:TrackCtrlSW/ui" \
  --add-data "$PWD/CTC-Office/ctc_ui/ui:CTC-Office/ctc_ui/ui" \
  --add-data "$PWD/TrainModel/ui:TrainModel/ui" \
  --add-data "$PWD/TrainModel/pics:TrainModel/pics" \
  --add-data "$PWD/Train-Ctrl_HW/ui_parts:Train-Ctrl_HW/ui_parts" \
  --add-data "$PWD/Train-Ctrl_HW/train_ctrl:Train-Ctrl_HW/train_ctrl" \
  --add-data "$PWD/Train-Ctrl_HW/check.py:Train-Ctrl_HW" \
  --add-data "$PWD/utils/Track_Overlow_Logo.png:utils" track_overflow.py
/tmp/harness-build/dist/track-overflow/track-overflow --speedup \
  --run-seconds 3 --log-dir /tmp/harness-frozen-logs
```

Data source paths are absolute because PyInstaller resolves them relative to the
spec file, which lives outside the repository.
The Train Controller package is also bundled in its source hierarchy so its
existing relative resource paths keep working; its module implementation is
unchanged. Both real module packages are included in the import analysis.

Validation on 2026-10-20, `kevin-framework`, Ubuntu 26.04.1 LTS, Intel Core Ultra 5
325 (8 cores), Python 3.14.4, PySide6 6.11.2, after merging Phase 1:

| Suite | Result |
|---|---|
| Harness and utils, pytest, offscreen | 152 passed; 516 subtests passed |
| Harness, unittest, offscreen | 88 passed |
| Train Model | 776 passed, 13 skipped |
| Track Model | 266 passed |
| Track Controller SW | 186 passed; 12 subtests passed |
| Track Controller HW | 61 passed; 48,062 subtests passed; one known failure below |
| Train Controller SW | 24 passed |
| Train Controller HW | 10 harness tests passed; self-check: 0 QML warnings, 0 behavior problems |
| CTC Office | 208 passed; 251 subtests passed |

The retained Track Controller HW failure is
`tests/test_territory.py::SampleWaysides::test_samples_match_the_course_layout_file`:
the course layout has a `next_blocks` field absent from the sample waysides.
The CTC suite's existing real-time assertion failed once under competing load and
passed on subsequent complete runs; its code and tests were left untouched.
The final combined run exposed the utils stall test consistently: its scripted
300 ms and 1,000 ms waits could together overshoot the test's 50 ms real-time
allowance. That test now compares against measured active wall time, subtracting
the actual freeze, instead of assuming the script timers woke exactly on time.
Its burst/backlog checks and tolerance are unchanged, as are the other test
scripts and all production clock, timeout and shutdown code.

Post-merge ten-second runs at 10x with 10,000 filler bytes per stub reply. Desktop
runs use the actual Wayland window. The seven-stub run selects the CTC Office
inspector; the Phase 1 run selects the Train Model and opens both real module
windows with one running train. CPU is the harness process only:

| Front end | Ticks / due | Achieved | Mean (ms) | p95 (ms) | Max (ms) | CPU / core | Slipped |
|---|---|---|---|---|---|---|---|
| Seven stubs, headless | 1000 / 1000 | 10.00x | 2.11 | 2.47 | 4.48 | 23% | 0 |
| Seven stubs, window | 1001 / 1000 | 10.01x | 2.19 | 2.54 | 28.15 | 28% | 0 |
| Phase 1 system, window | 1007 / 1006 | 10.01x | 3.17 | 6.42 | 61.21 | 30% | 0 |

All runs had zero late replies. The system run lasted 10.06 s. The clock starts earning
work when all modules are ready, while measurement starts at the first STEP.
Startup work already owed can be caught up during measurement, and counting the
first completed tick can add one to the tally. `measure.py` reports the
ready-to-first-STEP delay explicitly. Occasional round trips
over the 10 ms interval were made up by subsequent ticks, without slipping time.

The PyInstaller 6.22.2 one-folder build is about 492 MiB including Qt/QML libraries.
It ran on the Wayland desktop at 10x for three seconds (289 ticks) and headless for
two seconds (174 ticks); both durations include startup. Both runs had seven clean
zero exits and no protocol errors, late replies or slips. QML and the logo loaded
from the bundle. No generated build files were added to the repository.
PyInstaller reported an unavailable optional asset-downloader plugin and missing
XCB libraries on this host. Wayland and offscreen worked; X11 and Windows builds
have not been validated.

Phase 2 adds the Track Model's package (`--paths`), its window and its two layout files
(D023: no Blue Line) to the recipe above. Built with it on 2026-10-20 in a Linux cloud
container (PyInstaller 6.22.2, about 483 MB), the executable ran headless at 10x for
12 s from outside the checkout with an empty `PYTHONPATH`: G1 released, 1,075 ticks, no
faults, seven exits with code 0. The Track Model process found its layouts and window
in the bundle.

Phase 3 adds the Track Controller SW's package (`--paths "$PWD/TrackCtrlSW"`) and its
window (`--add-data "$PWD/TrackCtrlSW/ui:TrackCtrlSW/ui"`). It reads its layouts from the
Track Model's files, which the recipe bundles already (`default_layout_dir()`). Built on
2026-10-20 in a Linux cloud container (PyInstaller 6.22.2, 483 MB). Alone, the bundled
`--module track-controller-sw` loaded the Green layout and its window, then ended with
code 2 because no harness was there. `track-overflow --headless --speedup --load-starters
--run-seconds 12`, run from outside the checkout with an empty `PYTHONPATH`, logged
`WAYSIDES_READY` and `TRAIN_ADDED` at tick 2, ran 974 ticks with no faults, and ended
with seven exits of code 0.

Phase 4 adds the CTC Office's package (`--paths "$PWD/CTC-Office"`) and its window
(`--add-data "$PWD/CTC-Office/ctc_ui/ui:CTC-Office/ctc_ui/ui"`). Its window imports the
shared `ui/` folder, and it reads its layouts from the Track Model's files; the recipe
bundles both already (`ctc.module_process.layout_files()`, found under `_MEIPASS` in a
build). `ctc.track_layout.LAYOUT_DIR`, found from its source file, is used only when no
layout is passed: by the standalone window (`ctc_ui/__main__.py`), the test UI and the
tests. The process always passes one, so nothing on a running path reads it. A schedule
for `--schedule` is a file the user names, not bundled. Built on 2026-10-20 in a Linux
cloud container (PyInstaller 6.22.2, 483 MB). Alone, the bundled `--module ctc-office`
loaded its window, then ended with code 2 because no harness was there.
`track-overflow --headless --speedup --load-starters --dispatch G1:Green:65
--run-seconds 15`, run from `/tmp` with an empty `PYTHONPATH`, logged `WAYSIDES_READY`
at tick 1 and `TRAIN_ADDED` (G1 on Green) at tick 3, ran 1,381 ticks with no faults,
and ended with seven exits of code 0. The same command in window mode, offscreen, for
8 s: the same events, no faults, seven exits of code 0. No engineer set G1's gains in
either run, so G1 stayed at the yard exit (D024).

### Integration design document handoff

The Phase 1 session owns `documents/system-integration-design.md`. Its next update
should record the window under §5.1; close the window portion of G-LIFE-4; record
startup progress and timeout names under G-LIFE-2; record the bundled QML/icon check
under G-RUN-2; note the harness confirmation and additive `SHOW`/module-side handler
under G-RUN-7; and record the harness's 24-hour clock display under G-CLK-8.
The paired window/headless measurements belong alongside the existing budget table.
Windows packaging/timing and USB timing still require their own measurements.

Done in v0.9 of the design document: section 5.1 records the window, and G-LIFE-2,
G-LIFE-4, G-RUN-2, G-RUN-7 and G-CLK-8 are updated; section 5.3 has the Phase 2
measurements, with and without the window. v0.10 adds section 5.4, with Phase 3's
measurements and frozen build, and v0.11 section 5.5, with Phase 4's.

### Phase 1 merge

Phase 1 (`2f9b4d7`, including `0f23d33`) is merged with the operator window.
The four shared-file conflicts retained both the real-module factory/edge lifecycle
and the window/headless frontend. Phase 1's module implementations, entry-point
registry and edge-mapping files were retained as received.

The default CLI-mode check now exercises the real modules and verifies a released
train and seven clean exits. The all-stub window and headless checks use
`--stubs-only`. A separate GUI-process test closes a module main window, delivers
`SHOW` through `ModuleLink`, and verifies that the main window returns while a
transient dialog stays hidden and stepping state is unchanged.

After the merge, Train Model has 776 passing tests and 13 skips; the Train Controller
has 10 passing harness-driven tests and its self-check still reports zero QML warnings
and zero behavior problems. Track Model (266), Track Controller SW (186), Train
Controller SW (24) and CTC Office (208) pass. Track Controller HW retains its one known
sample-wayside failure and 61 passing tests.
The combined harness/utils pytest command passes 152 tests and 516 subtests.
Unittest discovery of `common/harness/tests` passes all 88 tests.

The merged frozen build also passes on the Wayland desktop: default system/window
(267 ticks in 3 s), system/headless (254 ticks in 3 s), and seven-stub/window
(175 ticks in 2 s) modes. Each run ended
seven processes with code zero, without logged faults; both system runs logged G1
joining the Green Line. The same bundle contains all three UIs and Train Model
images, retaining the real module implementations unchanged.
It also ran successfully from `/tmp` with an empty `PYTHONPATH`, independently
of the source checkout.
