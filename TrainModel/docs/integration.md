# Removing the test UI and wiring the Train Model into the system

How to take the Train Model from its standalone test setup to the integrated
system, per D010: the test UI is removed and the module is wired in with no
change to the module's physics or its interface.

Read [module-interface.md](module-interface.md) first; this guide assumes it.

At the time of writing there is no central harness in the repository yet.
Section 4 describes what it must do for the Train Model; the code there is a
sketch, not existing code.

## 1. What is module and what is test scaffolding

| Keep: the module | Remove: test scaffolding |
|---|---|
| `train_model/interface.py`: boundary types | `test_ui.py`: test UI entry point |
| `train_model/model.py`: physics | `train_model/harness.py`: test UI state, stand-in producers, clock driving |
| `train_model/state.py`: module wrapper the window binds to | `train_model/link.py`: socket link, wire format, `TestLinkServer` |
| `train_model/app.py`: window bootstrap | `ui/TestMain.qml`, `ui/TestView.qml`: test UI window |
| | `train_model/track_stub.py`: stand-in Track Model; Blue Line by default, Red or Green by flag |
| | `train_model/speed_limiter.py`: stand-in Train Controller speed limiter |
| `ui/Main.qml`, `ui/MainView.qml`: Train Model window | |
| `main.py`: standalone Train Model window (optional after integration) | |

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

After integration:

```
system process
┌──────────────────────────────────────────────────────────────────┐
│ SystemClock ─tick─► central harness ─step(dt, inputs)─► TrainModelState ── TrainModel
│                      ▲   │ edge mappings (D005/D008)         │
│  Train Controller ───┘   └──► Train Controller, Track Model ◄┘ outputs
│  Track Model                                     Main.qml / MainView.qml
└──────────────────────────────────────────────────────────────────┘
```

## 2. Removing the test UI

Do these in one commit, then run the checks in section 6.

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

`main.py` starts a `TestLinkServer`. Remove the import and the three lines
that create and start it, so it only builds the window:

```python
from train_model.app import run_window
from train_model.state import TrainModelState


def main() -> int:
    """Run the Train Model window on its own."""
    return run_window(
        "Train Model", "Main.qml",
        lambda: {"trainModel": TrainModelState()},
    )
```

Once the system process hosts the window (section 5), `main.py` is only a
standalone viewer and can be deleted.

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
`test_model_invariants.py`. Do not remove it until the release path below
exists.

### Passenger brake release

A passenger pull latches. Today only the test-only override clears it. Truth
(`arbitration/passenger-emergency-brake.md`, D011) says the **Train
Controller** releases it, but does not yet settle the signal or mechanism.
Until that is decided and implemented, removing the test UI leaves no way to
release a passenger pull. Settle this before integration.

### 2.5 Update the README

Remove the test UI parts of `TrainModel/README.md`: the two-process
description, `python test_ui.py` and its smoke test, `TRAIN_MODEL_LINK`, the
test UI rows of the layout table, and the "Passenger brake override" section.

## 3. What the system must do for each Train Model

For every train, the central harness (D005):

1. **Creates** one `TrainModelState(TrainConfig(seed=...))` when the train is
   dispatched, and drops it when the train leaves service. Use a distinct
   seed per train if their disembark counts should differ.
2. **Steps** it once per shared-clock tick with `dt = clock.tick_s`. Never
   vary dt; speed and pause change only how often ticks come (D006).
3. **Builds inputs** each tick, from the latest Train Controller commands and
   Track Model data, through the edge mappings (section 4).
4. **Routes outputs** each tick: `outputs.controller` to that train's Train
   Controller, `outputs.track` to the Track Model.
5. **Handles rejection.** `step` raises `InvalidTimeStepError` or
   `InvalidInputError` without changing the train. Decide what that means
   system-wide; the test UI's choice is to check the step first with
   `TrainModel.validate_inputs` and hold the clock rather than advance it with
   a train left behind.
6. **Runs on the Qt thread.** `TrainModelState` is a `QObject` whose signals
   drive the window; call it from the thread that owns it.

The Train Model never reads another module, never reads the clock, and never
calls the harness. Everything arrives through `step`.

## 4. Edge mappings

Per D008 the harness maps producer → catalog type (`common/interfaces.py`) →
consumer type. The Train Model's side of each edge:

### Train Controller → Train Model (`ControllerCommands`)

