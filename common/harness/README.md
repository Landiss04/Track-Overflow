# Central harness

The harness is the one process that owns the simulation clock and drives every module
(D005, D017). It starts each module as a process of its own and sends every module, on
every tick, `dt`, the simulation time, and its inputs. It then waits for every reply
before the next tick. The design, and the R and G numbers cited in the code, are in
[`documents/system-integration-design.md`](../../documents/system-integration-design.md).

Phase 0 built the harness, its protocol, and a stub process standing in for each of the
seven modules. Phase 1 wired in the Train Model and the Train Controller SW, and Phase 2
the Track Model. One Green Line train runs on the commands of a scripted wayside that
stands in for the Track Controller. The other four modules are still stubs.

## Run it

From the repository root, in the project's virtual environment:

```
python track_overflow.py                     # Phase 2 system, 1x
python track_overflow.py --speedup           # 10x
python track_overflow.py --run-seconds 30    # stop by itself
python track_overflow.py --log-dir logs      # event log folder
python track_overflow.py --stubs-only        # a stub for every module, as in Phase 0
```

No arguments open the operator window. Add `--headless` to echo every event to the
console, with a status line every 5 s. Ctrl+C ends the run in either mode. The CTC
Office's stub presses Run as soon as it is ready.

What a run does:

1. The harness starts seven module processes: the Track Model, the Train Model and the
   Train Controller SW as themselves, each in its window, and stubs for the rest.
2. The CTC Office's stub presses Run as soon as it is ready, since its window is not wired
   in yet, and releases train G1 onto the Green Line on the first tick.
3. The Track Model places G1 on the yard exit block (63) on the next tick. G1 joins the
   Train Model a tick later, and the Train Controller a tick after that.
4. G1 waits there until an engineer sets its gains in the Train Controller's console
   (D024).
5. Then the scripted wayside `wayside_script.GREEN_YARD_TO_DORMONT` takes it out of block
   63 at 45 km/h to a stop at GLENBURY (block 65, platform on the right). The right-hand
   doors open at a stand. About 60 s after the train entered the block, the wayside gives
   it authority again: the doors close, and it goes on at 40 km/h to DORMONT (block 73),
   where it stops and opens its doors at the end of its route.

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
| `track_edges.py` | The edges between the Track Model and the trains, and the Track Model's block names. |
| `wayside_script.py` | The scripted wayside that stands in for the Track Controller until Phase 3. |
| `stub_module.py` | The stand-in module process, with scripted faults. The CTC Office's stub also releases and retires trains on cue. |
| `stub_edges.py` | Inputs for a stub: its producers' outputs whole. |
| `measure.py` | The real-time budget measurement (G-CLK-6). |
| `ctc_edges.py`, `track_model_edges.py` | Edge mappings written before the process model. `track_model_edges.py` maps through the superseded catalog (R11); the running system uses `track_edges.py` instead. |
| `../../utils/harness_protocol.py` | The wire protocol, shared by both ends. |
| `../../utils/module_link.py` | `ModuleLink`: a module's end of the link. |
| `../../utils/module_window.py` | Makes a module process's windows hide instead of closing. |
| `../../utils/event_log.py` | The CSV event log. |
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
| A module ends or drops its link | It logs the exit and holds the clock for the rest of the run. Modules are never restarted mid-run. |
| A reply comes twice, or for no request | It logs `UNEXPECTED_REPLY` and ignores it. Every request is answered once. |
| The run falls behind real time | Owed ticks run back to back, up to 100. Past that the backlog is dropped and logged as `TIME_SLIPPED`. No module misses a tick; simulation time runs slower than real time. |
| A pause with ticks owed | At most the next tick stays owed, so the run resumes without a burst. |

The clock runs only while every module is ready, none is late or down, and the CTC
Office asks it to run. Its `clock_paused` and `clock_speedup` are read from its outputs,
and while the clock is paused, from its `STATE` messages.

## Protocol

