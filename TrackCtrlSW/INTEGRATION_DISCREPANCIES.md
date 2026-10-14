# Track Controller (SW) — integration discrepancies

Where the software Track Controller disagrees with the modules merged from
`ctc-interfacing` (CTC Office, shared `ui/`, `utils/`) and with the Track
Controller (HW) and Track Model READMEs, and with the `truth` branch.

Compiled 2026-10-08 against `Track-Ctrl-SW` at the `ctc-interfacing` merge.
Sources are cited so each item can be checked. **Nothing here is decided**:
each is a question for you, usually with the other module's owner.

Status key: **truth** = on the `truth` branch (decided). **proposed** = in
`truth/_inbox/` on another branch (not yet decided). **code** = what another
module's code does today.

Tick an item when it is resolved.

**Update:** the block-level rework resolved A1, A4, B1, B3, B6, B7 and C7, and
moved A2, A5 and B2 part of the way. Each item carries a `Status` line saying what
changed and what is left. A3 (the `step` boundary), B4, B5, C1 to C6 and D1 to D4
are untouched.

---

## A. Blocks integration outright

These stop the module being wired into the central harness at all.

- [x] **A1. Speed is in mph inside the module; the system is metric.**
  - **Status:** Done: speeds are whole m/s inside the module; only the screen shows mph.
  - Us: suggested and commanded speed are `float` mph end to end
    (`ControllerInputs.suggested_speed_mph`, the 5 mph PLC speed code).
  - Them: backend units are m/s everywhere; only UIs show mph (**truth**
    `conventions/units.md`, D002). The CTC sends `suggested_speed_mps: int`
    (**code** `CTC-Office/ctc/interface.py`). HW and Track Model use whole m/s
    (**code**, both READMEs).
  - Fix: store and exchange m/s (int), convert to mph only in `state.py` /
    QML.

- [ ] **A2. One suggestion per controller; everyone else keys it differently.**
  - **Status:** This module is now per block, as HW and D015 want. The CTC Office still sends per train, so the harness must map a train to the block it occupies.
  - Us: one suggested speed and one authority for a controller's whole
    territory.
  - CTC: one per **train** (`TrainSuggestion.train_id`) — and **truth**
    `signals/suggested-speed.md` / `suggested-authority.md` say "keyed by train
    ID".
  - HW: one per **block** (`ctc.suggestions: {block: Suggestion}`), and
    **proposed** D015 says the Track Controller "knows the blocks it governs,
    never the trains", so suggestions must be per block.
  - CTC and HW disagree with each other too. Needs a team decision; the HW
    position (per block) fits a wayside that only sees track circuits.

- [ ] **A3. No module boundary (`step(dt, inputs) -> outputs`).**
  - Us: the UI state object drives the controllers; the stand-in world lives
    inside `system.py`. There is no typed input/output boundary.
  - Them: each module defines its own boundary types and a `step(dt, inputs)`
    the harness calls (**truth** D005, D008). HW: `TrackController` Protocol
    with `step`, `snapshot`, `load_territory`, `load_program`, `reset`. CTC:
    `step(dt, inputs) -> outputs`.
  - REQ-INTF-009 requires the HW and SW Track Controllers to expose
    equivalent interfaces, so adopting the HW Protocol shape is the obvious
    route. The class diagram in `documents/uml/` shows a realization of
    `ISwTrackController` that the code does not have yet.

- [x] **A4. PLC programs are not portable between the two variants.**
  - **Status:** Done for the gating: numbers no longer enter the program, and each block has an `AUTH_n` bit as in HW. The remaining name differences are in A5.
  - Us: speed and authority enter the program as 4-bit vectors
    (`SUG_SPEED_0..3`, `CMD_AUTH_0..3`).
  - HW: numbers never enter the program; `AUTH_n` per block decides whether
    block *n* passes the CTC's suggestion (1) or sends 0 (0) (**code** HW
    README). **Proposed** D016: "one program file format serves both
    variants … speed and authority are numbers and do not enter the program."
  - The grammar is shared already (HW adopted ours). The I/O is not, so a
    program written for one variant does not compile on the other.

