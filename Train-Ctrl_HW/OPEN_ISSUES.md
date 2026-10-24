# Train-Ctrl_HW — open issues for review

Found but not fixed. Each entry says what goes wrong and where, so it can be
picked up later. Last reviewed 2026-10-24 against `cfba866`
(`REQUIREMENTS.md` M0–M20, revisions R2–R37; M5 is merged into M3).

## Resolved 2026-10-21

- **11. Block lengths unknown; overrun above 34.6 mph.** Authority is used
  as given (M16): the toy plant no longer counts blocks, and the bench's
  Block change button sends the next count. Stopping at the right block
  is the rest of the system's, which lowers the commanded speed in time
  (M17).
- **14. How a failure clears once integrated.** Decided: the controller
  detects resolution from the returned signals, in both modes (M3, §4). Building it is blocked on #23.
- **17. No block-change dummy.** The controller needs none: the Train
  Model's block change goes to the Track Model, which sends the next
  count (`development` `TrainModel/train_model/interface.py`:
  `block_changed` is in `TrackOutputs` only). The bench's Block change
  button stands in for it (R13).
- **22. Harness-spawned trains are never armed.** Decided: the engineer
  commissions every train, once, at the start; defaults are never applied
  on their own (M9). Harness trains wait at 0 W until then, as now.
