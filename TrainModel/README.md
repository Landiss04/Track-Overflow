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
  (`train_model/link.py`), and reads back only `TrainModelOutputs`. Three
  test-only commands ride alongside: set a failure, clear the passenger brake
  latch, and reset.

Once the system is integrated, the central harness calls the same
`TrainModelState.step` the link calls; the test UI and the link are removed
with no change to the module. Either window starts on its own; the test UI
reads *Not connected* until the Train Model is up, and reconnects if it
restarts.

QML owns all visuals; Python owns state. The two talk through QML context
properties: `theme` and `trainModel` in the Train Model window, `theme` and
`harness` in the test UI.

See [open issues](docs/open-issues.md) for speed-control ownership,
vehicle calibration, and the displayed power-consumption limitation.

## Physics stepping

Commands are held for the complete tick. Traction is evaluated at the
midpoint velocity so its mechanical work cannot exceed the available
commanded energy. Internal substeps resolve the low-speed `P/v` transition;
they do not change the harness clock. Stops are integrated only up to zero
velocity, then static holding or rollback is evaluated for the remaining
time. Reported acceleration uses the current forces at the final velocity.
Nonfinite numeric inputs and negative power are rejected before state changes.

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
integrates their physical effect. Failures can be set from either window.

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
nobody and is not kept for later. Disembarking is unchanged: a draw on each
door-open rising edge at rest.

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
- Power consumption (Train Model window) displays capped commanded power,
  suppressed on engine failure; see [open issues](docs/open-issues.md) for the
  measurement limitation.
- The test UI shows no onboard passenger count: it is not a cross-module
  output. The Train Model window shows it; the test UI shows the remaining
  `passenger_capacity`.
- Both pages display speed in mph, distance/elevation in feet, temperature
  in Fahrenheit, and power in kW. Grade remains in degrees. Test editors
  convert back to backend units before staging commands; model state remains SI.
