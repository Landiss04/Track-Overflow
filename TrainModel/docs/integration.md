# Removing the test UI and wiring the Train Model into the system

How to take the Train Model from its standalone test setup to the integrated
system, per D010: the test UI is removed and the module is wired in with no
change to the module's physics or its interface.

Read [module-interface.md](module-interface.md) first; this guide assumes it.

The system runs one process per module. The central harness spawns the Train
Model as its own process and drives it over the harness protocol (D005/D008; [system integration design](../../documents/system-integration-design.md) §4.5).

The central harness exists (`common/harness/`, Phase 1 of the design). It
starts the Train Model with `track_overflow.py --module train-model`, which
runs `train_model/module_process.py`: the fleet, the window, and the harness's
steps. Sections 3 to 5 say what that process and the harness each do.

## 1. What is module and what is test scaffolding

| Keep: the module | Remove: test scaffolding |
|---|---|
| `train_model/interface.py`: boundary types | `test_ui.py`: test UI entry point |
| `train_model/model.py`: physics | `train_model/harness.py`: test UI state, stand-in producers, clock driving |
| `train_model/state.py`: module wrapper the window binds to | `train_model/link.py`: socket link, wire format, `TestLinkServer` |
| `train_model/app.py`: window bootstrap | `ui/TestMain.qml`, `ui/TestView.qml`: test UI window |
| `train_model/module_process.py`: the process the harness starts | |
| `train_model/wire.py`: the boundary types as JSON, for the harness protocol | |
| | `train_model/track_stub.py`: stand-in Track Model; Blue Line by default, Red or Green by flag |
| | `train_model/speed_limiter.py`: stand-in Train Controller speed limiter |
| `ui/Main.qml`, `ui/MainView.qml`: Train Model window | |
| `main.py`: standalone window entry point; harness uses `module_process.py` | |

Shared code outside `TrainModel/` stays: `utils/system_clock.py` and
`utils/clock_driver.py` (the system clock), `ui/` (theme, components,
`aspect_lock.py`).

Today the two processes talk like this:

```
test_ui.py process                      main.py process
┌──────────────────────────┐            ┌──────────────────────────────┐
│ TestView.qml             │            │ Main.qml / MainView.qml      │
│ TestHarnessState         │  socket    │ TrainModelState ── TrainModel│
│  ├ SystemClock + driver  │ ─────────► │  ▲                           │
│  └ SocketLink ───────────┼─ JSON ───► │ TestLinkServer               │
└──────────────────────────┘            └──────────────────────────────┘
```

After integration, one process per module:

```
harness process                           Train Model process (module_process.py)
┌────────────────────────────────┐        ┌───────────────────────────────┐
│ SystemClock ─tick─► harness    │  step  │ TrainModelFleet               │
│ edge mappings (D005)           │ ─────► │  └ TrainModelState            │
│                                │ ◄───── │ Main.qml / MainView.qml       │
└────────────────────────────────┘ outputs└───────────────────────────────┘
   ▲ outputs          │ inputs
   Train Controller and Track Model processes
```

## 2. Removing the test UI

This is a development removal guide, not a product use case. The standalone
utility still exists in the inspected repo; no files are removed by this
documentation task. Run the relevant local checks after a future removal.

### 2.1 Delete the scaffolding files

```
TrainModel/test_ui.py
TrainModel/train_model/harness.py
TrainModel/train_model/link.py
TrainModel/train_model/speed_limiter.py
TrainModel/train_model/track_stub.py
TrainModel/ui/TestMain.qml
TrainModel/ui/TestView.qml
```

### 2.2 Delete the tests that exist only for the test UI

These import `harness`, `link`, the stand-ins or the test UI QML:

