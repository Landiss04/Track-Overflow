# Train Model module interface

The boundary of the Train Model: what a caller constructs, calls, sends and
receives. Defined in `train_model/interface.py` (types and the `TrainModel`
protocol) and implemented in `train_model/model.py`. The Qt wrapper the
system drives, `TrainModelState`, is in `train_model/state.py`.

Per D005, these are the Train Model's own boundary types. Other modules never
import them; the central harness maps between them and the system catalog
(`common/interfaces.py`, D008). All values are in backend units
(`truth/conventions/units.md`): SI, with grade in degrees and temperature in
°C.

## 1. Two layers

| Layer | Class | Who uses it |
|---|---|---|
| Physics | `train_model.model.TrainModel` | Pure Python, no Qt. Tests, and `TrainModelState`. |
| Module | `train_model.state.TrainModelState` | A `QObject` wrapping one `TrainModel`. The central harness (and today the test link) calls it; the Train Model window binds to it. |

Integrate against `TrainModelState`: it steps the physics **and** keeps the
Train Model window up to date. Use `TrainModel` directly only where no window
is wanted (tests, batch runs).

## 2. Construction

```python
from train_model.interface import TrainConfig
from train_model.model import TrainModel
from train_model.state import TrainModelState

model = TrainModel(TrainConfig())             # physics only
state = TrainModelState(TrainConfig(seed=7))  # module with its window state
```

- One instance per train. Instances share nothing.
- A new train is at rest with crew only, doors closed, no failures, cabin at
  20 °C, offset 0 and no block.
- `TrainConfig` is frozen. Give each train its own `seed` if trains should
  draw different disembark counts.

## 3. Calls

### `step(dt, inputs) -> TrainModelOutputs`

Advances one tick. This is the only call the rest of the system needs.

| | |
|---|---|
| `dt` | Tick length in seconds: the shared clock's fixed tick (`utils/system_clock.py`, 0.1 s). Constant for the whole run (D006). Fast-forward and pause change how often `step` is called, never `dt`. |
| `inputs` | `TrainModelInputs` for this tick (section 4). Send a complete set every tick; nothing is remembered between calls except the train's own state. |
| Returns | `TrainModelOutputs` for this tick (section 5). |
| Raises | `InvalidTimeStepError` if `dt` is not finite and positive, or is longer than 60 s. `InvalidInputError` (also a `ValueError`) if an on/off input is not a `bool`, a numeric input is not finite, power, `speed_limit_mps` or `commanded_speed_mps` is negative, `grade_deg` is not strictly between −90 and 90, `passengers_boarded` or `authority_blocks` is not an `int` from 0 to 2³¹ − 1, the largest count Qt and QML carry. Both are `TrainModelError`. A rejected step changes nothing. |

`TrainModelState.step(dt, inputs, *, override_passenger_brake=False)` has
the same contract, also refreshes the window, and marks the module as
*Running*. The keyword argument is test-only; integration leaves it `False`.

### `TrainModel.validate_inputs(dt, inputs) -> None` (static)

Applies the same checks as `step` without touching any train. Use it to
reject a tick before advancing the shared clock.

### `snapshot() -> TrainModelSnapshot` (`TrainModel` only)

Full observable state for display, with no side effects: operating mass,
acceleration, velocity, crew, passengers aboard, passenger-brake latch,
failure flags, the last outputs, the last accepted inputs and elapsed time. Not a cross-module
output: other modules must not read it.

### `outputs() -> TrainModelOutputs` (`TrainModelState` only)

The current outputs without stepping. They change between steps only when a
Train Model UI action happens (failure, passenger pull).

### UI actions (not cross-module inputs)

| Call | Effect |
|---|---|
| `set_failures(FailureState)` / `TrainModelState.setFailure(name, active)` | Murphy fault injection from the Train Model window. Shown at once in `snapshot().failures`, never output; physical effect from the next step. |
| `pull_passenger_emergency_brake()` / `TrainModelState.applyEmergencyBrake()` | A passenger pull. Latches; reported at once; force from the next step. |
| `clear_passenger_brake_for_test()` | **Test only.** Clears the latch. |
| `TrainModelState.reset()` | **Test only.** Replaces the train with a fresh one. |