- [ ] **A5. PLC I/O names differ.**
  - **Status:** Aligned now: `OCC_n`, `CLOSED_n`, `AUTH_n`, `SW_n`, `XING_n`, `SIG_n_*`, `MAINT`. Still different: HW has `FAIL_n` and `SWREV_n` where this module has `FAULT_n` and `MOVING_n`, and the yellow aspect's output suffix (`_O` here, `_Y` in HW).

  | Meaning | Ours | HW |
  |---|---|---|
  | Occupancy | `OCC_n` | `OCC_n` |
  | Closed | `CLOSED_n` | `CLOSED_n` |
  | Track failure | *(none)* | `FAIL_n` |
  | Switch reversed (read-back) | *(none)* | `SWREV_n` |
  | Switch fault / mid-throw | `FAULT_SWxx`, `MOVING_SWxx` | *(none)* |
  | Maintenance | `MAINT_HOLD` | `MAINT` |
  | Switch command | `SW_SWxx` | `SW_n` |
  | Signal aspects | `LT_LTxx_R/_O/_G/_SG` | `SIG_n_R/_Y/_G/_SG` |
  | Crossing | `XING_XGxx` | `XING_n` |
  | Speed / authority | `SUG_*`, `CMD_*` bit vectors | `AUTH_n` gate |

  Device names follow from A9: HW names a device by the block it is on.

---

## B. Contradicts a decision or a pending proposal

- [x] **B1. Authority is counted from the wrong place.**
  - **Status:** Done: speed and authority are per block, so nothing is counted from the wrong place. The vital layer no longer truncates authority at an occupied block; like HW it has no train direction, and the CTC stops authority before an obstruction (truth proposal).
  - **truth** D013: authority is the number of blocks ahead of **the train's
    current block**, along its route.
  - Us: the vital layer truncates authority counting from the controller's
    **first owned block**, not from where a train is (`vital.supervise`). The
    4-bit code also caps it at 15 blocks.
  - Follows from A2: once suggestions are per block, authority per block
    needs no train.