```
TrainModel/tests/test_harness.py
TrainModel/tests/test_harness_clock.py
TrainModel/tests/test_harness_extended.py
TrainModel/tests/test_input_submission.py
TrainModel/tests/test_link.py
TrainModel/tests/test_link_malformed.py
TrainModel/tests/test_speed_limiter.py
TrainModel/tests/test_station_dwell.py
TrainModel/tests/test_track_stub.py
TrainModel/tests/test_ui_sync.py
TrainModel/tests/qml_sync_check.py
TrainModel/tests/input_list_check.py
TrainModel/tests/announcement_check.py
TrainModel/tests/clock_ui_check.py
TrainModel/tests/drive_test_ui.py
TrainModel/tests/ebrake_button_check.py
TrainModel/tests/readout_sign_check.py
```

Three of these also check the Train Model window: `ebrake_button_check.py`
its emergency brake button, `announcement_check.py` its announcement popup
and failure buttons, and `readout_sign_check.py` that no readout shows a
negative zero. If that coverage matters after integration, rewrite them to
drive `TrainModelState` directly instead of through the test UI.

These stay and need no change, because they use only the module:
`test_physics.py`, `test_physics_extended.py`, `test_integration.py`,
`test_contract.py`, `test_stub.py`, `test_elapsed_clock.py`,
`test_model_invariants.py`.

### 2.3 Unhook the link from `main.py`

`main.py` starts a `TestLinkServer` for its one test train. Remove the
import and the lines that create and start it, so it only builds the
window around a fleet:

```python
from train_model.app import run_window
from train_model.fleet import TrainModelFleet


def main() -> int:
    """Run the Train Model window on its own."""
    return run_window(
        "Train Model", "Main.qml",
        lambda: {"fleet": TrainModelFleet()},
    )
```

`main.py` stays as the standalone entry point. The harness does not run it:
it runs `train_model/module_process.py` (section 5).

### 2.4 Test-only hooks left in the module (optional cleanup)

These are not part of the integration interface (D010). They do no harm if
left, but nothing in the system should call them:

| Hook | Where | Used by |
|---|---|---|
| `step(..., override_passenger_brake=...)` | `state.py` | link |
| `TrainModelState.reset()` | `state.py` | link |
| `TrainModelState.command_values()` | `state.py` | deleted tests only |
| `TrainModelState.releaseEmergencyBrake()` | `state.py` | deleted tests only; a no-op slot |
| `TrainModelState.clear_passenger_brake_for_test()` | `state.py` | link |
| `TrainModel.clear_passenger_brake_for_test()` | `model.py`, `interface.py` protocol | state, `test_contract.py`, `test_physics_extended.py`, `test_model_invariants.py` |

Removing the last one also means updating `test_contract.py` and the
passenger-brake tests in `test_physics_extended.py` and
`test_model_invariants.py`. The normal controller release path below already exists; retain the hook
while local developer utilities still use it.

### Passenger brake release

A passenger pull latches. The **Train Controller** releases it (D011): the
pull stays latched until the controller's `emergency_brake` goes from true to
false (Kevin Schillinger 2026-10-28). The controller takes a pull up as its
own emergency brake, so the driver's release clears both. A pull made after
the controller's last true is kept. There is no separate release command; the
one-shot `passenger_brake_release` (2026-10-20) is withdrawn. The window has
no release action. Once the test UI is gone, nothing calls the test-only
override.

### 2.5 Update the README

Remove the test UI parts of `TrainModel/README.md`: the two-process
description, `python test_ui.py` and its smoke test, `TRAIN_MODEL_LINK`, the
test UI rows of the layout table, and the "Passenger brake override" section.

## 3. What the system must do for each Train Model

The Train Model is one process, one of those the central harness spawns (one
process per module, D005). Inside it, every train is one `TrainModelState` in
one `TrainModelFleet` (`train_model/fleet.py`); there is no process per train.
The fleet lives in the Train Model process, and `module_process.py` does the
following on each of the harness's steps:

1. **Adds** a train with `fleet.add(train_id, line)` the first time the
   harness names it, which is the tick after the CTC Office releases it from
   the yard, and calls `fleet.remove(train_id)` once the harness stops naming
   it, after the CTC Office retires it (D022). Train IDs are the CTC Office's, used
   unchanged as opaque strings. Each train gets its own seed, derived from its ID, so
   trains draw different disembark counts and a run repeats; pass a
   `TrainConfig` to choose the seed instead. Adding an ID twice raises
   `DuplicateTrainError`, and an unknown ID raises `UnknownTrainError`.
