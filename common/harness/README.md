# Central harness

The harness is the one process that owns the simulation clock and drives every module
(D005, D017). It starts each module as a process of its own and sends every module, on
every tick, `dt`, the simulation time, and its inputs. It then waits for every reply
before the next tick. The design, and the R and G numbers cited in the code, are in
[`documents/system-integration-design.md`](../../documents/system-integration-design.md).

Phase 0 is built: the harness, its protocol, and a stub process standing in for each of
the seven modules. No real module is wired in yet.

## Run it

From the repository root, in the project's virtual environment:

```
python track_overflow.py                     # harness and seven stubs, 1x
python track_overflow.py --speedup           # 10x
python track_overflow.py --run-seconds 30    # stop by itself
python track_overflow.py --log-dir logs      # event log folder
```

No arguments open the operator window. Add `--headless` to echo every event to the
console, with a status line every 5 s. Ctrl+C ends the run in either mode. The CTC
Office's stub presses Run as soon as it is ready.

## Files

| File | What it holds |
|---|---|
| `../../track_overflow.py` | The one executable. No arguments start the harness; `--module <name>` starts one module. |
| `app.py` | Window/headless selection, status line and Ctrl+C handling. |
| `console.py`, `window.py`, `ui/` | Display snapshots, QML bootstrap and operator window. |
| `core.py` | `Harness`: the tick loop, timeouts, rejections, the CTC Office's clock controls, and the event log. |
| `pacer.py` | `TickPacer`: ticks the clock in real time, one tick in flight at a time. |
| `supervisor.py` | `ModuleSupervisor`: starts the module processes, accepts their links, and ends them. |
| `modules.py` | Module names, the edge map (`PRODUCERS`), and how a module process is started. |
| `stub_module.py` | The stand-in module process, with scripted faults. |
| `stub_edges.py` | Phase 0's input mapping: each module gets its producers' outputs whole. |
| `measure.py` | The real-time budget measurement (G-CLK-6). |
| `ctc_edges.py`, `track_model_edges.py` | Edge mappings written before the process model. `track_model_edges.py` maps through the superseded catalog (R11). |
| `../../utils/harness_protocol.py` | The wire protocol, shared by both ends. |
| `../../utils/module_link.py` | `ModuleLink`: a module's end of the link. |
| `../../utils/event_log.py` | The CSV event log. |

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

## Event log

One CSV file per run, written by the harness (R80). Its columns are `wall_time`,
`sim_time_s`, `time_of_day`, `tick`, `source`, `event`, `detail`. By default it is in
the user's local application data folder:

- Windows: `%LOCALAPPDATA%\TrackOverflow\logs`.
- Linux: `~/.local/share/TrackOverflow/logs`.

Every row is flushed as it is written. The events are listed in the docstring of
`core.py`.

## Wiring in a real module

A module joins the harness in place of its stub. Its process:

1. Runs under `track_overflow.py --module <name>`. `<name>` is the module's name in
   `modules.py`. Add a runner for it to `_MODULES` in `track_overflow.py`.
2. Creates a `ModuleLink(name, harness_name, step)` and calls `connect_to_harness()`.
   `step(tick, dt, sim_time_s, inputs)` steps the module once and returns its outputs.
   Raising `TickRejectedError` refuses the tick and leaves the module's state unchanged.
3. Calls `announce_ready()` once it can step. For the Track Controllers that comes after
   loading, which a person does in the window.
4. Quits on `quitRequested`, and on `harnessLost`. Hides its window instead of closing it,
   since only the harness ends a module. Ignores Ctrl+C, which the harness handles.
5. The CTC Office only: calls `push_state({"clock_paused": ..., "clock_speedup": ...})`
   when the dispatcher presses Run, Pause or the speed toggle while the clock is paused.

