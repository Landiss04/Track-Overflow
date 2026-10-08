# Train-Ctrl_HW — open issues for review

Found but not fixed. Each entry says what goes wrong and where, so it can be
picked up later. Last reviewed 2026-10-07 (code review of `Train-Ctrl_HW`).

## From the 2026-10-07 code review

1. **Driver target is not re-capped when the speed limit drops.**
   `main.py` — `ControllerCore.set_target_mps` caps the Manual target only when
   the driver sets it; `step()` and `enforce_safety()` never re-cap it. Manual,
   limit 43 mph, target 43 mph, then the limit drops to 25 mph: the train keeps
   holding 43 mph until the driver touches the dial.

2. **"Stop in N blocks" ignores a signal-pickup failure.**
   `main.py` — the snapshot reports the raw `authority_blocks`, while the
   controller acts on `ControllerCore.authority_blocks`, which is 0 during a
   pickup failure. The train is braked to a stand on no authority while the hero
   readout and the numbers drawer still say "Stop in 4 blocks", uncoloured.

3. **Half of the speed dial's dead zone requests full speed.**
   `ui_parts/components/SpeedDial.qml` — `valueFor` maps only the left half of the
   90° gap at the bottom to zero; the right half (270–315°) clamps to the limit.
   A press just right of bottom-centre in Manual commands line speed, not 0,
   contradicting the file's own header comment.

4. **The engineer hand-over can sign a driver in unasked.**
   `main.py` — `_retire_engineer` runs 1.5 s after commissioning and sets
   `operator = "driver"` unconditionally. Sign the console out (for example from
   the bench Operator row) inside that window and a driver is signed in anyway,
   unlocking Manual controls.

10. **The branch carries shared-file deletions and committed bytecode.**
    Commit `eb84435` (before this module work) deletes
    `documents/meeting_logs/*`, `WorkPackageTracking/WP1/deliverables-checklist.html`
    and `Utils/Track_Overlow_Logo.png`, moves `TrackModel/*.json` to
    `Track_layout/`, and commits `ui/__pycache__/*.pyc`, which every run
    rewrites. Merging the branch whole would apply all of that; take the module
    folder only (the merge guide's "rescue a folder" route) instead.

Items 5–8 from the same review are fixed (bench sends only edited rows;
inputs validated before any is applied; door and light tiles re-send; roster
signals only on change). Item 9 no longer applies: the signal head is back to
Ivan's sizing and the failure banners that squeezed it were removed
(2026-10-07).

## Carried over

- **Rolling resistance outside a brake failure** is open. It (C_rr 0.002)
  applies under a brake failure only, as a trial. The slow-down overshoot it
  once fixed is now fixed by the 0.05 m/s service band instead (35 → 30 mph
  settles at 30.02 mph).
- **Toy plant parameters differ from truth's Train Model**
  (`truth/modules/train-model.md`): 120 kW vs 480 kW, 51,433 kg vs about
  52,312 kg reference mass, Euler vs trapezoidal integration, rolling
  resistance only under a brake failure (C_rr 0.002).
- **The controller simulates the train itself** (truth D009 gives physics to the
  Train Model). `ControllerCore._plant()` is the stand-in until the Train Model
  is connected.
- **Station dwell (truth D007, 45 s) is not implemented**; truth does not say
  which module owns it.
- **Signal aspect has no truth entry** (truth's Track Signal carries only
  commanded speed and authority); a proposal exists on `Train-Ctrl_SW` only.
- **Authority as a block count** is pending the conflict proposals in
  `truth/_inbox/Train-Ctrl_HW/` (Kevin to resolve).
- **Service-brake amber and the 72 px hero readouts** (`brake_service` and
  `size_hero` in `main.py` `PENDING_TOKENS`) are pending the style-guide
  proposals in the same inbox.
- **Other sizes kept to Ivan's design but outside the style guide** (restored
  2026-10-07 at Jonathan's request): the speed and temperature dial figures are
  computed from the dial radius (`Math.max(32, r * 0.6)` and
  `Math.max(30, r * 0.66)`) rather than a token, and the door and light tiles
  are 52 px tall (the guide's control heights are 28 / 36 / 44) with
  Label-token text instead of the button type scale.
- **Local near-duplicates of shared components** — `ConsoleHeader`
  (ModuleHeader plus `alerts`), `HeroReadout`, `BrakeButton`, `SignalEditRow`,
  and the new `TrainPicker` — each needs a change to the shared `ui/` folder to
  retire or share.
- **Kp/Ki unit labels are SI** ("W per m/s", "W per m"); converting them changes
  the numbers engineers type.
- **The root `requirements.txt` on this branch lacks the PySide6 pin** that
  `development` has (`PySide6==6.11.2`).
