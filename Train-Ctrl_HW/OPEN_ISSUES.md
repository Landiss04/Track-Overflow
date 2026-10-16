# Train-Ctrl_HW — open issues for review

Found but not fixed. Each entry says what goes wrong and where, so it can be
picked up later. Last reviewed 2026-10-15 (requirements check against the SRS).

## From the 2026-10-07 code review

3. **Half of the speed dial's dead zone requests full speed.**
   `ui_parts/components/SpeedDial.qml` — `valueFor` maps only the left half of the
   90° gap at the bottom to zero; the right half (270–315°) clamps to the limit.
   A press just right of bottom-centre in Manual commands line speed, not 0,
   contradicting the file's own header comment.

## Added 2026-10-08

11. **Block lengths are unknown, so how fast the train moves through each
    block is unknown.**
    `main.py` — until the Track Model sends the authority count, the toy plant
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

## Carried over

- **Rolling resistance outside a brake failure** is open. It (C_rr 0.002)
  applies under an injected brake failure only, as a trial. The slow-down
  overshoot it once fixed is now fixed by the 0.05 m/s service band instead
  (35 → 30 mph settles at 30.09 mph at 480 kW).
- **Toy plant parameters differ from truth's Train Model**
  (`truth/modules/train-model.md`): 51,433 kg vs about 52,312 kg reference
  mass, Euler vs trapezoidal integration, rolling resistance only under a
  brake failure (C_rr 0.002). Power now matches (480 kW, provisional in truth).
- **The controller simulates the train itself** (truth D009 gives physics to the
  Train Model). `ControllerCore._plant()` is the stand-in until the Train Model
  is connected.
- **Signal aspect has no truth entry** (truth's Track Signal carries only
  commanded speed and authority); a proposal exists on `Train-Ctrl_SW` only.
- **Service-brake amber and the 72 px hero readouts** (`brake_service` and
  `size_hero` in `main.py` `PENDING_TOKENS`) are pending one style-guide
  proposal, `truth/_inbox/Train-Ctrl_HW/20261007-2059-style-guide-size-hero-token.md`,
  which carries both tokens. Authority as a block count is no longer open:
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
