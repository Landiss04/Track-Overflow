# Train Controller UI (page 4, driver cab)

PySide6 + QML front-end for the ECE1140 Train Controller, covering the page 4
driver cab for T-214 on the Green Line. The controls a driver uses are live and
drive a light simulation. There is no PI control law and no Train Model yet.

QML owns all visuals and Python owns state. The two talk through the QML
context properties `theme` and `controller`, the same pattern as `TrainModel/`.

## Design sources

- **Wireframe:** `wireframe/page4_train_controller.png` is the reference.
  `wireframe/page4_train_controller.html` is the self-contained grayscale
  HTML version for Figma (html.to.design). Frame 1 is the cab. Frame 2
  (page 4c) is the Engineer gains pop-up.
- **Tokens:** every colour, font size, spacing, radius and control height
  comes from `documents/UI_Style_Guide.md` (light theme), via
  `train_controller/theme.py`.
- **Units:** state is kept in SI units and converted for display per
  `common/Units.md` (mph, ft, °F), in `train_controller/units.py`.

## Run

```bash
python -m pip install PySide6      # once
cd TrainController
python main.py
```

Tests:

```bash
cd TrainController
python -m unittest discover tests
```

Offscreen smoke test (no display needed). `QT_QPA_FONTDIR` is needed because
Qt's offscreen platform ships no fonts:

```bash
QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts timeout 6 python main.py
```

## What you can do

| Control | Effect |
|---|---|
| SLOWER / FASTER | Target ±1 mph, 0 to the speed limit. Locked in Automatic. |
| Use CTC target | Adopt the CTC's commanded speed. Locked in Automatic. |
| Service brake OFF/ON | Slows the train at 1.2 m/s² while on. |
| EMERGENCY BRAKE | Immediate, no confirmation (style guide §7). Latches, and the header shows an E-BRAKE badge. |
| Simulate office release (test only) | Appears only while the e-brake is on, and clears it. |
| OPEN / CLOSE LEFT, RIGHT | Only on the platform side and only when stopped. The train won't move with doors open. |
| Announce again | Shows the station announcement for 5 s. |
| COOLER / WARMER | Setpoint ±1 °F (60–80). The cabin temperature drifts toward it. |
| Cabin lights / Headlights | OFF / ON. |
| USER: Engineer | Opens the Kp/Ki pop-up. Close or Esc returns to Driver. |
| MODE: Automatic / Manual | Automatic hands the target to the CTC. |

The tick runs once per second. The speed eases toward the target at up to
0.5 m/s², the distances count down, the train moves up the track-ahead strip
block by block, and it brakes to a stop at the end of its authority.

## Layout

```
main.py                                   entry point: theme, controller, QML
train_controller/theme.py                 design tokens (copied from TrainModel)
train_controller/aspect_lock.py           16:10 resize lock (copied from TrainModel)
train_controller/units.py                 SI to display unit conversions
train_controller/train_controller_state.py TrainControllerState: snapshot, slots, tick
tests/test_train_controller_state.py      unittest suite for the state
ui/Main.qml                               window, scaled canvas, pop-up host
ui/CabView.qml                            the three-column cab
ui/EngineerGainsPopup.qml                 Engineer-only Kp/Ki overlay
ui/components/*.qml                       shared-style components; the generic ones
                                          are copied from TrainModel/ui/components
wireframe/                                reference PNG and HTML wireframe
```

## Design discrepancies

1. **Doors while moving:** the wireframe shows OPEN LEFT enabled at 32 mph.
   Here it is only enabled when the train is stopped.
2. **Control gains moved:** the wireframe's CONTROL GAINS panel is replaced by
   an Engineer-only pop-up, so gain tuning is not part of the driver UI. The
   right column's panels take up the freed height.
3. **Kp/Ki are not used yet:** they are stored and applied, but the
   simulation is a kinematic ease, not a PI loop.
4. **Office release is a test affordance,** not a driver control. It stands in
   for the CTC Office until that module is connected.
5. **Colour:** the wireframe is grayscale. The QML applies the style guide's
   accent and semantic colours (for example, the current block uses `--info`,
   the closed block `--warning`, and the e-brake `--danger`).
6. **Unit case:** the wireframe prints `MPH` / `FT`. The QML uses `mph` / `ft`
   exactly as in `common/Units.md` (style guide §6.5).
7. **Arrival time:** the wireframe shows `08:47` against a `21:26:35` clock.
   The QML computes the ETA from the distance and current speed, and shows `—`
   when stopped.
8. **Pop-up is an in-canvas overlay,** not a `QtQuick.Controls` `Popup`. A
   `Popup` would be drawn outside the scaled canvas and would not scale with
   the window.
