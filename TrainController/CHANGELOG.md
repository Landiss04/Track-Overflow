# Train Controller — Changelog

Notable changes to the Train Controller module. Newest entries first. Each
entry names the commits that make it up, so the history can be traced in
`git log -- TrainController/`.

## 2026-09-29 — Page 4 driver cab, first version

Author: Jonathan Tsang · Branch: `Track-Ctrl-SW`

### Added

- **HTML wireframe** (`wireframe/page4_train_controller.html`): a
  self-contained, grayscale 1440×900 version of the page 4 cab mock-up for
  Figma import (html.to.design). Frame 2 (page 4c) is the new Engineer gains
  pop-up. The source PNG is kept beside it as the reference.
- **Controller state** (`train_controller/train_controller_state.py`):
  `TrainControllerState` exposes a display snapshot and one slot per driver
  action. A 1 s `step(dt)` tick eases speed toward the target, applies
  service (1.2 m/s²) and emergency (2.73 m/s²) braking, counts distances
  down, advances through the blocks, and stops the train at the end of its
  authority.
- **Unit conversions** (`train_controller/units.py`): SI state converts to
  mph, ft and °F per `common/Units.md`.
- **Tests** (`tests/test_train_controller_state.py`): 24 `unittest` cases
  covering speed targets, the Automatic lockout, brakes, doors, comfort
  controls, the tick, and gains.
- **QML UI** (`ui/`): a three-column cab styled with UI Style Guide v1.2
  tokens, and an Engineer-only Kp/Ki overlay (`EngineerGainsPopup.qml`).
  The generic components, theme and aspect lock are copied from
  `TrainModel/` so the two modules look and resize the same.
- **Dependency:** `PySide6==6.11.2` added to the root `requirements.txt`.

### Changed from the wireframe

- The CONTROL GAINS panel is removed from the driver view. Kp/Ki tuning
  opens as a pop-up when USER is set to Engineer.
- See README "Design discrepancies" for the full list: door interlock,
  unit case, computed arrival time, colour, and the test-only office
  release.

### Known limitations

- Kp/Ki are stored and applied but do not drive a PI control law yet.
- The route (GREEN I–N) and station are seeded placeholders, not read from
  `TrackModel/green_line.json`.
- The module is not connected to the Track Model, Train Model or CTC.
