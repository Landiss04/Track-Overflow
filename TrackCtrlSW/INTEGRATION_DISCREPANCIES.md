# Track Controller (SW) — integration discrepancies

Where the software Track Controller disagrees with the CTC Office, the
Track Controller (HW), the Track Model, the shared catalog
(`common/interfaces.py`) and the `truth` branch.

First compiled 2026-10-08 at the `ctc-interfacing` merge; brought up to date
2026-10-14 against `Track-Ctrl-SW` after the other modules' branches were
merged, the module boundary was added (`track_ctrl/interface.py`), and the
startup gate was added. Sources are cited so each item can be checked.

Status key: **truth** = on the `truth` branch (decided). **proposed** = in
`truth/_inbox/` on a branch (not yet decided). **code** = what another module's
code does today. **decided** = decided by you in chat, so it is this module's
position; it is not yet on `truth` unless a proposal says so.

Tick an item when it is resolved. An item that is ticked but still names
someone else's work says what is left for them.

---

## A. Blocks integration outright

- [x] **A1. Units.** Speed is whole m/s inside the module; only the screen shows
  mph (**truth** `conventions/units.md`, D002).

- [x] **A2. Suggestions are addressed by block.** The CTC Office now sends
  `TrainSuggestion(train_id, line, block_id, suggested_speed_mps,
  authority_blocks)`: the block the train is in, with authority counted from it.
  A wayside cannot address a train, so the harness edge
  (`common/harness/ctc_edges.py`, `ctc_to_track_controller`) drops the train ID
  and hands this module one `Suggestion` per `BlockKey`, as HW does. Two
  suggestions for one block (the CTC's one-train-per-block rule should prevent
  it) take the more restrictive speed and authority. Left over: **truth**
  `signals/suggested-speed.md` and `suggested-authority.md` still say "keyed by
  train ID" until the CTC's proposals on `ctc-deployment` are promoted.

- [x] **A3. Module boundary.** `track_ctrl/interface.py` holds the boundary
  types and the `TrackController` Protocol (`step`, `snapshot`, `load_program`,
  `reset`); `module.py` is the Qt-free module; `wire.py` and `errors.py` follow
  the HW and CTC layout (**truth** D005, D008). Left over:
  - HW's Protocol also has `load_territory(Territory)`. Ours loads a layout
    with `load_track(LineLayout)`, which takes this module's own layout type, so
    it is not in the Protocol. If REQ-INTF-009 needs the two variants to expose
    the same interface, a shared territory type is needed.
  - The harness has no CTC ↔ Track Controller edge yet
    (`common/harness/` has only `track_model_edges.py`).

- [x] **A4. PLC gating.** Numbers never enter the program; `AUTH_n` per block
  passes block *n*'s suggestion or sends 0, as in HW (**proposed** D016).

- [ ] **A5. PLC I/O names still differ from HW.** The grammar is shared (HW
  adopted ours).

  | Meaning | Ours | HW |
  |---|---|---|
  | Occupancy | `OCC_n` | `OCC_n` |
  | Closed | `CLOSED_n` | `CLOSED_n` |
  | Authority gate | `AUTH_n` | `AUTH_n` |
  | Maintenance | `MAINT` | `MAINT` |
  | Switch command | `SW_n` | `SW_n` |
  | Crossing | `XING_n` | `XING_n` |
  | Signal aspects | `SIG_n_R/_O/_G/_SG` | `SIG_n_R/_Y/_G/_SG` |
  | Track failure | *(none, by decision: see C1)* | `FAIL_n` |
  | Switch read-back | `MOVING_n` (derived from read-back) | `SWREV_n` |
  | Switch fault | `FAULT_n` (never driven, see C2) | *(none)* |

  A program written for one variant is flagged line by line on the other for the
  names it lacks. Settling this is a team decision (D016), and the yellow suffix
  is B2.

---

## B. Contradicts a decision or a pending proposal

- [x] **B1. Authority.** Authority is per block and passes through unchanged. The
  vital layer no longer counts blocks ahead or truncates it, and maintenance no
  longer holds it (removed 2026-10-14): a wayside knows neither the route nor the
  direction of travel, so stopping authority before a hazard is the CTC's job
  (**truth** `arbitration/authority-stops-before-obstruction`). **proposed**
  below.