## 4. Inputs: `TrainModelInputs`

```
TrainModelInputs
├── controller: ControllerCommands     from the Train Controller
└── track: TrackInputs                 from the Track Model
    ├── track_info: TrackInfo
    ├── track_signal: TrackSignal
    ├── beacon: Beacon | None
    └── passengers_boarded: int
```

### `ControllerCommands` (Train Controller, every tick)

| Field | Type | Unit | Meaning |
|---|---|---|---|
| `power_cmd_w` | float | W | Commanded power, ≥ 0. Capped at 480 kW inside the model. |
| `service_brake` | bool | | Service brake command. |
| `emergency_brake` | bool | | Emergency brake command (controller path only; a passenger pull is internal). |
| `interior_lights` | bool | | Light Command, interior. |
| `exterior_lights` | bool | | Light Command, exterior. |
| `door_left_open` | bool | | Door Command, left. Obeyed only at 0 mph. |
| `door_right_open` | bool | | Door Command, right. Obeyed only at 0 mph. |
| `temp_setpoint_c` | float | °C | Cabin temperature setpoint. |
| `announcement` | str | | Passed in; not used by the physics. |

### `TrackInfo` (Track Model, every tick)

| Field | Type | Unit | Meaning |
|---|---|---|---|
| `block_id` | str | | Block the train is in. |
| `grade_deg` | float | deg | Grade, positive uphill in the direction of travel. Strictly between −90 and 90. Layout files give percent; the loader converts. |
| `elevation_m` | float | m | Elevation. Validated, not used by the physics. |
| `speed_limit_mps` | float | m/s | Nonnegative. Passed through to the Train Controller. |
| `polarity` | bool | | Track-circuit polarity. A change from the previous tick is a block change. |
| `station_name` | str \| None | | Station in this block, or `None`. Default `None`. Boarding needs a station. |

### `TrackSignal` (Track Model, every tick)

| Field | Type | Unit | Meaning |
|---|---|---|---|
| `commanded_speed_mps` | float | m/s | Nonnegative. Passed through to the Train Controller. |
| `authority_blocks` | int | blocks | Blocks the train may travel before it must stop. Nonnegative. Passed through. |

Both are reported as 0 while signal pickup has failed.

### `Beacon` (Track Model, only on the tick the train passes one)

| Field | Type | Meaning |
|---|---|---|
| `station_name` | str | Station the beacon announces. |
| `platform_side` | `"L"` or `"R"` | Platform side. |
| `underground` | bool | Whether the station is underground. |

Send `None` on every other tick.

### `passengers_boarded` (Track Model)

An `int`, 0 except on a boarding event, never negative. It boards only at a
station with a door open, and never beyond capacity. It is consumed by the step that
carries it: send it on one tick only, and never more than the
`passenger_capacity` last reported.

## 5. Outputs: `TrainModelOutputs`

```
TrainModelOutputs
├── controller: ControllerOutputs      to the Train Controller
└── track: TrackOutputs                to the Track Model
```

### `ControllerOutputs`

| Field | Type | Unit | Meaning |
|---|---|---|---|
| `actual_speed_mps` | float | m/s | Signed; negative in rollback. |
| `emergency_brake_active` | bool | | Brake State [0]: emergency brake **engaged** (commanded or passenger), not the command. |
| `service_brake_active` | bool | | Brake State [1]: service brake engaged. False while the emergency brake is engaged or the brakes have failed. |
| `door_left_open`, `door_right_open` | bool | | Door State: actual doors after the interlock. |
| `interior_lights_on`, `exterior_lights_on` | bool | | Light State: follows the command. |
| `cabin_temp_c` | float | °C | Cabin temperature. |
| `commanded_speed_mps` | float | m/s | Passed through; 0 under signal pickup failure. |
| `authority_blocks` | int | blocks | Passed through; 0 under signal pickup failure or before the first step. |
| `speed_limit_mps` | float | m/s | Passed through from `TrackInfo`. |
| `beacon` | Beacon \| None | | This tick's beacon, else `None`. |