- [ ] **B2. Aspect names: ORANGE vs YELLOW.**
  - **Status:** The display name is now YELLOW everywhere in this module. The PLC output suffix is still `_O`; HW uses `_Y`.
  - Us: RED, **ORANGE**, GREEN, SUPER GREEN.
  - HW, Track Model and `common/interfaces.py` `SignalAspect`: RED,
    **YELLOW**, GREEN, SUPER GREEN.
  - **proposed** `signal-light-command.md` (HW branch) records this as an open
    **conflict** naming our README as the ORANGE source; resolution owner
    Braden. It came from your original brief ("red, orange, green and super
    green"). Your call to concede or argue it.

- [x] **B3. Who owns maintenance mode.**
  - **Status:** Done: the CTC Office owns maintenance mode; this UI shows it and cannot change it. Maintenance no longer holds authority. Still to confirm with the CTC owner: a hand-set switch yields to the CTC's command for the same switch.
  - Us: the programmer enters maintenance from the Track Controller's top bar,
    then hand-sets switches in a dialog. (This is what your original brief
    asked for.)
  - **proposed** `maintenance-mode.md` (HW branch): "The CTC Office controls
    maintenance mode; the Track Controller obeys it and has no control of its
    own to enter or leave it." In maintenance, switches follow the **CTC's**
    switch commands, not the programmer.
  - CTC code: sends `switch_commands` only in maintenance and closes blocks,
    and its README says "the mode itself is not sent to the Track Controller"
    (**proposed** `maintenance-mode-superseded`). HW expects a
    `ctc.maintenance_mode` bool. **CTC and HW disagree with each other here
    too.**
  - Also differs: we hold authority at 0 for the whole controller in
    maintenance; HW keeps the program setting signals, crossings and
    authority.

- [ ] **B4. The controller knows trains; the decision says it must not.**
  - **proposed** D015: the Track Controller "shows no train IDs" and "reports
    no train identity, location or speed".
  - Us: block tiles show train IDs (`T-101`, `TEST`), and `system.py` moves
    trains. (The stand-in trains can stay as test scaffolding; the IDs on
    tiles should go.)
  - Separately, the CTC expects `TrainReport`s from the Track Controller
    (**code**), which D015 rules out; that is CTC vs HW, not us.

- [ ] **B5. One line or both.**
  - **proposed** D014: the HW Track Controller runs every wayside of one line,
    the SW Track Controller every wayside of the other.
  - Us: both lines, 11 controllers. Which line is ours is not decided (D014
    leaves it open).

- [x] **B6. Territories are hard-coded, not loaded.**
  - **Status:** Done for full layouts: **Load track...** reads `TrackModel/*.json` and divides it among a chosen number of waysides. HW's cut wayside databases (a `wayside` field) are refused with a message, not loaded.
  - **proposed** D014: a wayside's territory is loaded from a database file in
    the Track Controller UI. HW loads `data/waysides/*.json`, cut from
    `TrackModel/green_line.json`.
  - Us: `layout.build_default_system()` generates a synthetic network: even
    partitions, invented switch/signal/crossing positions, cycling speed
    limits, invented station names. Nothing matches the real track.

- [x] **B7. Identifiers.**
  - **Status:** Done for blocks and devices: a block is its layout number, and a switch, signal and crossing are named by the block they are listed on. The display name is still `Green Line` where truth says `Green`.
  - **truth** `conventions/identifiers.md`: a block is `(line, block_id)` with
    `block_id` the layout file's block number as a string (`"Green"`, `"12"`);
    a switch is named by the block it is listed on (`"12"`).
  - Us: `"G013"`, `"SW01"`, `"LT01"`, `"XG01"`, `"GTC-01"`.
  - Track Model's provisional block format `"GREEN D-13"` differs from truth
    as well (their item, noted for completeness).

---

## C. Missing inputs or outputs the neighbours provide or expect

- [ ] **C1. No track-failure input.** The Track Model reports broken rail,
  track circuit and power failures per block (**code** edges); HW reads them
  as `FAIL_n` and fails safe (speed 0, authority 0, crossing active). We have
  no failure input at all (also SRS REQ-FUNC-072).

- [ ] **C2. Our switch FAULT / MOVING inputs have no producer.** Nobody
  reports them. The Track Model reports **actual switch positions**; HW
  treats "switch not at its commanded position" as the fault. Replace ours
  with a position read-back.

- [ ] **C3. No read-back of actual device states.** The Track Model returns
  the actual switch positions, crossing states and lamp aspects
  (`TrackReadback`); HW reports those to the CTC rather than its own
  commands. We report commands and read nothing back.

- [ ] **C4. Track heaters.** The Track Model expects the Track Controller to
  command heaters per section and reads back heater state and track
  temperature (**code** `WaysideCommands.heaters_on`, `TrackReadback`). We
  have none. (Flagged when the test UI was built; still open.)

- [ ] **C5. Report to the CTC is occupancy only.** HW sends a `CtcReport` per
  wayside per tick: per block occupied, failure, switch position, signal
  aspect, crossing. The CTC wants occupancy, switches, crossings and failures
  (`TrackControllerInputs`). We expose occupancy (and only in the log/UI).

- [ ] **C6. Signal placement.** HW: one signal at every switch and nowhere
  else, named after it (`SIG-12`). Track Model: signals stand on the block
  **before** each switch. Ours: one generated signal per controller, mid-way
  through its territory, unrelated to any switch. (HW and Track Model also
  disagree with each other.)

- [x] **C7. Commanded speed rounding.** Track Model and HW: commanded speed is
  - **Status:** Done: commanded speed is a whole number of m/s.
  a whole number of m/s, rounded down. Ours: multiples of 5 mph. Resolves with
  A1.

---

## D. Repository conventions

- [ ] **D1. Toolchain drift.** **truth** `conventions/toolchain.md` needs
  PySide6 ≥ 6.11 and PyInstaller ≥ 6.22.2 in the venv. Ours has PySide6
  6.8.3 and no PyInstaller.

- [ ] **D2. Copies of shared UI components.** The CTC README: "Do not copy
  shared components into this module; change them in `ui/`." We have our own
  `AppButton`, `StatusBadge`, `SegmentedToggle`, `Panel`, `MonoText`,
  `FieldLabel`, `SignalRow` and our own `theme.py`; the shared ones now live
  in the repo-root `ui/`.

- [ ] **D3. Linting.** The repo convention is `flake8 --max-line-length=79`
  (72 for docstrings), plus pylint and pep8-naming
  (**truth** `files-and-paths.md`). We only run mypy.

- [ ] **D4. Truth proposals.** `AGENTS.md` expects each branch to propose
  the facts it settles in `truth/_inbox/<branch>/`. `Track-Ctrl-SW` has
  none, so the SW variant's positions (ORANGE, programmer-owned maintenance,
  vital rules) are invisible to the other teams except through this README.

---

## Already consistent

- Shared simulation clock: now runs on `utils.SystemClock` at a fixed 0.1 s
  tick, 05:00:00 start, 24-hour display, 1× / 10× (D006, D017).
- PLC grammar: HW adopted ours (**proposed** D016).
- Closed blocks are never overridden: closure turns a signal red and cuts
  authority (`maintenance-closure-lock`, proposed by CTC).
- Separate, kept test UI over a local named pipe, standing in for the CTC,
  Track Model and clock — the same pattern as CTC and HW (**proposed** D018).
- The vital layer only restricts, as in HW.
- Authority unit is blocks (D013), though counted from the wrong place (B1).
