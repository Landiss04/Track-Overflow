# Train Model UI

PySide6 + QML front-end for the ECE1140 Train Model, covering **page 3a** (main
operational view) and **page 3b** (test harness). `TrainModelState` wraps the
real `TrainModel` in `train_model/model.py`, and the views show the model's
state. Header metadata that the model does not produce (train ID, line,
arrival) shows a dash. The clock shows elapsed model time.

The two pages are **independent windows, each its own process**:

- **Train Model** (`main.py`) owns the module. Its header reads *Running* while
  steps arrive and *Paused* once they stop.
- **Test UI** (`test_ui.py`) stands in for the Track Model, the Train
  Controller and the clock. It drives the module only through its interface,
  `step(dt, TrainModelInputs) -> TrainModelOutputs`, over a local socket
  (`train_model/link.py`), and reads back only `TrainModelOutputs`. Two
  test-only commands ride alongside: clear the passenger brake latch, and
  reset. Failures are set only in the Train Model window; the test UI sees
  their effect in the outputs. Its clock is the shared simulation clock
  (`utils/system_clock.py`): each step is one clock tick, dt is the clock's
  fixed tick length, and the **1x / 10x** speed toggle changes only how often
  ticks happen. A step is checked with the module's own input rules before
  its tick, so rejected input never advances the clock, and the clock is held
  as soon as the Train Model drops. Every 30 ticks the test UI compares the
  clock with the steps the module accepted and shows any gap as **Clock
  drift**.

The test UI also carries three stand-ins, all removed at integration with the
rest of it:

- **Blue Line, loaded by default** (`train_model/track_stub.py`). As the
  stand-in Track Model, the test UI reads the Track Model's
  `TrackModel/blue_line.json` and follows the train along section A, through
  the switch at block 5, to Station B at block 10. The track rows (block,
  grade, elevation, speed limit, polarity, station, beacon) move to the next
  block once the train's offset reaches the block's 50 m, and polarity flips
  on each change, which is the Train Model's block-change event. The
  transponder at block 9 sends the Station B beacon. An edit to a track row
  lasts until the next block change. Travel is forward only, and the train
  stays on block 10 at the end of the route. Run Control shows the track.
- **Speed limiter** (`train_model/speed_limiter.py`). The Train Model does not
  govern its own speed (D009), so as the stand-in Train Controller the test UI
  limits it: a PI control law (trapezoidal integration of the speed error, no
  integration while saturated) lowers the entered power to hold the speed at
  the cap, the vehicle's 70 km/h or the speed limit where that is lower. More
  than 0.5 m/s over the cap, or over it and still speeding up with no power as
  on a downhill, it cuts power and applies the service brake until the train
  is 1.5 m/s under the cap. The service brake is on or off, so a downhill
  cycles it; the wide band keeps that to about one application every 4 s at
  -5°, rather than one every 1.6 s. It also drops its integral: the limiter cannot see
  an engine failure, so its integral grows while the train coasts, and kept
  past a brake it would return as a surge on every release, a power and brake
  cycle lasting about a minute. `power_command` keeps showing the entered
  power; the Train Model window's power readout shows what was sent. Run
  Control shows the cap and when it is limiting.
- **Station dwell** (D007). Also as the stand-in Train Controller, once a door
  opens with the train at rest at a station, the test UI holds it there for
  45 s: no power, service brake on, the open doors kept open, whatever is
  entered. Once per stop; the next stop begins once the train has moved. Run
  Control counts the dwell down.

The test UI's inputs scroll in place: the left column shows only the rows that
fit and wraps from the last row back to the first (mouse wheel or drag). The
right column scrolls on its own. The output table lists only what the Train
Controller and the Track Model act on: emergency brake state, door state,
light state, cabin temperature, position block and offset, actual speed,
passenger capacity and speed limit. The passthroughs (commanded speed,
authority, beacon) are still outputs of the module and show on the Train
Model window.

Once the system is integrated, the central harness calls the same
`TrainModelState.step` the link calls; the test UI and the link are removed
with no change to the module. Either window starts on its own; the test UI
reads *Not connected* until the Train Model is up, and reconnects if it
restarts. One test UI at a time drives a Train Model: a second one reads
*Another test UI open* and takes over once the first closes. A test UI that
takes over a train another one drove gets it reset, to match its own fresh
stand-ins; failures or a passenger pull set before the first test UI drives
are kept.

