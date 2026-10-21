# Train Model UI

PySide6 + QML front-end for the ECE1140 Train Model, covering **page 3a** (main
operational view) and **page 3b** (test harness). `TrainModelState` wraps the
real `TrainModel` in `train_model/model.py`, and the views show the model's
state. Train ID and line come from the fleet/harness roster. The current clock
uses harness-supplied time in integrated operation and model elapsed time
in standalone operation. Independent drift checks run every 15 harness ticks.
The inspected window retains next station/platform and omits arrival time.

The [SDD v0.2](../documents/Railway_Sim_SDD_Train_Model.md) records Kevin
Schillinger’s October 20, 2026 accepted design. The current working tree includes
concurrent backend/UI edits for summed brakes, complete beacon validation,
integrated clock checks and arrival removal. This documentation task inspected
those edits without implementing or testing them; see [follow-up](docs/open-issues.md).

## Development: standalone utility

The test UI is a developer utility, not a product actor or product use case.

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
  on each change, which is the Train Model's block-change event. The module
  hears of a change a tick late and restarts its offset then, so the stub
  carries the distance run past each block's end into the next: every block
  ends where the track does. The
  transponder at block 9 sends the Station B beacon. An edit to a track row
  lasts until the next block change. Travel is forward only, and the train
  stays on block 10 at the end of the route. Run Control shows the track.
  Flags load another line instead (see [Run](#run)): `--line red` or
  `--line green` loads that line's layout, and `--route` sets the blocks to
  travel as ranges in order. A range that counts down is travelled against the
  block numbering, so its grades change sign; a range longer than 1,000
  blocks, more than any line has, is refused. Default routes: Red `9-1,16-66`,
  from the yard to South Hills Junction; Green
  `63-100,85-77,101-150,28-1,13-57`, the loop from the yard back to it. The
  Red and Green layouts mark no transponders, so the block before each station
  sends its beacon, with the station's platform side (left where it has both)
  and underground flag. The limiter below reacts to each block's limit as the
  train enters it, so where a line's limit drops it brakes down after the
  fact rather than before.
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
  entered, from the tick the door opens, so a door sent together with power
  is still held. Once per stop; the next stop begins once the train has
  moved. Run Control counts the dwell down.

The test UI starts with values a train would begin with, so a first tick
needs no typing: at rest with no power, interior and exterior lights on, doors
closed, cabin set to 70 °F. On a loaded line, the commanded speed is the first
block's speed limit, the authority is the route's last block (the destination
block, block 10 on the Blue Line), and the first block's beacon announces the
first station ahead, so the Train Model window names the next station from the
first tick. Until that tick the rows show these starting values rather than
reading back the module, which has been sent nothing yet; only a passenger
emergency brake pull shows before then. Reset returns to them.

The test UI's inputs scroll in place: the left column shows only the rows that
fit and wraps from the last row back to the first (mouse wheel or drag). Tab
scrolls either column to the control it focuses, and a scroll never takes
focus from a field being edited. The right column's scroll bar always shows,
since Run control runs below the fold, and a refused send scrolls its reason
into sight. The
right column scrolls on its own. The output table lists only the
outputs the Train Model window does not show: position block and offset, and
passenger capacity. The rest (emergency brake, door and light state, cabin
temperature, actual speed, speed limit, and the commanded speed, authority
and beacon passthroughs) are still outputs of the module and show on the
Train Model window.

Once the system is integrated, the central harness calls the same
`TrainModelState.step` the link calls; the test UI and the link are removed
with no change to the module. Either window starts on its own; the test UI
reads *Not connected* until the Train Model is up, and reconnects if it
restarts. One test UI at a time drives a Train Model: a second one reads
*Another test UI open* and takes over once the first closes. A test UI that
takes over a train another one drove gets it reset, to match its own fresh
stand-ins; failures or a passenger pull set before the first test UI drives
are kept. The other way round holds too: a test UI that reconnects after
driving (the Train Model restarted, or the link dropped) gets a fresh train,
so it starts its clock, track, limiter and dwell fresh as well, keeping any
edits not yet sent.

QML owns all visuals; Python owns state. The two talk through QML context
properties: `theme` and `fleet` in the Train Model window, `theme` and
`harness` in the test UI. The fleet holds one `TrainModelState` per train;
the window shows the train picked in its header selector. Standalone,
`main.py` runs a one-train fleet (`T-1`) for the test UI to drive.

See [open issues](docs/open-issues.md) for speed-control ownership and
the remaining backend/UI work.

Detailed documentation in `docs/`:

- [physics.md](docs/physics.md): exactly what each step computes.
- [module-interface.md](docs/module-interface.md): calls, inputs, outputs,
  errors and timing at the module boundary.
- [integration.md](docs/integration.md): removing the test UI and wiring the
  module into the system.
- [bugs.md](docs/bugs.md): open known bugs, with how to reproduce each.

## Physics stepping

Commands are held for the complete tick. Traction is evaluated at the
midpoint velocity in the power-limited regime so segment work matches
commanded work without artificial energy gain. Constant-force segments are exact.
Internal boundaries handle stops and traction-regime transitions accurately;
further segment limits maintain stability. Segment durations total the fixed
external dt; speed/pause change tick frequency only. Stops are integrated only up to zero
velocity, then static holding or rollback is evaluated for the remaining
time. Reported acceleration uses the current forces at the final velocity.
Nonfinite numeric inputs and negative power are rejected before state changes,
as are inputs of the wrong type: a `bool` or text where a number belongs, an
integer too large for a float, a number where a name belongs, and a beacon
whose platform side is not `L`, `R` or `LR`, or whose complete canonical
beacon payload exceeds 128 characters. The inspected codec counts syntax and
escapes; [encoding and validation](docs/module-interface.md#beacon-payload-encoding)
reject overlength payloads without truncation. Name length alone is insufficient.

## Accepted vehicle and brake scope

Maximum power is confirmed at **480 kW**. Rolling resistance uses the existing
configured coefficient `0.002` and is the only passive resistance term in scope;
grade remains gravitational force and braking commanded force. No real-world
calibration study is claimed, and aerodynamic drag, wheel slip and brake build-up
are outside this model.

Both brakes may engage simultaneously and their configured forces sum. Emergency
follows the controller command or passenger latch; service follows its command
unless service failure is active. The inspected working tree implements
independent engagement and summed forces. Pickup failure already outputs zero
commanded speed and authority while leaving terrain unaffected. Position offset
references the front of the train; this decision adds no block-crossing behavior.

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
python test_ui.py --line green   # the same on the Green Line loop
python test_ui.py --line red --route 9-1,16-66   # a line and a route
python test_ui.py --help         # every flag and default route
```

Offscreen smoke test (no display needed):

```bash
QT_QPA_PLATFORM=offscreen timeout 8 python main.py      # clean = no output
QT_QPA_PLATFORM=offscreen timeout 8 python test_ui.py   # clean = no output
```

Local developer verification (`pip install pytest` into `.venv` first):

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
```

Set `TRAIN_MODEL_LINK` to run a pair on a private link name, for example
beside a Train Model that is already open.

For native Windows startup sizing, run the following from the repository
root in the signed-in desktop session. Repeat at the presentation's display
resolution and DPI settings; the check opens each real launcher and checks
that its frame fits above the taskbar, with the shared icon installed:

```powershell
TrainModel\.venv\Scripts\python TrainModel\tests\windows_startup_check.py
```

Use `--shots DIR` to save startup screenshots. The offscreen Windows test
runner can use `QT_QPA_FONTDIR=C:\Windows\Fonts` so Qt can find its fonts;
native desktop runs use the Windows font system directly.

## Type-check

```bash
cd TrainModel
.venv/bin/python -m mypy main.py test_ui.py train_model/
```

PySide6 ships its own type stubs, so no local stubs are needed.

## Build an executable

PyInstaller builds each window as its own executable. Run from the
repository root, not `TrainModel/`. The data folders and logo keep their
source paths inside the bundle: the code finds them under the bundle's
root (`sys._MEIPASS`) at the same paths as under the repository root,
and the QML reaches the shared `ui/` and `pics/` by relative paths.
A folder left out does not fail the build; the window fails to load,
or loads with a blank ad or no track.

| Folder | Holds |
| --- | --- |
| `TrainModel/ui` | the Train Model and test UI QML |
| `TrainModel/pics` | the header ads |
| `ui` | the shared QML components |
| `TrackModel` | the line layouts the test UI loads |
| `utils/Track_Overlow_Logo.png` | the shared window and taskbar icon |

On Windows (PowerShell; `;` separates an `--add-data` source from its
destination, `:` on Linux):

```powershell
foreach ($app in 'main', 'test_ui') {
    pyinstaller --noconfirm --onedir --name $app `
        --paths TrainModel --paths . `
        --add-data "TrainModel\ui;TrainModel\ui" `
        --add-data "TrainModel\pics;TrainModel\pics" `
        --add-data "ui;ui" `
        --add-data "TrackModel;TrackModel" `
        --add-data "utils\Track_Overlow_Logo.png;utils" `
        --hidden-import ui.theme --hidden-import ui.aspect_lock `
        "TrainModel\$app.py"
}
```

The executables land in `dist\main\` and `dist\test_ui\`. Verified with
PyInstaller 6.22.2 and PySide6 6.11.2 on Windows 11 and Linux.

## Layout

```
main.py                 Train Model process: one-train fleet, link server, Main.qml
test_ui.py              test UI process: link client, harness, TestMain.qml
train_model/app.py      shared bootstrap: theme, font, QML engine, scaling
train_model/link.py     test UI link: wire format, server, socket client
train_model/state.py    TrainModelState — page 3a bindable values + slots
train_model/fleet.py    TrainModelFleet — one TrainModelState per train, by ID
train_model/harness.py  TestHarnessState — page 3b inputs/outputs/run control
train_model/track_stub.py  test UI stand-in Track Model (Blue Line)
train_model/speed_limiter.py  test UI stand-in Train Controller speed limiter
ui/Main.qml             Train Model window shell, train selector, page 3a
ui/TestMain.qml         test UI window shell around page 3b
ui/MainView.qml         page 3a
ui/TestView.qml         page 3b
pics/                   header ads, 711 x 44 PNG each
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
is a one-time event: the step that boards it (at rest with a door
open) consumes the count and returns its row to zero. Sent before then,
the count waits in its row until it can board. Enter another count for
another boarding event. Reset clears the model,
failures, pending edits, and elapsed time.

## Doors and boarding

The Train Controller ensures doors remain closed when required. The Train
Model follows Door Command at any speed and enforces no interlock.

The Track Model sends boarding events only at stations. The Train Model checks
rest, an open door, count bounds and capacity without a station-presence gate.
`TrackInfo.station_name` is station display metadata. An ineligible event boards
nobody and is not retained by the model; the developer utility may keep its
staged count until an eligible send. Disembarking is one draw per stop, on the
first tick at rest with a door open, at a station or elsewhere. Reopening a
door does not redraw until the train has moved.

## Development: passenger brake override

The test harness emergency-brake input can explicitly override the passenger
latch. An injected brake failure blocks the service brake only; the emergency
brake and a passenger pull still work. The overview offers
no release action. Normal release is the Train Controller’s one-shot
`passenger_brake_release`; it clears only the passenger latch, preserving an
independently held controller emergency command. That path already exists. Its button always reads *Apply emergency brake* and is
disabled while the emergency brake is engaged from any source (a Train
Controller command from the test UI, or a pull) and while a pull is latched.

## Train Model window

- **Ads.** The open middle of the header, between the train selector and
  the line and clock, shows an ad: a long, thin card like those in a
  subway car. The ads in `pics/` take turns, each up for 30 s. They are
  drawn at 711 x 44 px on the 1440 x 900 canvas, the slot's full width;
  while the *E-brake* badge shows, the slot narrows to 591 px and the
  ad's sides are cropped. A new ad is added to `pics/` and to the list
  in `ui/Main.qml`.
- **Announcements.** Each new announcement from the Train Controller opens a
  popup with its text, over the left column and clear of the emergency brake
  button. It is not modal; **Dismiss** or Escape closes it, the same
  announcement on later ticks does not reopen it, and an empty announcement
  closes it. It never grows past the window: a long announcement scrolls
  inside it.
- **Stations.** The Position card's *Station* row names the station in the
  current block. *Next station* is the last beacon's station, kept until the
  train reaches it.
- **Failures.** An active failure's button is red (danger) and reads *Clear*;
  an idle one is the secondary style and reads *Induce*. The red is a Train
  Model exception to style guide §6.1, which gives a clear-fault action the
  green success fill; the guide itself is unchanged.

## Remaining display limitations

- Train ID and line already come from fleet metadata. Arrival time is outside
  the intended window for now; the inspected QML retains next-station/platform
  without arrival. Integrated time and selected-train drift diagnostics are
  present in current working-tree code; see [follow-up](docs/open-issues.md).
- Power command (Train Model window) displays the commanded power, capped at
  the maximum and zero on engine failure. It is not the power delivered or
  consumed, which the model does not account for.
- The test UI shows no onboard passenger count: it is not a cross-module
  output. The Train Model window shows it; the test UI shows the remaining
  `passenger_capacity`.
- Both pages display speed in mph, distance in feet, temperature in
  Fahrenheit, and power in kW. Grade remains in degrees. Elevation is not
  shown in the Train Model window; the test UI's elevation input is in feet. Test editors
  convert back to backend units before staging commands; model state remains SI.