| Module field | From | Note |
|---|---|---|
| `power_cmd_w` | power command | W, ≥ 0; a negative value is rejected. |
| `service_brake`, `emergency_brake` | brake commands | |
| `interior_lights`, `exterior_lights` | light command | |
| `door_left_open`, `door_right_open` | door command | The model no longer enforces a 0 mph interlock; see open-issues.md. |
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
| `track_info.station_name` | the block's station, else `None` | Needed for boarding. **No catalog field yet**: add one to the Track Model edge. |
| `track_signal.commanded_speed_mps`, `authority_blocks` | track circuit | Authority is an `int` count of blocks, ≥ 0. |
| `beacon` | beacon under the train this tick, else `None` | |
| `passengers_boarded` | boarding count | Send once per boarding event, at rest with a door open, ≤ last `passenger_capacity`. Otherwise 0. |

### Train Model → Train Controller (`ControllerOutputs`)

Actual speed, Brake State, Door State, Light State, cabin temperature,
and the passed-through commanded speed, authority, speed limit and beacon.
Failure status is not sent. See [module-interface.md](module-interface.md#5-outputs-trainmodeloutputs).

### Train Model → Track Model (`TrackOutputs`)

Block ID, offset (signed), actual speed, block-change flag, passenger
capacity. The Track Model uses position for occupancy and capacity for the
next boarding count.

The catalog's `ITrainModel` (`common/interfaces.py`) is setter-shaped
(`set_power_command`, `update(dt)`, `get_state`). Per D008 the module does
not implement or import it; if the harness wants that shape, it wraps
`TrainModelState` in an adapter on the harness side.

### Sketch

Illustrative only; names on the harness side are placeholders.

```python
from train_model.interface import TrainConfig, TrainModelInputs
from train_model.model import TrainModelError
from train_model.state import TrainModelState


class TrainModelEdge:
    """Harness-side owner of one train's Train Model."""

    def __init__(self, train_id: str, seed: int) -> None:
        self.train_id = train_id
        self.module = TrainModelState(TrainConfig(seed=seed))

    def on_tick(self, _sim_time_s: float, tick_s: float) -> None:
        inputs = TrainModelInputs(
            controller=map_controller_to_train_model(
                controller_outputs(self.train_id)),
            track=map_track_to_train_model(track_outputs(self.train_id)),
        )
        try:
            outputs = self.module.step(tick_s, inputs)
        except TrainModelError as exc:
            report_rejection(self.train_id, exc)   # system policy, step 5
            return
        deliver_to_controller(self.train_id,
                              map_to_controller(outputs.controller))
        deliver_to_track_model(self.train_id, map_to_track(outputs.track))


# clock = SystemClock(); clock.add_tick_listener(edge.on_tick)
```

Order within a tick matters for latency only: if the Train Controller steps
before the Train Model, it acts on the Train Model's previous outputs, one
tick behind. Pick one order and keep it fixed.

## 5. Showing the Train Model window

`train_model/app.py`'s `run_window` creates its own `QGuiApplication` and runs
the event loop, so it suits a standalone process only. Inside the system's
own application, load the window with the system's engine instead:

1. Expose `theme` (from `ui/theme.py`, `build_theme()`) and `trainModel` (the
   train's `TrainModelState`) as context properties.
2. Load `TrainModel/ui/Main.qml`.
3. Optionally apply `ui.aspect_lock.install_window_scaling` to the window.

`Main.qml` and `MainView.qml` read only `trainModel` and `theme`, and contain
no reference to the test UI. The header shows *Running* while steps arrive
and *Paused* when they stop, whoever sends them. Failure injection and the
passenger emergency brake button call `TrainModelState` directly, so they
keep working with no test UI. For several trains, give each window its own
`TrainModelState`, or switch one window's `trainModel` between trains.

## 6. Checks after removal

```bash
cd TrainModel
grep -rn "harness\|train_model.link\|TestMain\|TestView\|test_ui" \
    --include=*.py --include=*.qml .        # comments only, no imports
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
QT_QPA_PLATFORM=offscreen timeout 8 .venv/bin/python main.py   # clean = no output
.venv/bin/python -m mypy main.py train_model/
```

The physics, integration, contract, stub, elapsed-clock and invariant tests
should all pass unchanged; they never touched the test UI. mypy reports one
known error in `app.py` ([B17](bugs.md#b17)) until that is fixed.