In the harness, the module's stub spec gives way to a `ModuleSpec(name, ("--module",
name))`, and `stub_inputs` gives way to mapping functions from its producers' types to
its own (D005).

## Tests

From the repository root:

```
python -m pytest common/harness/tests utils/tests
python -m unittest discover -s common/harness/tests
```

The end-to-end tests start the harness four times, with seven stub processes each. They
check ticks, time, the one-tick input latency, readiness, speed, pause and resume,
rejection, a duplicate reply, refused connections, a late reply, a crash, and stopping
while a module is still loading. They take about 5 s.

## Measuring the budget

```
python -m common.harness.measure --seconds 10 --payload-bytes 10000
```

This runs seven stubs at 10x and reports the round trip of each tick against the 10 ms
budget. The results are in section 5 of the design document.

## Operator window

The window is titled **Track Overflow — Central Harness**. Its Qt application name
remains `TrackOverflow`, preserving the default log folder. It uses the shared
Daylight Ops QML theme, logo, `ModuleHeader` and `ScaledWindow`.

```sh
python track_overflow.py
python track_overflow.py --speedup --run-seconds 30 --log-dir /tmp/run-logs
python track_overflow.py --headless --speedup --run-seconds 30
```

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
  `showRequested`; stubs have no handler and ignore it. A real module connects the
  signal to showing its hidden window. Closing module windows still only hides them.
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
its twice-per-second formatting cost.

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
  --add-data "$PWD/common/harness/ui:common/harness/ui" \
  --add-data "$PWD/ui:ui" \
  --add-data "$PWD/utils/Track_Overlow_Logo.png:utils" track_overflow.py
/tmp/harness-build/dist/track-overflow/track-overflow --speedup \
  --run-seconds 3 --log-dir /tmp/harness-frozen-logs
```

Data source paths are absolute because PyInstaller resolves them relative to the
spec file, which lives outside the repository.

Validation on 2026-10-20, `kevin-framework`, Ubuntu 26.04.1 LTS, Intel Core Ultra 5
325 (8 cores), Python 3.14.4, PySide6 6.11.2:

| Suite | Result |
|---|---|
| Harness and utils, pytest, offscreen | 116 passed; 515 subtests passed |
| Harness, unittest, offscreen | 53 passed |
| Train Model | 763 passed, 13 skipped |
| Track Model | 266 passed |
| Track Controller SW | 186 passed; 12 subtests passed |
| Track Controller HW | 61 passed; 48,062 subtests passed; one known failure below |
| Train Controller SW | 24 passed |
| Train Controller HW `main.py --check` | 0 QML warnings, 0 behavior problems |
| CTC Office | 208 passed; 251 subtests passed |

The retained Track Controller HW failure is
`tests/test_territory.py::SampleWaysides::test_samples_match_the_course_layout_file`:
the course layout has a `next_blocks` field absent from the sample waysides.
Unchanged real-time assertions in the utils and CTC suites each failed once under
competing load, then passed on subsequent complete runs. Their implementation and
tests were left untouched.

Ten-second runs at 10x with 10,000 filler bytes per reply, seven stubs. The desktop
runs use the actual Wayland window with the CTC Office inspector active:

| Front end | Ticks / due | Achieved | Mean (ms) | p95 (ms) | Max (ms) | CPU / core | Slipped |
|---|---|---|---|---|---|---|---|
| Headless | 1000 / 1000 | 10.00x | 2.20 | 2.94 | 7.32 | 23% | 0 |
| Desktop window | 1008 / 1000 | 10.08x | 2.29 | 2.99 | 5.84 | 38% | 0 |
| Desktop window, repeat | 1008 / 1002 | 10.06x | 2.67 | 6.53 | 19.33 | 34% | 0 |

All runs had zero late replies. The repeat lasted 10.02 s. The clock starts earning
work when all modules are ready, while measurement starts at the first STEP.
The desktop repeat's first STEP was 73.02 ms after readiness, so startup work
already owed was caught up during measurement; this explains the apparent speed
slightly over 10x. `measure.py` reports that delay explicitly. Occasional round trips
over the 10 ms interval were made up by subsequent ticks, without slipping time.

The PyInstaller 6.22.2 one-folder build is about 492 MiB including Qt/QML libraries.
It ran on the Wayland desktop at 10x for three seconds (289 ticks) and headless for
two seconds (174 ticks); both durations include startup. Both runs had seven clean
zero exits and no protocol errors, late replies or slips. QML and the logo loaded
from the bundle. No generated build files were added to the repository.
PyInstaller reported an unavailable optional asset-downloader plugin and missing
XCB libraries on this host. Wayland and offscreen worked; X11 and Windows builds
have not been validated.

### Integration design document handoff

The Phase 1 session owns `documents/system-integration-design.md`. Its next update
should record the window under §5.1; close the window portion of G-LIFE-4; record
startup progress and timeout names under G-LIFE-2; record the bundled QML/icon check
under G-RUN-2; note the harness confirmation and additive `SHOW`/module-side handler
under G-RUN-7; and record the harness's 24-hour clock display under G-CLK-8.
The paired window/headless measurements belong alongside the existing budget table.
Windows packaging and real-module/USB timing still require their own measurements.
