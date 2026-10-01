# Train Model UI

PySide6 + QML front-end for the ECE1140 Train Model, covering **page 3a** (main
operational view) and **page 3b** (test harness). `TrainModelState` wraps the
real `TrainModel` in `train_model/model.py`: the test harness sends it inputs
and drives the clock, and the views show the model's state. Header metadata that the model does not produce (train ID, line, arrival)
shows a dash. The clock shows elapsed model time, and the mode follows the
harness run/pause state.

QML owns all visuals; Python owns state. The two talk through QML context
properties (`theme`, `trainModel`, `harness`).

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
python main.py
```

Offscreen smoke test (no display needed):

```bash
QT_QPA_PLATFORM=offscreen timeout 8 python main.py   # clean = no output
```

## Type-check

```bash
cd TrainModel
.venv/bin/python -m mypy main.py train_model/
```

PySide6 ships its own type stubs, so no local stubs are needed.

## Layout

```
main.py                 entry point: builds theme, state objects, loads QML
train_model/state.py    TrainModelState — page 3a bindable values + slots
train_model/harness.py  TestHarnessState — page 3b inputs/outputs/run control
ui/Main.qml             window shell, nav rail, 3a/3b view switcher
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

Both pages read the same model snapshot. Passenger-brake and failure changes
refresh the controls and discrete outputs immediately, including while paused;
the next tick integrates their physical effect. Terrain, beacons, lights,
doors, temperature, passenger counts, and the clock refresh from that snapshot.

Test input rows show live values until edited. Explicit edits are marked
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
latch. An injected brake failure still prevents braking. The overview's
passenger-brake release action remains inert pending a decision on normal
operation; this test override does not define that policy.

## Remaining display limitations

- Train ID, line, and arrival time have no model source and display a dash.
- Manual door buttons remain disabled: the model displays the commanded doors
  as the interlock allows them.
- Power consumption displays capped commanded power, suppressed on engine
  failure; see [open issues](docs/open-issues.md) for the measurement limitation.
- Both pages display speed in mph, distance/elevation in feet, temperature
  in Fahrenheit, and power in kW. Grade remains in degrees. Test editors
  convert back to backend units before staging commands; model state remains SI.
