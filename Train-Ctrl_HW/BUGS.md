# Known bugs

Open bugs in the Train Controller (both variants, M13) and its test bench, in
the format of the Train Model's [`docs/bugs.md`](../TrainModel/docs/bugs.md):
each has a way to reproduce it, its cause where known, and a suggested fix.
Below them, the bug count week by week (REQ-COMP-009) and the log of bugs
resolved. Open issues that are decisions or plans, not defects, stay in
[`OPEN_ISSUES.md`](OPEN_ISSUES.md).

Last updated 2026-10-30, on `Train_Ctrl_integration` `2764230`. Sources: this
branch's git history and `CHANGELOG.md`, and Kevin Schillinger's harness
walkthrough on `claude/quirky-fermi-sickg4` `51eca3b`
(`documents/central-harness-windows-gui-2026-10-28.md`, "F" numbers, and
`documents/module-owner-review.md`, "TC-1").

Severity:

- **Medium**: reachable in normal use, or on a real line.
- **Low**: cosmetic, a debugging view, or tooling.

Area is the **controller** (`train_ctrl/control.py` and the fleet), the
**console** (the driver's and engineer's window), the **bench** (the test
window and its simulation), or **tooling** (`check.py`).

| ID | Area | Severity | Summary |
|---|---|---|---|
| [B1](#b1) | Controller | Medium | A signal pickup failure never clears under the harness (F37) |
| [B2](#b2) | Console | Medium | A negative gain is saved as 0 without a word, for good (F23) |
| [B3](#b3) | Controller | Medium | A healthy train climbing a grade is taken for an engine failure (#28) |
| [B4](#b4) | Controller | Medium | A Green train over its limit after dispatch (TC-1, not reproduced) |
| [B5](#b5) | Console | Low | The authority readout names "GREEN K" for every train (F24) |
| [B6](#b6) | Console | Low | *Stop the train* and the *Service brake* row disagree (F25) |
| [B7](#b7) | Console | Low | Acceleration reads 0.00 m/s² under the harness (F26) |
| [B8](#b8) | Bench | Low | Five header pills push *Set time* off the bench (#36) |
| [B9](#b9) | Tooling | Low | The self-check fails on a loaded machine (#21) |

## Bugs

### B1

**A signal pickup failure never clears under the harness.** Controller,
Medium. Kevin's F37, 2026-10-28.

- **Reproduce:** under the harness, induce a signal pickup failure on a train
  in the Train Model window, then clear it. The Train Controller still shows
  *Signal pickup: Fault*, and the train never drives in Automatic again.
- **Cause:** the failure latches (`control.py` `detect_failures`), and only
  the bench clears it (`clear_failure`); the controller does not detect the
  resolution (M3, `REQUIREMENTS.md` §4, `OPEN_ISSUES.md` #23).
- **Fix:** since 2026-10-28 a lost pickup arrives as null, so a non-null
  commanded speed and authority is the resolution §4 describes: clear
  `signal_pickup` on the first tick both arrive non-null. Not done; to choose.

### B2

**A negative gain is saved as 0 without a word, for good.** Console, Medium.
Kevin's F23, 2026-10-28.

- **Reproduce (Kevin):** type `abc-5` in Kp and press *Set gains*. Kp is saved
  as 0 with no message, and gains cannot be changed afterwards.
- **Likely cause, not reproduced here:** the field's `DoubleValidator`
  (`ui/ValueField.qml`) refuses the letters but accepts `-5`, and
  `commission_gains` (`backend.py`) clamps a negative gain to 0 and commissions
  it. A train with Kp 0 cannot be recommissioned (M9).
- **Fix:** refuse a negative gain in `commission_gains` with a note, as a
  non-number already is, and give the fields a bottom of 0.

### B3

**A healthy train climbing a grade is taken for an engine failure.**
Controller, Medium. `OPEN_ISSUES.md` #28, measured 2026-10-21.

- **Reproduce:** against the Train Model, a full train under full power onto a
  +2 % or +5 % grade is flagged 2.4–2.9 s in and stopped on the emergency
  brake. Measurements in #28.
- **Cause:** the rule "speed not up 0.05 m/s in 2 s" also describes a train
  slowing on a climb.
- **Fix:** port the steady-fall rule Kevin accepted (R91), which exists only
  in `460579b` (`control.py`, `tests/test_engine_detection.py`).

### B4

**A Green train over its limit after dispatch.** Controller, Medium. TC-1,
2026-10-29; not reproduced, so not verified.

- **Seen (Kevin, native Windows):** about 50 s after dispatch, G1 at 34.9 mph
  against a 24.9 mph limit, commanded 22.4 mph, service brake on. One reading.
- **Possible cause (Kevin), not checked:** Green 66 to 67 drops from 70 to
  40 km/h; a train braking at the service rate from the earlier block's speed
  reads like this for a few seconds. The controller does not slow ahead of a
  lower commanded speed (M1).
- **Next:** reproduce: dispatch a Green train from the yard at 1x and watch
  blocks 66 to 67. TC-1 names `TrainController/` as the owner, but Green
  trains run this module (M13).

### B5

**The authority readout names "GREEN K" for every train.** Console, Low.
Kevin's F24, 2026-10-28.

- **Reproduce:** under the harness, open *Show all numbers* for a Red train:
  "6 to block GREEN K".
- **Cause:** `State.authority_target` defaults to `"GREEN K"`
  (`state.py`), and only the bench's spawn sets it; the harness never does.
  It names a section letter, not a block.
- **Fix:** show it only when set, or drop it with the drawer (it is a drawer
  value that goes in the final iteration).

### B6

**Stop the train and the Service brake row disagree.** Console, Low. Kevin's
F25, reproduced 2026-10-29.

- **Reproduce:** steps in Kevin's report (*F25 reproduction*): a Red train
  holding 22 mph on the downhill from block 11 to 15. The badge reads BRAKING
  while the row reads Released, and the other way round.
- **Cause:** the badge (`StopPanel.qml`) shows the Train Model's report,
  `fb_service_brake`; the row (`NumbersDrawer.qml`) the controller's command,
  `service_brake`. On a downhill the controller pulses the brake 2 ticks in
  6–8, and the report arrives `ECHO_TICKS` (2) later, so the two are always
  out of phase. The brake itself works.
- **Fix:** to choose: label the two as report and command, or show the same
  one in both.

### B7

**Acceleration reads 0.00 m/s² under the harness.** Console, Low. Kevin's
F26, 2026-10-28.

- **Cause:** `accel_mps2` comes from the bench simulation, and is 0 when there
  is none (`backend.py`; noted in `OPEN_ISSUES.md`).
- **Fix:** none planned; the drawer and this value go in the final iteration
  (M12).

### B8

**Five header pills push Set time off the bench.** Bench, Low.
`OPEN_ISSUES.md` #36, 2026-10-24.

- **Reproduce:** on the bench, show the mode, Underground, E-brake, a failure
  and the Station dwell pill at once. The time wheels push the clock and
  *Set time* past the window edge.
- **Fix:** with the time-setting redesign (`OPEN_ISSUES.md` #45).

### B9

**The self-check fails on a loaded machine.** Tooling, Low.
`OPEN_ISSUES.md` #21, 2026-10-16.

- **Reproduce:** run `main.py --check` straight after another run: on
  2026-10-16, 9 failures in the failure-handling section; alone, 0.
- **Cause:** older sections wait on wall-clock deadlines while the control
  timer runs.
- **Fix:** step the controller directly, as the checks since 2026-10-24 do.

## Week by week

Weeks end on Friday. **Reported**: the bug was first recorded. **Verified**:
it was reproduced, measured, or its cause located, as recorded. **Resolved**:
fixed, with the commit. Counted from the log below and the open bugs above;
a bug with no recorded date for a step is not counted for that step.

| Week ending | Reported | Verified | Resolved | Open at the end |
|---|---|---|---|---|
| 2026-10-09 | 7 | 5 | 7 | 0 |
| 2026-10-16 | 2 | 2 | 1 | 1 |
| 2026-10-23 | 10 | 10 | 9 | 2 |
| 2026-10-30 | 10 | 9 | 5 | 9 |
| 2026-11-06 | (planned) | | | |

Not counted in Reported: the gains hand-over (#16) and the 0/0 pickup rule,
whose first report is not dated in the record. Both are in the resolved
counts, so "Open at the end" is the open bugs above, not a running sum.

**To resolve by 2026-11-06:** F2 is done (`5fd4874`). Candidates, to pick:
B1 (small, now that a lost pickup is null), B2, B3 (port from `460579b`), B5.

## Resolved

One line each; details in the commits.

| Bug | Reported | Verified | Resolved |
|---|---|---|---|
| The emergency brake engaged at random | 10-04 | — | 10-04 `8cc9d19` |
| Test window layout broken | 10-04 | — | 10-04 `ead805e` |
| Bench sent the whole draft, rounded, re-latching a released e-brake (review 5) | 10-07 | 10-07 | 10-07 `7611dc9` |
| A set with one bad value was half applied (review 6) | 10-07 | 10-07 | 10-07 `7611dc9` |
| A second press of a door or light tile did nothing (review 7) | 10-07 | 10-07 | 10-07 `7611dc9` |
| Train pickers rebuilt every UI tick: scroll reset, lost clicks (review 8) | 10-07 | 10-07 | 10-07 `7611dc9` |
| Signal lamps did not always fit (review 9) | 10-07 | 10-07 | 10-07 `7611dc9` |
| The operator bar shifted when the gains were set | 10-16 | 10-16 | 10-16 `8ca396f` |
| The controller's own e-brake, echoed back, re-latched after a release | 10-20 `0608f97` | 10-20 | 10-21 (R16) |
| Light tiles locked after a bench light edit | 10-21 | 10-21 | 10-21 `5b99075` (R18) |
| Seven texts cut off (R23) | 10-21 | 10-21 | 10-21 `a6366c8` |
| Gains hand-over signed a driver in unasked (#16) | — | 10-24 | 10-24 `bf277b1` |
| Under the harness every service brake read as a brake failure (#42) | 10-24 | 10-24 | 10-24 `6def698` |
| Integrated, a brake failure never resolved (#44) | 10-24 | 10-24 | 10-24 `3dd15ef` |
| A valid stop from ≥ 2 blocks read as a pickup failure (Braden's request 9) | — | — | 10-28 `a6c1eb3`, here `f05053b` |
| Both consoles titled "HW Train Controller" (F2) | 10-28 | 10-28 | 10-30 `5fd4874` |

The seven texts count as seven bugs and review items 5–9 as five, so the
log's 16 rows are 22 resolved bugs.
