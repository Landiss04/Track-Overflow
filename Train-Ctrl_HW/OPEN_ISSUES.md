# Train-Ctrl_HW — open issues for review

Found but not fixed. Each entry says what goes wrong and where, so it can be
picked up later. Last reviewed 2026-10-16 (requirements review,
`REQUIREMENTS.md`).

## From the 2026-10-07 code review

Item 3 (half of the speed dial's dead zone asked for full speed) is fixed
(2026-10-16): the whole gap reads 0, with a check.

## Added 2026-10-08

11. **Block lengths are unknown, so how fast the train moves through each
    block is unknown.**
    `train_ctrl/control.py` — until the Track Model sends the authority count, the toy plant
    spends one block per `BLOCK_LENGTH_M` travelled, so the console shows the
    train making progress. Every block is taken as 100 m, an arbitrary stand-in:
    the real lengths vary block by block and are not known to this module. The
    "Stop in N blocks" readout therefore counts down at the wrong rate wherever
    a real block is longer or shorter than 100 m.

    The controller only brakes once the count reaches 0, so a block must be
    at least as long as the service-brake stopping distance, v² / (2 × 1.2 m/s²),
    or the train runs past its authority. At 100 m that holds only up to
    15.5 m/s (34.6 mph):

    | Speed when the count reaches 0 | Stopping distance | Past the authority |
    |---|---|---|
    | 30 mph | 75 m | none (25 m short) |
    | 34 mph | 96 m | none (4 m short) |
    | 43 mph | 154 m | 54 m |
    | 70 km/h (43.5 mph) | 158 m | 58 m |

    The 30, 34 and 43 mph rows are measured on the toy plant over 20 blocks,
    Manual; 70 km/h is computed. Resolved when the Track Model sends real
    counts (delete the countdown from `_plant()` then), or when the block
    lengths are known.

    How the real system does it (checked on `development`, 2026-10-15): the
    controller needs no block-change input. The Track Model flips the track
    circuit polarity at each block, the Train Model turns that flip into a
    block-change event sent to the **Track Model only** (truth
    `signals/block-change-event.md`), and the Track Model then sends each
    train the Track Signal of the block it occupies, which the Train Model
    passes through to us. So the authority count is refreshed per block by
    the wayside, provided the Track Controller writes a decreasing count into
    each block along the route (not checked). A dead or uncommanded block
    arrives as 0 m/s and 0 blocks, which the controller reads as a lost
    signal and stops on: correct, the failure propagates from the track
    circuit through the Train Model.

    Resolution: train model will need a block change event. This causes authority
    decrement. Should be already implemented as a dumby function currently

## Added 2026-10-15

14. **How a failure clears once integrated — undecided.**
    Today only the test bench clears a latched failure (`clear_failure`, called
    when a bench failure row is set back to False); the driver then releases
    the emergency brake at a stand. With the real Train Model and no bench,
    nothing clears it, so the train stays stopped on the emergency brake.
    Candidate approaches, none chosen:
    - (a) **Auto-clear when the returned signals look healthy again** — brake:
      a service-brake test at a stand shows Brake State applied; engine:
      commanded power produces acceleration again; pickup: a valid non-zero
      Track Signal resumes.
    - (b) **Murphy's clear reaches the controller** through the harness. This
      needs a truth signal, since `failure-status` was withdrawn.
    - (c) **A maintenance or CTC action** clears it.
    - (d) **A driver or engineer acknowledgement at a stand.** A driver "Reset
      failure" button was tried and removed (2026-10-15).

    To be decided with Kevin (Train Model owner) and the team, through truth.
    - The toy plant's Brake State during a failed service brake (reads false) is
      the plant's own stand-in, not taken from truth `brake-state.md`.

## Added 2026-10-16 (requirements review, `REQUIREMENTS.md`)

16. **The engineer hand-over can still sign a driver in unasked.**
    `train_ctrl/backend.py` — `_retire_engineer` runs 1.5 s after
    commissioning and sets `operator = "driver"` unconditionally. Sign the
    console out inside that window and a driver is signed in anyway,
    unlocking Manual controls. (Was item 4; dropped from this list but not
    fixed.)

17. **No block-change dummy exists yet.** Item 11's resolution expects
    one; nothing in `train_ctrl/` handles a block-change event, and the toy
    plant still counts authority down every 100 m.

18. **Automatic lights at dusk have no input.** In Automatic the lights
    should come on in a tunnel (beacon underground) and at dusk.
    Nothing tells the train when it is dark, so neither is built yet.

19. **Module rules are not recorded outside this folder.** Rules M1–M14
    in `REQUIREMENTS.md` (commanded speed as the limit, driver-only
    e-brake release, failure detection, door and announcement ownership)
    are in neither truth's Train Controller contract (still a
    placeholder) nor the SRS. Update the documentation later.

20. **Leftovers on this branch.** `old_main.py` is an unused copy of the
    pre-split `main.py`; `ui/__pycache__/theme.cpython-314.pyc` is
    committed again (`d444312`); flake8 reports about 30 issues in the
    split files (unused re-exports in `__init__.py`, missing final
    newlines, blank-line spacing).