Newline-delimited JSON, one object per line, over a Qt local socket: a named pipe on
Windows and a socket file elsewhere. Every message carries `op`, an integer request `id`
and the `tick`. The full description is the docstring of `utils/harness_protocol.py`.

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
- **The wayside.** `wayside_script.ScriptedWayside` stands in for the Track Controller,
  and for the CTC Office's suggestions, until Phases 3 and 4. From the Track Model's
  occupancy alone, it commands per block the speed and authority of a scripted route:
  authority to the next stop not yet served, or to the destination, and the next block
  preloaded with one block less (R49), so a train never enters a block that reads zero.
  A stop holds the train for 60 s after it enters the stop's block, as the CTC Office's
  schedule would: braking, then the 45 s dwell, which the Train Controller enforces
  (D007). The wayside steps on the
  Track Model's outputs of the tick before, so its commands reach the Track Model a tick
  later, as a module's would. It serves one train, once.
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
`sim_time_s`, `time_of_day`, `tick`, `source`, `event`, `detail`. By default it is in
the user's local application data folder:

- Windows: `%LOCALAPPDATA%\TrackOverflow\logs`.
- Linux: `~/.local/share/TrackOverflow/logs`.

Every row is flushed as it is written. The events are listed in the docstring of
`core.py`.

## Wiring in a real module

A module joins the harness in place of its stub, as the Train Model and the Train
Controller did in Phase 1 and the Track Model in Phase 2 (their `module_process.py` files
are worked examples). Its process:

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
   when the dispatcher presses Run, Pause or the speed toggle while the clock is paused.

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

Phases 1 and 2 add three layers of tests:

- `test_harness_edges.py`: the roster, the edges, the Track Model's block names and the
  scripted wayside, as plain objects.
- `test_harness_train_loop.py`: the three module processes' step functions, in one
  process, wired through `SystemEdges` with the harness's one-tick delay, every message
  through JSON. It runs the whole default route: the order the modules take the train,
  block by block, the GLENBURY stop behind the door interlock, boarding, the light on
  block 64, and the stop at DORMONT; and the driver's release of the emergency brake,
  with and without a passenger pull. It takes a few seconds.
- `test_harness_system.py`: the real Track Model, Train Model and Train Controller
  processes and four stubs. It covers the order the modules take the train, its
  placement at the yard exit, the blocks in order, a stop at GLENBURY behind the door
  interlock, and a clean shutdown, in about 10 s.

`--engineer-gains KP KI` on the Train Controller's process plays the engineer in these
tests. A real run never passes it.

The modules' own sides are tested in `TrackModel/tests/test_module_process.py`,
`TrainModel/tests/test_module_process.py` and `Train-Ctrl_HW/tests/test_harness_driven.py`.

## Measuring the budget

```
python -m common.harness.measure --seconds 10 --payload-bytes 10000
```

This runs seven stubs at 10x and reports the round trip of each tick against the 10 ms
budget. `--system` runs the system as wired instead, with the Train Controller playing
the engineer so the train moves. The results are in section 5 of the design document.

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

The default is now the Phase 2 system: three real modules and four stubs.
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
arrow-key scrolling. Focusing a Show window action keeps it in view.

Events retain their simulation timestamp, tick, source, name and detail. Faults carry
a `FAULT` text label as well as the danger palette. The virtualized list keeps at most
3,000 events, while the CSV remains the complete record. Select an event or use the
arrow keys to read and copy its detail; **Read history** stops automatic following,
and **Follow latest** resumes it. The log path is selectable at the bottom.

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
  --add-data "$PWD/common/harness/ui:common/harness/ui" \
  --add-data "$PWD/ui:ui" \
  --add-data "$PWD/TrackModel/ui:TrackModel/ui" \
  --add-data "$PWD/TrackModel/green_line.json:TrackModel" \
  --add-data "$PWD/TrackModel/red_line.json:TrackModel" \
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
measurements, with and without the window.

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