- [ ] **B2. Aspect output suffix.** The display name is YELLOW everywhere here,
  but the PLC output suffix is still `_O`; HW, the Track Model and the catalog
  use `_Y`. The earlier Orange/Yellow **conflict** in HW's
  `signal-light-command.md` is closed on our side; the suffix is the last piece
  (our own proposal `signal-yellow` records the decision). Rename it with A5.

- [x] **B3. Maintenance mode** belongs to the CTC Office; this UI shows it and
  cannot change it. The CTC now sends **no mode flag at all**, only switch
  commands (line, switch, position), so our `CtcInputs.maintenance_mode` was
  removed (2026-10-14). The module infers maintenance from a command in effect on
  a switch it governs. Still to confirm:
  - a dispatcher in maintenance who has commanded no switch yet looks like
    automatic mode to us; if that matters, the CTC would have to say so;
  - a hand-set switch yields to the CTC's command for the same switch (our
    choice);
  - HW still expects `ctc.maintenance_mode` (**code**), so HW disagrees with the
    CTC and with us; the harness cannot map a flag the CTC no longer has.

- [ ] **B4. Train identity.** **proposed** D015: the Track Controller shows no
  train IDs. The boundary now carries presence only and the stand-in trains live
  in the test UI, but block tiles still show a label for an occupied block
  (`TEST`); the label should go. Separately, the CTC expects a `TrainReport`
  with offset and speed from the Track Controller (**code**
  `ctc.interface.TrainReport`). **Decided:** it cannot have either, only block
  presence. That is the CTC's to change.

- [ ] **B5. One line or both.** **proposed** D014: HW runs every wayside of one
  line, SW the other. Ours loads Green and Red together. Not urgent
  (**decided**); which line is ours is also still open.

- [x] **B6. Territories are loaded**, not hard-coded: **Load track...** reads a
  `TrackModel/*.json` layout and divides it among a chosen number of waysides.
  HW's cut wayside databases (a `wayside` field) are refused with a message.

- [x] **B7. Identifiers.** A block is `BlockKey(line, block_id)` with the layout
  number as a string; a switch, its signal and a crossing are named by the block
  they are listed on (**truth** `conventions/identifiers.md`). Left over:
  - The UI's line name is `Green Line` where truth says `Green`; the boundary
    uses `Green`.
  - The Track Model's provisional `"GREEN D-13"` differs from truth (their item).
  - See E2 for the section letter.

---

## C. Inputs and outputs the neighbours provide or expect

- [ ] **C1. No failure input (decided).** The Track Controller sees a track
  failure only as an occupied block. Others still carry failures to it:
  HW reads `FAIL_n` and sends a failure per block in its `CtcReport`; the CTC
  has `TrackFailureReport` as an input from the Track Controller; the catalog's
  `TrackReadback.failures` goes to it. Our boundary has no such field, so the
  harness must drop it for SW, and **the CTC must learn of failures from the
  Track Model or not at all.** Also affects SRS REQ-FUNC-072.

- [ ] **C2. `FAULT_n` has no producer.** Nothing at the boundary drives it now,
  because no failures arrive. `MOVING_n` is derived: a switch whose actual
  position is not the one last commanded. Remove `FAULT_n` from the PLC image,
  or keep it for a future source.

- [x] **C3. Read-back of device states.** The boundary takes the Track Model's
  actual switch, crossing and signal states, and reports them to the CTC in each
  wayside's `CtcReport`. Only the switch read-back is acted on (a switch that
  did not follow is held at speed 0); the others are reported, not used by the
  vital layer.

- [x] **C4. Track heaters (decided).** The Track Model switches them from the
  temperature; the Track Controller neither commands nor reads them. Left over
  for the catalog and harness: `WaysideCommands.heaters_on` and
  `TrackReadback.heaters_on` / `track_temp_c` should be dropped for this module.

- [x] **C5. Report to the CTC.** One `CtcReport` per wayside per tick, with per
  block occupancy and the Track Model's own switch, crossing and signal
  read-back. It carries no failure (C1) and no train (B4).

- [ ] **C6. Signal placement.** Ours and HW: one signal at every switch, named
  after the block it is on. Track Model: signals stand on the block **before**
  each switch. HW and the Track Model disagree with each other too.