QML owns all visuals; Python owns state. The two talk through QML context
properties: `theme` and `trainModel` in the Train Model window, `theme` and
`harness` in the test UI.

See [open issues](docs/open-issues.md) for speed-control ownership and
vehicle calibration.

Detailed documentation in `docs/`:

- [physics.md](docs/physics.md): exactly what each step computes.
- [module-interface.md](docs/module-interface.md): calls, inputs, outputs,
  errors and timing at the module boundary.
- [integration.md](docs/integration.md): removing the test UI and wiring the
  module into the system.
- [bugs.md](docs/bugs.md): open known bugs, with how to reproduce each.

## Physics stepping

Commands are held for the complete tick. Traction is evaluated at the
midpoint velocity so its mechanical work cannot exceed the available
commanded energy. Internal substeps resolve the low-speed `P/v` transition;
they do not change the harness clock. Stops are integrated only up to zero
velocity, then static holding or rollback is evaluated for the remaining
time. Reported acceleration uses the current forces at the final velocity.
Nonfinite numeric inputs and negative power are rejected before state changes.

## Reference mass and operating mass

The model uses two masses with different jobs.

**Reference mass** (`TrainConfig.m_ref_kg`, fixed at 51,433 kg) is the mass at
which the datasheet rates the vehicle's performance: two-thirds load. The
datasheet gives 40,900 kg empty and 56,700 kg fully loaded (4 pass./m²), so
the ⅔-load mass is 40,900 + ⅔ × (56,700 − 40,900) = 51,433 kg. It is used only
to turn the rated rates into force limits, and never changes during a run:

| Force | Rated rate × reference mass |
|---|---|
| Max traction (`f_max_n`) | 0.5 m/s² × 51,433 = 25,717 N |
| Service brake (`f_service_n`) | 1.2 m/s² × 51,433 = 61,720 N |
| Emergency brake (`f_emergency_n`) | 2.73 m/s² × 51,433 = 140,413 N |

**Operating mass** (`TrainModelSnapshot.mass_kg`) is what the train weighs now,
and is the *m* in F = m·a every tick: empty mass plus crew and passengers at
77.11 kg (170 lb) each. It runs from 41,286 kg (5 crew only) to 58,404 kg
(full, 222 passengers) and is recomputed whenever passengers board or alight.

Because the forces are fixed while the mass varies, the datasheet rates hold
at ⅔ load, and an empty train accelerates and brakes harder than a full one:

| Train | Operating mass | Emergency deceleration |
|---|---|---|
| Crew only | 41,286 kg | ≈ 3.42 m/s² |
| At the reference mass | 51,433 kg | 2.73 m/s² from the brake, ≈ 2.75 m/s² with rolling resistance |
| Full | 58,404 kg | ≈ 2.42 m/s² |

The two masses use different passenger weights by design: the reference mass
comes straight from the datasheet's empty and loaded masses, the operating mass
from 170 lb per person (customer Q&A). That is why 148 passengers at 170 lb
(52,312 kg) does not equal the 51,433 kg reference mass.

## Design sources

- **Tokens** — every color, font size, spacing, radius, and control dimension
  comes from `documents/UI_Style_Guide.md` (light theme), exposed as a single
  `theme` object built by the shared [`ui/theme.py`](../ui/theme.py) at the
  repository root. No QML file hard-codes a
  color or a token-sized dimension.
- **Dimensions & copy** — element sizes and the on-screen text are taken from
  the Figma CSS exports in `refrence-docs/` (`UIwireframe.css` = main page,
  `TestUIwireframe.css` = test UI).

## Run

```bash
cd TrainModel
source .venv/bin/activate        # PySide6 6.11 + mypy; see "Setup" if missing
python main.py                   # Train Model window
python test_ui.py                # test UI window, in a second terminal
```

Offscreen smoke test (no display needed):

```bash
QT_QPA_PLATFORM=offscreen timeout 8 python main.py      # clean = no output
QT_QPA_PLATFORM=offscreen timeout 8 python test_ui.py   # clean = no output
```