- `old_main.py` (was in #20) was removed in `c98393e`.
- **26 (most of it). The bench's simulation lived inside the
  controller.** Moved to `bench_sim.py` (R15): the bench now steps the
  fleet through `step_all`, its edits go to the simulation, and the
  controller sees them on the next tick. What is left is the choice of
  simulator, below.
- **Emergency echo** (`HARNESS_INTEGRATION.md`): fixed with #25's
  controller side (R16).
- **18. Automatic lights** are built (R20, M8).
- **29. The dial's 70 km/h scale against M1.** Decided (R29, M14): the
  dial keeps its 70 km/h scale as display only, not a cap; a commanded
  speed above 43.5 mph cannot be set from the dial, and that is accepted.
- **31 (first bullet). The bench clock** now starts at the first
  commissioning and then always runs, whichever train is selected (M11,
  R37).

## Added 2026-10-15

- The toy plant's service brake state reads false during a failed service
  brake, as the real Train Model's does (`development`
  `TrainModel/docs/physics.md` §4). Unlike the Train Model, it does not
  also read false while the e-brake is engaged (#23).

## Added 2026-10-16 (requirements review, `REQUIREMENTS.md`)

16. **The engineer hand-over can still sign a driver in unasked.**
    `train_ctrl/backend.py` — `_retire_engineer` runs 1.5 s after
    commissioning and sets `operator = "driver"` unconditionally, on
    whichever train is selected by then. Sign the console out inside that
    window and a driver is signed in anyway, unlocking Manual controls.
    Select an uncommissioned train inside it and a driver is signed in to
    that train, against M9 (no driver before the gains).

19. **Module rules are not recorded outside this folder.** Rules M0–M20
    in `REQUIREMENTS.md` are in neither truth's Train Controller contract
    (still a placeholder) nor the SRS. Update the documentation later.

20. **Leftovers on this branch.** `ui/__pycache__/*.cpython-314.pyc` is
    committed; flake8 reports 42 lines in this folder (15 are the
    deliberate re-exports in `__init__.py`; the rest are missing final
    newlines, blank-line spacing, long doc lines and an unused variable in
    `harness_sim.py`).

21. **The self-check is timing-sensitive.** Several `check.py` sections
    wait on wall-clock deadlines (`_until`) while the control timer runs.
    On a loaded machine the timer is starved and checks fail that pass
    alone: on 2026-10-16 a run started straight after another reported 9
    failures in the failure-handling section, and the same code then
    passed with 0 in 34 s. Run `--check` on its own; a fix would step the
    controller directly instead of waiting on the timer.

## Added 2026-10-21 (controller / test bench separation)

23. **Brake and engine resolution cannot be seen while the emergency brake
    is on.** Blocks M3. On detection the controller latches the
    e-brake, and the pills are meant to clear before the driver releases
    it. But on `development` (`TrainModel/docs/physics.md` §3–4):
    - the Train Model reports the service brake as **not engaged whenever
      the e-brake is engaged**, so a repaired service brake never reads
      applied;
    - the e-brake force (about 140 kN) is far above full traction (about
      25.7 kN), so a repaired engine can never show rising speed.

    Signal pickup is unaffected (a non-zero Track Signal can return at any
    time). Decided in part (R29, M2, M3): once the train stands, the
    driver may release the e-brake in Manual with the failure still
    latched, and the failure does not engage it again. That lets a
    repaired service brake read applied, since the driver may command it
    under a brake failure (M4, R32); nothing yet concludes from that
    reading that the brake is resolved. It does not settle the engine: a latched
    failure keeps the target at 0, so no power is commanded and §4's
    "commanded power gives rising speed again" cannot happen. Candidate
    approaches for the rest, none chosen:
    - (a) Once stopped, hold an engine failure on the service brake
      instead of the e-brake, and probe with power.
    - (b) Once stopped, briefly drop the controller's e-brake command and
      probe: command the service brake for a brake failure, a little power
      for an engine failure. Risk: rollback on a grade.
    - (c) Ask Kevin to report the service brake's state independently of
      the e-brake.

24. **The Train Model passes a speed limit to the controller.** It is in
    the code, not a stray document: `ControllerOutputs.speed_limit_mps`,
    passed through from `TrackInfo` (`development` `de7a98f`,
    `TrainModel/train_model/interface.py`, `docs/module-interface.md` §5).
    The controller ignores it (M1; `read_inputs` drops unknown keys). To
    settle with Kevin: drop it from `ControllerOutputs`, or have the
    harness not map it.

25. **The passenger e-brake after the driver releases it.** Decided (M2):
    the driver's release overrides the passenger state. The controller
    side is done (R16): only a turn on of the emergency brake state, while
    the controller is not commanding it, is a pull, so a held report no
    longer re-latches it. Still open:
    - The Train Model's passenger latch is cleared only by a test-only call
      (`clear_passenger_brake_for_test`), so it keeps reporting the
      e-brake engaged after the release; agree with Kevin what it should
      report.
    - A pull reported within a tick or two of a release, before the
      reported state has gone false, is not seen.
    - The bench's passenger pull is reported for one tick only, not
      latched as the Train Model's is.

26. **Which simulator the bench uses.** The bench's simulation is now
    separate (`bench_sim.py` `SimTrain`, R15), still the toy plant. Not
    decided:
    - (a) keep the toy plant (Euler, rolling resistance only under a brake
      failure, no grade; its service brake state does not go false under
      the e-brake as the Train Model's does); or
    - (b) reuse the Train Model's pure-Python `train_model.model.TrainModel`
      from `development` inside `SimTrain`: one physics, with real rolling
      resistance and grade. D005 says modules do not import each other's
      boundary types, so this needs a team decision.

27. **Signal light ahead is not mapped from the Track Model.** Decided
    (M20): it comes from the Track Model directly, as
    `TrackModelOutputs.signal_seen[train_id]` on `development`: a
    `SignalAspect` on the tick the train enters a signal block, `None`
    otherwise. The controller reads `signal_light_ahead` and keeps the
    last value. Map it in the harness at integration.

28. **Engine-failure detection false-positives; the new rule is not on
    this branch.** The decided rule (§4: power above 0, no brake at any
    time in the window, speed falling by more than a threshold, never
    within the control band, a window longer than 2 s) was described as
    already written, but `c98393e` still has the old `F = P/v` rule.
    Push it here, and fix its window and threshold, which are not
    recorded yet.

    Measured 2026-10-21: this controller against `development`'s
    `TrainModel` (`de7a98f`), grades from `Track_layout/` (Green ±5 %,
    Red ±2 %), commanded 15 m/s. Worst speed fall over a window with
    power above 0, no brake, and outside a 0.1 m/s band of the target:

    | Case | 2 s | 3 s | 4 s | 5 s |
    |---|---|---|---|---|
    | Healthy, flat | 0 | 0 | 0 | 0 |
    | Healthy, onto +2 %, full load | 0.19 | 0.23 | 0.26 | 0.27 |
    | Healthy, onto +5 %, crew only | 0.44 | 0.50 | 0.53 | 0.53 |
    | Healthy, onto +5 %, full load | 0.55 | 0.67 | 0.74 | 0.81 |
    | Engine failed, flat (any load, 5 or 15 m/s) | 0.04 | 0.06 | 0.08 | 0.10 |
    | Engine failed, +2 % | 0.43 | 0.65 | 0.86 | 1.08 |
    | Engine failed, +5 % | 1.02 | 1.53 | 2.04 | 2.55 |

    (m/s; a 0.05 or 0.2 m/s band changes these by under 0.1.) No window
    and threshold separate them: on the flat a dead engine loses only
    rolling resistance (0.0196 m/s²), less than a healthy full train
    loses under full power on +5 %, which keeps slowing as long as the
    hill lasts. Without the grade (M19) the controller cannot tell the
    two apart. On the bench nothing falls at all: the bench simulation
    has no resistance, so a dead engine coasts at constant speed. The
    current `F = P/v` rule flags a healthy full train 2.4–2.9 s onto a
    +2 % or +5 % grade.

30. **Rules decided 2026-10-21 not yet in the code.** M3 (resolution not
    detected, blocked on #23), M19 (engine detection uses mass
    and `F = P/v`, #28), M20 (signal light not mapped, #27). Update
    `HARNESS_INTEGRATION.md` and `CHANGELOG.md` with each.

31. **Bench-side leftovers from the separation (R15–R17).**
    - Setting the bench clock is a jump: the lights act only if the jump
      changes night to day or back. 05:00 (the start) to 18:00 is night
      to night, so nothing changes; set a daytime first, or 17:59 and let
      the clock run.
    - The numbers drawer's acceleration comes from the bench simulation
      and reads 0 under a harness: it is not a signal the controller
      receives (M12; the drawer is to be removed).

32. **Choices made in R21–R22 for review** (2026-10-21, not specified):
    - Automatic opens the doors on *arrival* (station beacon heard, no
      authority, stopped), the same event as the arrival announcement.
      Before, it opened at any stop after a new beacon.
    - The departure announcement also needs authority above 0, the same
      "Track Signal resumes" test Automatic departs on.
    - Wording: "The train *id* is departing from *station*" (the request
      said "train *id* is departing", without "The").
    - The bench sends a beacon once after any beacon row is sent, so
      setting underground alone works; every such beacon with a station
      name arms a station stop, as a real beacon would.
    - "Arriving soon" fires whenever the authority reaches 3, station or
      not; a rise to 3 announces too, accepted (M7, R29).
    - Lights: both interior and exterior switch together.
    - The bench's hours wheel runs 0–23, not 0–24 as asked: 24:00 is
      00:00, and 24:30 is not a time of day (R27).
    - Switching to Manual during a brake failure (R26) now lets the
      driver ask for the service brake (the button is live, R32; the
      e-brake can be released in Manual at a stand, R31), but nothing
      detects a resolution yet (#23), so the bench still clears the
      failure.
    - With an uncommissioned train selected nobody is signed in, so
      nobody can reach its emergency brake from the console; it commands
      0 W and cannot move under its own power.

33. **What the cut-off text scan cannot see** (R23). It catches text Qt
    elides and text drawn past the window's edge, at the states the
    self-check reaches. It does not catch text overlapping a neighbour
    inside the window, or a state the check never reaches (a very long
    station name, say).

34. **E-brake left off in Automatic with a failure latched** (R31, to
    test later). The driver releases the emergency brake in Manual at a
    stand, failure still latched, then switches to Automatic: the brake
    stays off, and the train is held only by the 0 target (and the
    service brake if it moves). That follows M3 ("does not engage it
    again"). To decide after testing: keep it, or have Automatic engage
    it again while a failure is latched.

## Carried over

- **Rolling resistance.** Decided: the controller models no outside forces
  (M19). The toy plant's rolling resistance (C_rr 0.002, under an injected
  brake failure only) is the bench simulation's, and goes with it (#26).
- **Signal aspect has no truth entry** (truth's Track Signal carries only
  commanded speed and authority). The Track Model now sends it directly
  (#27); truth still needs an entry.
- **Service-brake amber and the 72 px hero readouts** (`brake_service` and
  `size_hero` in `train_ctrl/console_theme.py` `PENDING_TOKENS`) are outside
  the style guide; the proposal that carried both was removed from the
  inbox (`69b5cc9`).
- **Other sizes kept to Ivan's design but outside the style guide** (restored
  2026-10-07 at Jonathan's request): the speed and temperature dial figures are
  computed from the dial radius (`Math.max(32, r * 0.6)` and
  `Math.max(30, r * 0.66)`) rather than a token, and the door and light tiles
  are 52 px tall (the guide's control heights are 28 / 36 / 44) with
  Label-token text instead of the button type scale.
- **Local near-duplicates of shared components** — `ConsoleHeader`
  (ModuleHeader plus `alerts`), `HeroReadout`, `BrakeButton`, `SignalEditRow`,
  and `TrainPicker` — each needs a change to the shared `ui/` folder to
  retire or share.
- **Kp/Ki unit labels are SI** ("W per m/s", "W per m"); converting them changes
  the numbers engineers type.
- **The root `requirements.txt` on this branch lacks the PySide6 pin** that
  `development` has (`PySide6==6.11.2`).