- [x] **C7. Commanded speed** is a whole number of m/s.

---

## D. Repository conventions

- [ ] **D1. Toolchain drift.** **truth** `conventions/toolchain.md` needs
  PySide6 ≥ 6.11 and PyInstaller ≥ 6.22.2. Ours has PySide6 6.8.3 and no
  PyInstaller.

- [ ] **D2. Copies of shared UI components.** The CTC README: "Do not copy
  shared components into this module; change them in `ui/`." We have our own
  `AppButton`, `StatusBadge`, `SegmentedToggle`, `Panel`, `MonoText`,
  `FieldLabel`, `SignalRow` and `theme.py`.

- [ ] **D3. Linting.** The convention is `flake8 --max-line-length=79` (72 for
  docstrings), pylint and pep8-naming (**truth** `files-and-paths.md`). We only
  run mypy.

- [ ] **D4. Truth proposals.** In `truth/_inbox/Track-Ctrl-SW/` now:
  `signal-yellow`, `test-ui-clock`, `vital-restrictions`, and two new ones
  (`track-controller-ready`, `track-controller-vital-restrictions`, and `track-controller-ready-per-wayside`, which supersedes the first).
  **`vital-restrictions` is out of date** (it records the maintenance hold and
  authority truncation, both removed); the new proposal supersedes it. Only a
  human edits or deletes an existing proposal, so it is left as it is for you to
  withdraw.

---

## E. New with the boundary and startup

- [ ] **E1. A startup gate and a `ready` signal.** The module is not ready until
  a line is loaded and every wayside has a PLC program; until then no program
  runs and every output is fail-safe. Readiness is **per wayside and per
  line**: each `CtcReport` carries `line`, `ready` and `reason`, so the CTC sees
  which waysides are not ready. `TrackControllerOutputs.ready` is derived (all
  ready). The CTC must not dispatch or send a speed or authority on any line
  until every wayside is ready.
  - Neither the CTC, HW, the catalog nor the harness has anything like it. HW
    has the same startup (it loads territories and programs) but reports no
    readiness.
  - Truth proposal: `signals/track-controller-ready`.
  - Needs the CTC to wait, HW to report it too, and the harness to map it. Whether
    the harness also holds the clock until every module is ready is open.

- [ ] **E2. Section letter in the block key.** Ours leaves it out (**decided**,
  still disputed). HW's `BlockKey` has `(line, section, block_id)`; the CTC and
  truth use `(line, block_id)`. The harness has to add or drop it per edge.

- [ ] **E3. The shared catalog is stale for this module.**
  `common/interfaces.py` still has `ISwTrackController` in the old
  single-signature style (`receive_suggestion(block_id, ..., authority_block_id)`
  with an authority **block ID**, against D013's count); the truth shard
  `track-controller-sw.md` is a placeholder pointing at it, which D008 says
  modules never import. `WaysideCommands`/`TrackReadback` are the live types.

- [ ] **E4. Vital rules and the truth record.** The restrictions this module
  enforces are now in one proposal (`track-controller-vital-restrictions`). Some
  overlap `arbitration/` entries already on truth (`no-switch-under-train`,
  `block-closure`, `suggested-speed-under-block-limit`); the proposal links them
  instead of restating them.

---

## Already consistent

- Shared simulation clock: the test UI runs `utils.SystemClock` at a fixed 0.1 s
  tick, 05:00:00 start, 1× / 10×; the module is stepped with `dt` and the time
  (D006, D017).
- Boundary shape: own types, `step(dt, inputs) -> outputs`, `snapshot()`, a
  strict `wire.py`, one base error, as HW and the CTC (**truth** D005, D008).
- Test UI: a separate process over a local named pipe, using the same
  `step`/`outputs`/`busy` pattern as the Train Model and HW, standing in for the
  CTC, Track Model and clock.
- PLC grammar: HW adopted ours (**proposed** D016).
- The vital layer only restricts, as in HW.
- Authority unit is blocks, passed through (D013).
- Closed blocks are never overridden; the CTC owns maintenance mode (**proposed**
  `maintenance-closure-lock`).
- Suggestions are per block: a block with none sends nothing, as in HW.
