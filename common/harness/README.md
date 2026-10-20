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

Ctrl+C stops the harness, which tells every module to quit. Every logged event is echoed
to the console, with a status line every 5 s. The CTC Office's stub presses Run as soon
as it is ready, since there is no window yet to press it in.

## Files

| File | What it holds |
|---|---|
| `../../track_overflow.py` | The one executable. No arguments start the harness; `--module <name>` starts one module. |
| `app.py` | The harness's command line, status line and Ctrl+C handling. |
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