Tests (`pip install pytest` into `.venv` first):

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
```

Set `TRAIN_MODEL_LINK` to run a pair on a private link name, for example
beside a Train Model that is already open.

## Type-check

```bash
cd TrainModel
.venv/bin/python -m mypy main.py test_ui.py train_model/
```

PySide6 ships its own type stubs, so no local stubs are needed.

## Layout

```
main.py                 Train Model process: state, link server, Main.qml
test_ui.py              test UI process: link client, harness, TestMain.qml
train_model/app.py      shared bootstrap: theme, font, QML engine, scaling
train_model/link.py     test UI link: wire format, server, socket client
train_model/state.py    TrainModelState — page 3a bindable values + slots
train_model/harness.py  TestHarnessState — page 3b inputs/outputs/run control
train_model/track_stub.py  test UI stand-in Track Model (Blue Line)
train_model/speed_limiter.py  test UI stand-in Train Controller speed limiter
ui/Main.qml             Train Model window shell around page 3a
ui/TestMain.qml         test UI window shell around page 3b
ui/MainView.qml         page 3a
ui/TestView.qml         page 3b
```

Reusable QML components are not in this folder. They live in the shared
root-level [`ui/`](../ui/README.md) library and are imported from each view
with `import "../../ui"`.

## Setup (if `.venv` is missing)

```bash
cd TrainModel
python3 -m venv .venv
.venv/bin/pip install "PySide6==6.11.*" "mypy==2.3.*"
```

## UI state and editing

The Train Model window reads the model snapshot. The test UI reads only the
module's outputs: the Train Model pushes them after every step and after any
Train Model UI action, so passenger-brake and failure changes reach the test
UI's controls and outputs immediately, including while paused; the next tick
integrates their physical effect. Failures are set only in the Train Model window: the
test UI had its own failure card, removed as redundant. Failure status is not
an output, since the Train Model does not send it to the Train Controller, so
the test UI does not show which failures are set, only their effect.

Test input rows show live values until edited: brakes, lights, doors,
commanded speed and authority read back from the outputs; the rest show the
last accepted command. There is no power output, so `power_command` shows the
accepted command even while the engine has failed. Explicit edits are marked
**pending** and remain staged until **Send inputs**, which also advances one
tick. Starting or advancing a fresh simulation also sends its initial edits.
Live updates preserve the focused editor and its unfinished text. A rejected
submission displays an error, pauses running, and retains the model state and
pending edits for correction. Validation happens before a passenger-brake
override, so invalid inputs cannot release the brake.
Later ticks reuse accepted producer commands, so a suppressed readout during
a failure does not overwrite the underlying command. `passengers_boarded`
is a one-time event: sending consumes the count and returns its row to zero;
enter another count for another boarding event. Reset clears the model,
failures, pending edits, and elapsed time.

## Doors and boarding

The doors are interlocked: a door can only open at 0 mph. An open command
while the train is moving leaves the door closed, and a held command opens it
on the first tick that starts at rest. An open door closes as soon as the
train moves. Door state therefore reports the actual doors, which can differ
from the command.

Passengers board only at a station with a door open. The `station` input row
names the station in the current block (`TrackInfo.station_name`); leave it
empty away from a station. A boarding count sent at any other time boards
nobody and is not kept for later. Disembarking is one draw per stop, on its
first door opening at rest; the next stop begins once the train has moved.

## Passenger brake override

The test harness emergency-brake input can explicitly override the passenger
latch. An injected brake failure blocks the service brake only; the emergency
brake and a passenger pull still work. The overview offers
no release, pending a decision on normal operation; this test override does
not define that policy. Its button always reads *Apply emergency brake* and is
disabled while the emergency brake is engaged from any source (a Train
Controller command from the test UI, or a pull) and while a pull is latched.

## Remaining display limitations

- Train ID, line, and arrival time have no model source and display a dash.
- Manual door buttons remain disabled: the model displays the commanded doors
  as the interlock allows them.
- Power command (Train Model window) displays the commanded power, capped at
  the maximum and zero on engine failure. It is not the power delivered or
  consumed, which the model does not account for.
- The test UI shows no onboard passenger count: it is not a cross-module
  output. The Train Model window shows it; the test UI shows the remaining
  `passenger_capacity`.
- Both pages display speed in mph, distance/elevation in feet, temperature
  in Fahrenheit, and power in kW. Grade remains in degrees. Test editors
  convert back to backend units before staging commands; model state remains SI.