2. **Steps** the fleet once per shared-clock tick with
   individual `fleet.get(train_id).step(dt, inputs)` calls. Never vary dt;
   speed and pause change only tick frequency (D006). The atomic `step_all`
   helper is separate from integrated per-train rejection.
3. **Builds inputs** each tick, one `TrainModelInputs` per train, keyed by
   train ID, from the latest Train Controller commands and Track Model data,
   through the edge mappings (section 4).
4. **Routes outputs** each tick: collect each train’s outputs by ID. Send `outputs.controller` to that train's Train Controller and
   `outputs.track` to the Track Model.
5. **Handles rejection.** Only the train whose input is invalid misses the
   tick; the other trains step, and the rejection names that train
   (`modules/train-model.md`). `step_all` is all or nothing, so the process
   does not use it: it checks each train with `validate_inputs` and steps it
   with `fleet.get(train_id).step(...)`. A rejected train's reply holds its
   unchanged outputs, and the harness logs the rejection.
6. **Runs on the Qt thread.** The fleet and every `TrainModelState` are
   `QObject`s whose signals drive the window; call them from the thread
   that owns them.

A 20-train `step_all` takes about 1.5 ms on a development laptop, well
inside the 10 ms between ticks at 10x (`tests/test_fleet.py`).

The physics never reads another module or the clock and never calls the
harness. Its process adapter receives dt and simulation time through the
harness `STEP` message; clock reconciliation is described below.

## 4. Edge mappings

The harness maps each producer's types straight to the consumer's, on their
JSON form (`train_model/wire.py`). The catalog in `common/interfaces.py` is
superseded (D008). The Train Controller edges are in
`common/harness/train_edges.py`, and the Track Model edges, since Phase 2, in
`common/harness/track_edges.py`. A train joins the Train Model once the Track
Model feeds it, and its block arrives by number (`"63"`); the Train Model knows
the train's line. The Train Model's side of each edge:

### Train Controller → Train Model (`ControllerCommands`)

| Module field | From | Note |
|---|---|---|
| `power_cmd_w` | power command | W, ≥ 0; a negative value is rejected. |
| `service_brake`, `emergency_brake` | brake commands | |
| `interior_lights`, `exterior_lights` | light command | |
| `door_left_open`, `door_right_open` | door command | The model enforces no interlock; the Train Controller holds it (truth `door-command`). |
| `temp_setpoint_c` | temperature setpoint | °C. |
| `announcement` | announcement | `""` if none. |

### Track Model → Train Model (`TrackInputs`)

| Module field | From | Note |
|---|---|---|
| `track_info.block_id` | block the train occupies | |
| `track_info.grade_deg` | block grade | Degrees; the layout loader converts from percent. |
| `track_info.elevation_m` | block elevation | |
| `track_info.speed_limit_mps` | block speed limit | m/s. |
| `track_info.polarity` | track-circuit polarity | Must flip on each block entry; that flip is the block change. |
| `track_info.station_name` | the block's station, else `None` | Display metadata; no Train Model station gate. `track-info` has six fields. |
| `track_signal.commanded_speed_mps`, `authority_blocks` | track circuit | Authority is an `int` count of blocks, ≥ 0. |
| `beacon` | beacon under the train this tick, else `None` | Preserve typed/named fields; enforce the complete 128-character canonical payload. Controller retains prior data when needed. |
| `passengers_boarded` | boarding count | Track Model sends only at stations, once per event, ≤ last `passenger_capacity`. Train Model checks rest, doors, count and capacity without a station gate. Otherwise 0. |

### Train Model → Train Controller (`ControllerOutputs`)