21. **The self-check is timing-sensitive.** Several `check.py` sections
    wait on wall-clock deadlines (`_until`) while the control timer runs.
    On a loaded machine the timer is starved and checks fail that pass
    alone: on 2026-10-16 a run started straight after another reported 9
    failures in the failure-handling section ("the driver set a target
    during an engine failure", "the brake would not release once the
    engine failure cleared", ...), and the same code then passed with 0 in
    34 s. Run `--check` on its own; a fix would step the controller
    directly instead of waiting on the timer.

22. **Harness-spawned trains are never armed.** Since `b9e3f6a`,
    `harness_sim.py` no longer sets `armed`, so its trains sit at 0 W
    until an engineer commissions the gains on the console, one train at
    a time. How a harness-dispatched train gets its gains (defaults on
    dispatch, or the engineer each time) is undecided. Decided
    2026-10-20 (truth D024): the engineer, for every new train; the
    console may offer default gains but never applies them by itself.

## Added 2026-10-20 (Phase 1 of the central harness)

23. **The dwell belongs to the controller now.** Fixed 2026-10-20, for
    the owners to review (`CHANGELOG.md`): Kevin Schillinger set that the
    CTC Office schedules the 45 s dwell and the controller enforces it
    (truth D007 and its pending update). The Automatic station stop now
    holds the doors open at least 45 s (`DWELL_S`, counted in 0.1 s
    steps), however soon the Track Signal resumes, then closes them and
    departs once Door State reports them closed. `check.py` checks it.

24. **The fourth light is spelled with a space.** `ASPECTS` holds
    `"SUPER GREEN"`; truth `signals/signal-aspect-ahead` spells it
    `SUPER_GREEN`, as every enumerated value is in capitals with
    underscores. The harness maps it on the way in for now
    (`common/harness/train_edges.py`).

25. **A station run through stays pending until the next stop.** A new
    beacon station marks a stop pending (`apply_staged`), served once the
    train stands. A train that runs through the station without stopping,
    as it does through every station not on its schedule (truth D020),
    keeps it pending: the beacon after the station names the same station,
    so nothing clears it. At its next stand, wherever that is, Automatic
    opens the platform-side doors and holds the dwell there. Found under
    the central harness on 2026-10-20: with authority back before the
    train had stopped at GLENBURY, it ran through, stopped at the end of
    its route in block 67, and opened its doors there. A fix could clear
    the pending stop when a beacon for the same station arrives while the
    train is moving, as it leaves the station.

## Added 2026-10-21

26. **Engine detection tripped holding speed up a grade.** Fixed 2026-10-21,
    for the owners to review (`CHANGELOG.md`), to rules set by Kevin
    Schillinger: never flag a train within the control band of its target;
    flag only a fall in speed with power commanded and no brake in the
    window; use a window a few seconds longer than 2 s. The old rule (speed
    not up 0.05 m/s for 2 s with power on) stopped G1 at Green 93 on the
    round trip. Read literally, "fell by more than the band over the window"
    also trips running onto Green 7's 5 % grade, where the speed sags about
    0.5 m/s before the PI catches it; so the fall must also be steady (a dead
    engine's fall is a straight line, a sag curves out). Still open: a train
    at a stand with a dead engine is not flagged (it never falls), and a
    train that cannot hold its speed up a grade at full power is.

## Carried over

- **Rolling resistance outside a brake or engine failure** is open. It
  (C_rr 0.002) applies under an injected brake or engine failure only, as
  a trial; under an engine failure it lets the dead engine show as a
  fall. The slow-down overshoot it once fixed is now fixed by the
  0.05 m/s service band instead (35 → 30 mph settles at 30.08 mph at
  480 kW).
- **Toy plant parameters differ from truth's Train Model**
  (`truth/modules/train-model.md`, October 20 review proposal): Euler vs exact
  constant-force segments and midpoint power-limited integration,
  rolling resistance only under a brake failure (C_rr 0.002). Mass
  (51,433 kg reference) and power (480 kW, confirmed by Kevin’s October 20
  SDD review) match. Rolling resistance is the only passive resistance term in
  Train Model scope; no aerodynamic-drag/wheel-slip/brake-build-up prerequisite
  or real-world calibration study is implied.
- **The controller simulates the train itself** (truth D009 gives physics to the
  Train Model). `ControllerCore._plant()` is the stand-in until the Train Model
  is connected.
- **Signal aspect has no truth entry** (truth's Track Signal carries only
  commanded speed and authority). The console shows it but never acts on
  it.
- **Service-brake amber and the 72 px hero readouts** (`brake_service` and
  `size_hero` in `train_ctrl/console_theme.py` `PENDING_TOKENS`) are outside
  the style guide; the proposal that carried both was removed from the
  inbox (`69b5cc9`). Authority as a block count is no longer open:
  truth D013 (2026-10-06) adopted it, so the three authority proposals and
  the separate brake-service one were withdrawn (2026-10-15).
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
