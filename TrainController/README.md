# Train Controller UI (page 4, driver cab)

PySide6 + QML front-end for the ECE1140 Train Controller (software variant):
the page 4 driver cab for T-214 on the Green Line. The controls a driver uses
are live and drive a light simulation on real Green Line track. There is no
PI control law and no Train Model connection yet.

QML owns all visuals and Python owns state. The two talk through the QML
context properties `theme` and `controller`, the same pattern as `TrainModel/`.

## Sources of truth

Normative rules come from the `truth` branch (see `AGENTS.md`). Read them with
`git show origin/truth:truth/<path>`. This module follows:

- `ui/style-guide.md`: tokens and component rules. The Train Controller
  service brake and emergency brake are the only unconfirmed destructive
  controls (§7).
- `conventions/units.md`: backend SI, display imperial. **Authority is a block
  ID**, shown unconverted.
- `conventions/identifiers.md`: every ID is a string.
- `conventions/files-and-paths.md`: layout data is loaded from the
  `TrackModel/*.json` files at startup.
- `conventions/toolchain.md`: Python ≥ 3.10, PySide6 ≥ 6.11 and PyInstaller
  6.22.2, **in a virtual environment only**.

The UI is built from the shared components in the repository-level
[`ui/`](../ui/README.md) folder: `ScaledWindow`, `ModuleHeader`, `Panel`,
`TelemetryReadout`, `SafetyButton`, `SegmentedToggle`, `SelectField`,
`FormField`, `TrackBlock`, `StatusBadge`, `KeyValueRow`, `Callout`,
`AppButton` and `ValueField`. The theme and window scaling come from the same
place. Only pieces with no shared equivalent live in `ui/components/` here.

## Setup and run

Everything runs from the module's virtual environment (Windows paths shown;
use `.venv/bin/` on macOS/Linux):

```bash
cd TrainController
python -m venv .venv
.venv/Scripts/python -m pip install -r ../requirements.txt
.venv/Scripts/python main.py
```

Tests:

```bash
cd TrainController
.venv/Scripts/python -m unittest discover tests
```

Offscreen smoke test (no display needed). `QT_QPA_FONTDIR` is needed on
Windows because Qt's offscreen platform ships no fonts:

```bash
QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts timeout 6 .venv/Scripts/python main.py
```

## Scenario

T-214 enters **block 62** (section J) with **authority to block 76** (the end
of section M). Ahead are GLENBURY (block 65) and DORMONT (block 73), both with
right-side platforms. The speed limit is that of the occupied block, read from
`TrackModel/green_line.json`.

## What you can do

| Control | Effect |
|---|---|
| Slower / Faster | Target ±1 mph, from 0 to the occupied block's limit. Locked in Automatic. |
| Use CTC target | Adopt the CTC's commanded speed. Locked in Automatic. |
| Service brake Off/On | Immediate. Slows at 1.2 m/s² while on, and a header badge shows it. |
| Emergency brake | Immediate, no confirmation. Latches, and the header shows an E-BRAKE badge. |
| Release emergency brake | The driver releases it, **only once the train is fully stopped**. |
| Open / Close left, right | Only when stopped in a station block, on that station's platform side. The train won't move with doors open. |
| Announce again | Shows the station announcement for 5 s. |
| Cooler / Warmer | Setpoint ±1 °F (60–80). The cabin temperature drifts toward it. |
| Cabin lights / Headlights | Off / On. |
| User: Engineer | Opens the Kp/Ki pop-up (step or type values, then apply). Close or Esc returns to Driver. |
| Mode: Automatic / Manual | Automatic hands the target to the CTC. |

The tick runs once per second. The speed eases toward the target at up to
0.5 m/s², the distances count down, the train moves block by block, and it
brakes to a stop at the end of its authority block.

## Layout

```
main.py                                    entry point: shared theme + scaling, controller, QML
train_controller/track_layout.py           loads green_line.json (IDs as strings, km/h to m/s)
train_controller/units.py                  backend to display conversions (truth factors)
train_controller/train_controller_state.py TrainControllerState: snapshot, slots, tick
tests/                                     unittest suites for the state and the loader
ui/Main.qml                                ScaledWindow, ModuleHeader, selector strip, pop-up host
ui/CabView.qml                             the three-column cab
ui/EngineerGainsPopup.qml                  Engineer-only Kp/Ki overlay
ui/components/                             local only: SignalAspectRow, TrackAhead, GainStepper
wireframe/                                 reference PNG and HTML wireframe (Figma import)
```

## Design discrepancies

1. **Doors while moving:** the original wireframe showed OPEN LEFT enabled at
   32 mph. Doors only open when stopped in a station block.
2. **Control gains moved:** the wireframe's CONTROL GAINS panel is an
   Engineer-only pop-up instead. Gain tuning is not part of the driver UI.
3. **Kp/Ki are not used yet:** they are stored and applied, but the
   simulation is a kinematic ease, not a PI loop.
4. **Release only when stopped** is an interim rule and may change.
5. **Routing:** the route is the contiguous ascending run of blocks 62–76.
   Switches and other routes are not modelled.
6. **Speed-limit source:** the layout file, until Track Info reaches the
   controller through the central harness (D005).
7. **Header controls:** the shared `ModuleHeader` has no slot for controls,
   so the Train / User / Mode selectors sit in a strip directly beneath it.
8. **Pop-up is an in-canvas overlay,** not a `QtQuick.Controls` `Popup`. A
   `Popup` would be drawn outside the scaled canvas and would not scale.
9. **Arrival time** is computed from the distance and current speed, and
   shows `—` when stopped.