Actual speed, Brake State, Door State, Light State, cabin temperature,
and the passed-through commanded speed, authority, speed limit and beacon.
Failure status is not sent. See [module-interface.md](module-interface.md#5-outputs-trainmodeloutputs).

### Train Model → Track Model (`TrackOutputs`)

Block ID, signed front-of-train offset in m, actual speed, block-change flag, passenger
capacity. The Track Model uses position for occupancy and capacity for the
next boarding count.

The catalog's setter-shaped `ITrainModel` (`common/interfaces.py`) is
superseded with the catalog. The module does not implement or import it, and
nothing needs that shape.

### On each tick

The harness builds the Train Model's inputs in `common/harness/edges.py`:
every train in service, keyed by train ID under `trains`, with its line, the
Train Controller's last commands for it mapped onto `controller`, and its
`track` inputs. A train the Train Controller has not commanded yet gets
inert commands (no power, service brake on). The process steps each train
and replies with each train's outputs under `trains`, and a `rejected`
object naming any train it refused. The harness hands each train's
`controller` outputs to that train's Train Controller on the next tick.

Every module steps on the same tick, each on the other modules' outputs from
the tick before: a module sees its inputs only on the rising clock edge
(D017). The order of steps therefore does not matter. A command therefore
comes back in a report two ticks after it is sent, which the Train
Controller allows for.

### Integrated time reconciliation and drift

Accepted design: `sim_time_s` is the unwrapped end-of-tick timestamp. On a train’s
first roster appearance set `epoch = sim_time_s - dt` once. On harness tick
numbers divisible by 15, after accepted stepping, compare
`epoch + accepted_model_elapsed_s` with supplied `sim_time_s` using an absolute
`1e-6 s` tolerance. Include rejected trains with their retained elapsed time.
The window displays harness time independently; never reset model elapsed time
or realign epochs to conceal missing steps or other discrepancies.

The inspected working tree implements this in `module_process.py` (`_epochs`
and the `tick % 15` check), `fleet.py` (time fan-out), and `state.py` (display
and absolute drift tolerance). `Main.qml` displays selected-train drift diagnostics.
These concurrent edits were inspected, not implemented or tested by this task.
The older standalone utility check every 30 ticks remains a separate development
path, not an integrated check.

## 5. Showing the Train Model window

`train_model/app.py`'s `run_window` creates its own `QGuiApplication` and runs
the event loop. That is what the system needs: the Train Model runs as its own
process, so `module_process.py` calls `run_window` with the fleet the harness
drives. Closing the window hides it; only the harness ends the process
(`utils/module_window.py`, D005).

`Main.qml` and `MainView.qml` read only `fleet` and `theme`, and contain no
reference to the test UI. One window shows every train: a train selector
right after the header's status badges lists the fleet, and the window
binds to `fleet.current`, the selected train. The first train added is
selected; when the selected train is removed, the next one in the roster
takes over. With no trains, the selector reads "No trains" and the window
shows an idle train that is never stepped. The header shows *Running* while
steps arrive for the selected train and *Paused* when they stop, whoever
sends them. Failure injection and the passenger emergency brake button call
the selected `TrainModelState` directly, so they act on that train only and
keep working with no test UI. Identity and line already come from the fleet
roster. The intended window retains next-station/platform information and removes
arrival time. The inspected QML now shows next station/platform without arrival.

## 6. Checks after removal

```bash
cd TrainModel
rg -n "harness|train_model.link|TestMain|TestView|test_ui" \
    -g "*.py" -g "*.qml" .        # comments only, no imports
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
QT_QPA_PLATFORM=offscreen timeout 8 .venv/bin/python main.py   # clean = no output
.venv/bin/python -m mypy main.py train_model/
```

These are local developer verification utilities. Select checks appropriate
to removal and to any brake, beacon or integrated-clock changes. The working
tree includes focused `test_beacon_codec.py` and `test_integrated_clock.py`
utilities; their presence alone does not establish passing results. No tests were executed for this documentation edit. mypy reports one
known error in `app.py` ([B17](bugs.md#b17)) until that is fixed.
