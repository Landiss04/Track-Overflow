# Central harness

The harness is the one process that owns the simulation clock and drives every module
(D005, D017). It starts each module as a process of its own and sends every module, on
every tick, `dt`, the simulation time, and its inputs. It then waits for every reply
before the next tick. The design, and the R and G numbers cited in the code, are in
[`documents/system-integration-design.md`](../../documents/system-integration-design.md).

Phase 0 built the harness, its protocol, and a stub process standing in for each of the
seven modules. Phase 1 wires in the first two real modules: the Train Model and the Train
Controller SW, with one Green Line train on a fixed track feed. The other five modules are
still stubs.

## Run it

From the repository root, in the project's virtual environment:

```
python track_overflow.py                     # Phase 1 system, 1x
python track_overflow.py --speedup           # 10x
python track_overflow.py --run-seconds 30    # stop by itself
python track_overflow.py --log-dir logs      # event log folder
python track_overflow.py --stubs-only        # a stub for every module, as in Phase 0
```

Ctrl+C stops the harness, which tells every module to quit. Every logged event is echoed
to the console, with a status line every 5 s.

What a run does:

1. The harness starts seven module processes: the Train Model and the Train Controller SW
   as themselves, each in its window, and stubs for the rest.
2. The CTC Office's stub presses Run as soon as it is ready, since its window is not wired
   in yet, and releases train G1 onto the Green Line on the first tick.
3. G1 joins the Train Model, and a tick later the Train Controller.
4. G1 waits in the yard exit block until an engineer sets its gains in the Train
   Controller's console (D024).
5. Then it runs the fixed track feed `track_feed.GREEN_STATION_STOP`. It goes out of
   block 63 at 45 km/h and stops at GLENBURY (block 65, platform on the right). The
   right-hand door opens, and after about 50 s the train goes on into block 66.

A module window that is closed only hides; the process ends when the harness does.

## Files

| File | What it holds |
|---|---|
| `../../track_overflow.py` | The one executable. No arguments start the harness; `--module <name>` starts one module. |
| `app.py` | The harness's command line, status line and Ctrl+C handling. |
| `core.py` | `Harness`: the tick loop, timeouts, rejections, the CTC Office's clock controls, and the event log. |
| `pacer.py` | `TickPacer`: ticks the clock in real time, one tick in flight at a time. |
| `supervisor.py` | `ModuleSupervisor`: starts the module processes, accepts their links, and ends them. |
| `modules.py` | Module names, the edge map (`PRODUCERS`), which modules are wired in (`WIRED_MODULES`), and how a module process is started. |
| `edges.py` | `SystemEdges`: builds every module's inputs, with real edges into the wired modules. |
| `roster.py` | The trains in service, from the CTC Office's `new_trains` and `retired_trains` (D022). |
| `train_edges.py` | The edges between the Train Model and the Train Controller. |
| `track_feed.py` | The fixed track feed that stands in for the Track Model until Phase 2. |
| `stub_module.py` | The stand-in module process, with scripted faults. The CTC Office's stub also releases and retires trains on cue. |
| `stub_edges.py` | Inputs for a stub: its producers' outputs whole. |
| `measure.py` | The real-time budget measurement (G-CLK-6). |
| `ctc_edges.py`, `track_model_edges.py` | Edge mappings written before the process model. `track_model_edges.py` maps through the superseded catalog (R11). |
| `../../utils/harness_protocol.py` | The wire protocol, shared by both ends. |
| `../../utils/module_link.py` | `ModuleLink`: a module's end of the link. |
| `../../utils/module_window.py` | Makes a module process's windows hide instead of closing. |
| `../../utils/event_log.py` | The CSV event log. |
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
| module → harness | `READY` | `module`, `protocol` (the version, now 1) |
| module → harness | `OUTPUTS` | `outputs`; `id` and `tick` of the `STEP` it answers |
| module → harness | `REJECTED` | `reason`; `id` and `tick` of the `STEP` it answers |
| module → harness | `STATE` | `state`, a change made between ticks |

The harness listens on a server named `track-overflow-<pid>-<random>`, open only to the
same user, and passes the name to each module as `--harness <name>`. A connection's
first message must be `READY` naming an expected module that is not yet connected.
Anything else is refused and logged.

## Trains and edges (Phase 1)

The edges (`edges.py`) build each module's inputs from the outputs every module gave on
the tick before. They see each tick's new outputs once, when the tick is over
(`Edges.tick_completed`), and that is where the CTC Office's train events take effect,
exactly once.

- **Roster.** A train in the CTC Office's `new_trains` joins on the next tick: in the
  Train Model at once, and in its line's Train Controller (Green: SW, Red: HW, D021) a
  tick later. The Train Controller needs the Train Model's report of the train on every
  tick, and there is none before the first. A train in `retired_trains` leaves both. The
  harness logs `TRAIN_ADDED` and `TRAIN_REMOVED`, and refuses a malformed ID or a line
  other than Green or Red.
- **Train Controller → Train Model.** Each train's commands map onto the Train Model's
  `controller` input (`train_edges.py`). Until a train's first commands arrive, the
  Train Model gets `INERT_COMMANDS`: no power, the service brake on, doors shut.
- **Train Model → Train Controller.** Each train's `controller` outputs map onto the
  Train Controller's inputs. The light ahead comes from the track feed, with
  `SUPER_GREEN` spelled the Train Controller's way.
- **Track.** `track_feed.FixedTrackFeed` gives each train its track by time since it
  entered service: the block, its track info, the track signal, any beacon, and the
  light ahead. Polarity flips at every block change. A script's authority must count
  down to a stop: a drop from 2 or more blocks straight to none reads as a signal pickup
  failure in the Train Controller.
- **Rejections.** The Train Model steps each train on its own. A train whose inputs it
  refuses misses the tick, and the harness logs `TICK_REJECTED` with the train's ID.

Every train's inputs and outputs travel under `trains`, keyed by train ID. Each module
names its own fields: the Train Model as in `train_model/interface.py`, the Train
Controller as its `read_inputs` keys and `TrainModelCommands` fields.

A command comes back in a report two ticks after it is sent: the Train Model acts on it
on the next tick, and its report reaches the Train Controller the tick after. The Train
Controller allows for that (`echo_ticks`). Otherwise the report of its own emergency
brake would read as a passenger pull and undo the driver's release.

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
Controller did in Phase 1 (their `module_process.py` files are worked examples). Its
process:

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

Phase 1 adds three layers of tests:

- `test_harness_edges.py`: the roster, the edges and the track feed, as plain objects.
- `test_harness_train_loop.py`: the two module processes' step functions, in one
  process, wired through `SystemEdges` with the harness's one-tick delay. It covers the
  station stop behind the door interlock, the driver's release of the emergency brake,
  and a passenger pull and its release. It takes well under a second.
- `test_harness_phase1.py`: the real Train Model and Train Controller processes and five
  stubs. It covers the release of G1, the station stop, the door interlock and a clean
  shutdown, in about 7 s.

`--engineer-gains KP KI` on the Train Controller's process plays the engineer in these
tests. A real run never passes it.

The modules' own sides are tested in `TrainModel/tests/test_module_process.py` and
`Train-Ctrl_HW/tests/test_harness_driven.py`.

## Measuring the budget

```
python -m common.harness.measure --seconds 10 --payload-bytes 10000
```

This runs seven stubs at 10x and reports the round trip of each tick against the 10 ms
budget. The results are in section 5 of the design document.
