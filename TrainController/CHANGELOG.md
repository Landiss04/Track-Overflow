# Train Controller — Changelog

Notable changes to the Train Controller module. Newest entries first. Each
entry names the commits that make it up (by hash, or by subject where the
entry was written before the hash existed), so the history can be traced in
`git log -- TrainController/`.

## 2026-10-02 — Shared UI components, block-ID authority, real Green Line

Author: Jonathan Tsang · Branch: `Train-Ctrl_SW`

Commits: "Train Controller: load Green Line layout; authority as a block ID" ·
"Train Controller: rebuild the cab on shared ui/ components" ·
"Train Controller: update wireframe, README and changelog"

Brings the module in line with the `truth` branch (`AGENTS.md`) and the
shared component library in the repository-level `ui/` folder.

### Changed

- **Authority is a block ID**, per truth `conventions/units.md` and
  `identifiers.md`. The "To stop point" distance readout is replaced by an
  Authority readout (`76`). The stop point is the end of the authority block.
- **Real Green Line track:** new `train_controller/track_layout.py` loads
  `TrackModel/green_line.json` at startup (block IDs as strings, km/h to m/s).
  The seeded route runs from block 62 to authority block 76, through GLENBURY
  (65) and DORMONT (73). The speed limit now follows the occupied block.
- **Shared UI:** the cab is rebuilt on `ScaledWindow`, `ModuleHeader`,
  `Panel`, `TelemetryReadout`, `SafetyButton`, `SegmentedToggle`,
  `SelectField`, `FormField`, `TrackBlock`, `StatusBadge`, `KeyValueRow`,
  `Callout`, `AppButton` and `ValueField`. The theme and window scaling come
  from `ui/theme.py` and `ui/aspect_lock.py`. The local copies of theme,
  aspect lock and 16 components are deleted. Only `SignalAspectRow`,
  `TrackAhead` and `GainStepper` remain local.
- **Emergency brake:** the driver releases it, only once the train has fully
  stopped. The "office must release it" text and the test-only office release
  are removed.
- **Doors** open only when stopped in a station block, on that station's
  real platform side.
- **Engineer pop-up:** Kp/Ki can also be typed (`setKp` / `setKi`).
- **Units:** conversion factors updated to the truth values (2.236936,
  3.280840).
- **Toolchain:** PySide6 and PyInstaller now come from `TrainController/.venv`
  only, per truth `conventions/toolchain.md`.
- **Tests:** 36 cases (was 24), including a new `tests/test_track_layout.py`.

### Corrected

- The 2026-09-29 entry below originally named the branch `Track-Ctrl-SW`. The
  work lives on `Train-Ctrl_SW`.

## 2026-09-29 — Page 4 driver cab, first version

Author: Jonathan Tsang · Branch: `Train-Ctrl_SW`

Commits: `3050c73` wireframe · `d52e2d0` state, units and tests ·
`c7d84b6` QML UI, README and changelog

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
