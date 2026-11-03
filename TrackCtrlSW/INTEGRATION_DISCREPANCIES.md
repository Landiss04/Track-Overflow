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
  - The harness's edges are `common/harness/wayside_edges.py`, on each
    module's JSON form: CTC Office → Track Controller, Track Model ↔ Track
    Controller, and Track Controller → CTC Office (Phase 3). The typed
    `common/harness/ctc_edges.py` is off the running path and stays for this
    module's tests.

- [x] **A4. PLC gating.** Numbers never enter the program; `AUTH_n` per block
  passes block *n*'s suggestion or sends 0, as in HW (**proposed** D016).

- [x] **A5. PLC language and I/O names now match HW's** (2026-10-20, so one
  program file runs on either variant, REQ-INTF-009). Checked, not assumed:
  `tests/test_hw_language.py` compiles the same text with both implementations
  and compares errors, expanded names and scan results (1,200 random programs
  plus edge cases), and runs HW's own sample programs on an equivalent software
  territory. Findings:
  - The grammar already matched. One rule differed: a letter range such as
    `OCC_a..d` is case-preserving and both ends must be the same case. Fixed.
  - Names are now HW's: inputs `OCC_n`, `CLOSED_n`, `FAIL_n`, `SWREV_s`, `MAINT`;
    outputs `AUTH_n`, `SW_s`, `SIG_s_R/_Y/_G/_SG`, `XING_c`. `FAULT_s` and
    `MOVING_s` are gone, the yellow suffix is `_Y`, and the vital code's own bits
    (`CTCCMD`, `HAND` ...) cannot be declared by a program.
  - **Open:** `FAIL_n` is in the image but always 0 here (**decided**: this
    wayside is told of no failures), so a HW program that reacts to `FAIL_n` runs
    but never sees one. The two variants behave the same only when a failed
    block reads occupied, as the Track Model reports it.
  - **Not copied, on purpose:** HW compiles every statement twice by different
    algorithms and treats a disagreement as a latched vital fault. That is
    implementation, not language; the variants share a language, not code, to stay
    diverse. If the SRS wants the dual-channel check in this variant too, it
    should be written separately, not copied.
  - **Open:** HW's vital layer is still Python and still clamps speed and
    truncates nothing; ours is PLC code attached to every program and has no
    numeric rule (clamping and zero-authority-zero-speed are the CTC's). A
    program behaves the same on both only where the CTC keeps speeds under the
    limit.

---

## B. Contradicts a decision or a pending proposal

- [x] **B1. Authority.** Authority is per block and passes through unchanged. The
  vital layer no longer counts blocks ahead or truncates it, and maintenance no
  longer holds it (removed 2026-10-14): a wayside knows neither the route nor the
  direction of travel, so stopping authority before a hazard is the CTC's job
  (**truth** `arbitration/authority-stops-before-obstruction`). **proposed**
  below.

- [x] **B2. Aspect output suffix.** Now `_Y`, as HW (2026-10-20).
  (Was: The display name is YELLOW everywhere here,
  but the PLC output suffix is still `_O`; HW, the Track Model and the catalog
  use `_Y`. The earlier Orange/Yellow **conflict** in HW's
  `signal-light-command.md` is closed on our side; the suffix is the last piece
  (our own proposal `signal-yellow` records the decision). Rename it with A5.)

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

- [x] **C6. Signal placement.** Confirmed by Harry Tye 2026-10-28: one signal per
  switch, at its point, named by the switch, and facing the oncoming train (TM-2,
  `86f4658`). Before:
  Ours and HW: one signal at every switch, named
  after the block it is on. Track Model: signals stand on the block **before**
  each switch. HW and the Track Model disagree with each other too. The harness
  maps each light through its switch (`common/harness/track_devices.py`): ours by
  the switch's block, the Track Model's by the block the light stands on. Whether
  that mapping is right is open with both owners. Under the starter program a
  train leaving the yard sees the yard switch's light YELLOW, from a light that
  faces away from it (`TrackModel/BUGS.md` B1).

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
  - Since Phase 3 the harness maps it: `wayside_edges.track_controller_to_ctc`
    puts each wayside's readiness in the CTC Office's input, and the harness logs
    `WAYSIDES_NOT_READY` and `WAYSIDES_READY`. It gates the harness's scripted
    CTC Office, which releases no train and sends nothing for a line until the
    line is ready. Readiness does not hold the clock (R71). Left: HW.

- [ ] **E2. Section letter in the block key.** Ours leaves it out (**decided**,
  still disputed). HW's `BlockKey` has `(line, section, block_id)`; the CTC and
  truth use `(line, block_id)`. The harness has to add or drop it per edge. For
  this module it is settled at the harness: the edges use `(line, block_id)`,
  without the section letter, as the CTC Office does. Left: HW's section keys
  (Phase 5).

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

- [ ] **E5. Starter program separation rule (for the owners to review).** The
  starter held every block beside an occupied one, including the empty next
  block the CTC Office preloads for the train about to enter it (R49, truth
  `track-signal`). A train then read speed 0 and authority 0 at every block it
  entered, and the Train Controller latched a pickup failure. Changed in Phase 3
  in `track_ctrl/controller.py`: only a block with a train in it is held,
  `AUTH_n := NOT (OCC_n AND (OCC_n-1 OR OCC_n+1))`. Two trains side by side are
  still both held, and stay held: the starter cannot tell direction.

- [ ] **E6. Switch dialog signals renamed (for the owners to review).**
  `SwitchDialog.qml`'s `applied` signal clashed with `Dialog.applied()`, and
  PySide6 6.11 warned on every launch. The harness's tests need an empty stderr.
  Renamed in Phase 3 to `switchApplied`, and `released` to `switchReleased`, with
  `ProgramView.qml` and `StatusView.qml`. The warning did not stop the signal
  working.

- [ ] **E7. Starter program switch rule: a train can get back to the yard (Q7;
  for the owners to review).** The starter threw a switch reverse only while a
  train stood on its reverse leg in the same wayside, and wrote `SW_n := 0`
  otherwise. Green 28 (`28-29; 150-28`, reverse leg 150 in GTC-06) and 76
  (`76-77;77-101`, reverse leg 101 in GTC-05) never left normal, and the CTC
  Office counts authority only up to a switch not set for the route, trailing
  moves included: a train coming back round the line waited at 77, then at 150,
  for good, and never reached the yard entry block 57. Changed on 2026-10-21 in
  `track_ctrl/controller.py`, `track_ctrl/layout.py`:
  - **Two new PLC inputs.** *(Withdrawn 2026-10-22: they were not HW's names,
    so one program no longer ran on both variants, REQ-INTF-009. The inputs are
    HW's again, `OCC_n`, `CLOSED_n`, `FAIL_n`, `SWREV_s`, `MAINT`; the starter
    uses `SWREV_s` where it used `REV_s` and no longer reads a suggestion, so it
    cannot tell which way a train on a leg is heading.)* `SUG_n`: the CTC Office
    sends a suggestion for block `n` (with no train in it, it is the next block
    of the train about to enter it, truth `track-signal`). `REV_s`: switch `s`
    stands reverse as this controller last drove it.
  - **The direction of travel.** Every controller carries its line's
    `next_blocks` from the layout file, for the starter only.
  - **The rule** (see the README, design decision 6): set each switch for the
    train coming to its points, facing (`NOT OCC_p AND OCC_f`; was
    `SUG_p AND NOT OCC_p AND OCC_f`) or trailing off a one-way leg (`OCC_l`;
    and the block before it where the leg is the block the switch is listed
    on); stand for a way in the wayside cannot see (Green
    28 stands reverse); hold the switch where it stands while its points are
    occupied or trains come for both positions; normal in maintenance unless
    held. The vital layer is unchanged.
  - **The Green route, yard exit 63 round to 57:** switch 76 normal for 76 to 77
    and reverse for 78 to 101; 85 normal for 85 to 86 and reverse for 100 to 85;
    28 reverse for 150 to 28 and normal for 28 to 29; 12 normal for 13 to 12 and
    reverse for 1 to 13. 58 and 62 stay normal: retirement is a stop at 57 with
    authority 0 (D022), and no route enters the yard.
  - **Left for the owners** (Harry Tye):
    - The vital switch lock is on the block a switch is listed on. For Green 12,
      58, 62 and 76 that is a leg, not the points (13, 57, 63, 77). The starter
      now holds a switch while its points are occupied, but a program that does
      not is not stopped by the vital layer, and a train on 76 locks switch 76
      though it is not on it. A train about to enter 76 while another stands on
      77 bound for 101 enters 76 with the switch reverse and waits there for good.
      Locking on the points block as well would be more restrictive, not less;
      moving the lock off the listed block would be less restrictive and would
      clear that case. Not changed here. The waiting case is closed from the
      CTC side instead (Landis and Harry Tye, 2026-10-28, relayed by Kevin): the
      CTC counts a switch's blocks as next to each other whatever position it
      reports, so a follower stays on 75 while a train is on 77. The lock is
      unchanged, and the points-block question for a user program stays open.
    - A way in from another wayside's block is not seen. Green's default
      division has only one (150 to 28), which switch 28 stands for. Another
      division can have more; a cross-wayside input (the neighbour's occupancy
      of the leg) would serve them and is a boundary change.
    - The Red Line runs both ways, so the starter cannot tell a train's
      direction from occupancy there, and its switches stay normal.
  - Tests: `tests/test_starter_switches.py` (18), `tests/test_layout.py` (+2);
    harness `test_harness_train_loop.py` `ReturnToYardTest` (5, about 140 s,
    run with `TRACK_OVERFLOW_ROUND_TRIP=1`): a scheduled Green run to DORMONT
    and on round the line, retired once at 57.
  - **Not this module's, and blocking the round trip today:** at Green 93 the
    Train Controller latches an engine failure while holding a steady 5 m/s up
    the grade (its detector wants the speed to rise within 2 s while power is
    on) and applies the emergency brake, so no train gets past 93 in the full
    system, with or without this change. With that detector held off, the round
    trip passes; with the old starter it then stops at 77 for good.

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