### `TrackOutputs`

| Field | Type | Unit | Meaning |
|---|---|---|---|
| `block_id` | str | | Block from this tick's `TrackInfo`; `""` before the first step. |
| `offset_m` | float | m | Distance since the last block change, front of train; negative in rollback. |
| `actual_speed_mps` | float | m/s | Same value as in `ControllerOutputs`. |
| `block_changed` | bool | | True on the tick polarity changed. |
| `passenger_capacity` | int | | Places left, after this tick's disembark draw and boarding. |

## 6. Timing and ordering

- Call `step` once per shared-clock tick, with the clock's fixed `dt`.
- Outputs describe the state at the **end** of the tick. A consumer that
  feeds back (the Train Controller computes power from speed) sees them on
  its next tick, one tick of latency.
- Doors and boarding use the speed at the **start** of the tick.
- A UI action between ticks changes `outputs()` immediately; integrate its
  physical effect on the next `step`.

## 7. Errors

| Exception | When | State after |
|---|---|---|
| `InvalidTimeStepError` | dt nonfinite, ≤ 0 or > 60 s | Unchanged |
| `InvalidInputError` | On/off input not a `bool`; nonfinite number; negative power, speed limit or commanded speed; grade not strictly between −90° and 90°; boarding count or authority not an int from 0 to 2³¹ − 1 | Unchanged |

Both derive from `TrainModelError`. A rejected step does not advance the
train or its random generator. Decide in the harness what a rejection means
for the rest of the system (section 3 of [integration.md](integration.md)).

## 8. Signals to truth names

| Truth signal | Direction | Field(s) |
|---|---|---|
| `power-command` | in | `controller.power_cmd_w` |
| `service-brake-command` | in | `controller.service_brake` |
| `emergency-brake-command` | in | `controller.emergency_brake` |
| `light-command` | in | `controller.interior_lights`, `exterior_lights` |
| `door-command` | in | `controller.door_left_open`, `door_right_open` |
| `temperature-setpoint` | in | `controller.temp_setpoint_c` |
| `announcement` | in | `controller.announcement` |
| `track-info` | in | `track.track_info` |
| `track-signal` | in, passed out | `track.track_signal` → `commanded_speed_mps`, `authority_blocks` |
| `beacon` | in, passed out | `track.beacon` → `controller.beacon` |
| `passengers-boarded` | in | `track.passengers_boarded` |
| `actual-speed` | out | `controller.actual_speed_mps`, `track.actual_speed_mps` |
| `brake-state` | out | `emergency_brake_active`, `service_brake_active` |
| `door-state` | out | `door_left_open`, `door_right_open` |
| `light-state` | out | `interior_lights_on`, `exterior_lights_on` |
| `cabin-temperature` | out | `cabin_temp_c` |
| `train-position` | out | `track.block_id`, `track.offset_m` |
| `block-change-event` | out | `track.block_changed` |
| `passenger-capacity` | out | `track.passenger_capacity` |

`TrackInfo.station_name` has no promoted truth signal yet: the Track Model
must supply it for boarding to work.

## 9. Minimal example

```python
from train_model.interface import (
    ControllerCommands, TrackInfo, TrackInputs, TrackSignal,
    TrainConfig, TrainModelInputs,
)
from train_model.model import TrainModel

model = TrainModel(TrainConfig())
inputs = TrainModelInputs(
    controller=ControllerCommands(
        power_cmd_w=120_000.0, service_brake=False, emergency_brake=False,
        interior_lights=True, exterior_lights=True,
        door_left_open=False, door_right_open=False,
        temp_setpoint_c=21.0, announcement="",
    ),
    track=TrackInputs(
        track_info=TrackInfo(block_id="GREEN A1", grade_deg=0.29,
                             elevation_m=0.5, speed_limit_mps=12.5,
                             polarity=True, station_name=None),
        track_signal=TrackSignal(commanded_speed_mps=12.5,
                                 authority_blocks=2),
        beacon=None,
        passengers_boarded=0,
    ),
)
out = model.step(0.1, inputs)
print(out.controller.actual_speed_mps, out.track.offset_m)
```
