# Known bugs

Open bugs in the Train Controller (both variants, M13) and its test bench, in
the format of the Train Model's [`docs/bugs.md`](../TrainModel/docs/bugs.md):
each has a way to reproduce it, its cause where known, and a suggested fix.
Below them, the bug count week by week (REQ-COMP-009) and the log of bugs
resolved. Open issues that are decisions or plans, not defects, stay in
[`OPEN_ISSUES.md`](OPEN_ISSUES.md).

Not tracked here:

- **The numbers drawer** (*Show all numbers*). It is for debugging outside
  integration and goes in the final iteration, so what it shows under the
  central harness is not a bug: Kevin's F24, F25 and F26 (2026-10-31).
- **Questions for other modules.** Those go in
  [Notes for other modules](#notes-for-other-modules) at the end.

Last updated 2026-10-31, on `Train_Ctrl_integration` `f11ebe5`. Sources: this
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
| [B3](#b3) | Controller | Medium | A healthy train climbing a grade is taken for an engine failure (#28) |
| [B8](#b8) | Bench | Low | Five header pills push *Set time* off the bench (#36) |
| [B9](#b9) | Tooling | Low | The self-check fails on a loaded machine (#21) |

## Bugs

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
- **Measured 2026-10-31**, both rules driving the Train Model on
  `claude/quirky-fermi-sickg4` `57e8847` with the harness's two-tick echo
  (Kp 400,000, Ki 8,000), the train running onto the grade from a steady
  speed on the flat:

  | Case | Current rule | Steady fall |
  |---|---|---|
  | Healthy, onto +2 %, full load, 15 m/s or 70 km/h | Latched 3.0–3.3 s in | Never |
  | Healthy, onto +4 %, full load, 45 km/h | Latched 2.5 s in | Never |
  | Healthy, onto +5 %, crew only, 15 m/s or 70 km/h | Latched 2.5–2.6 s in | Never |
  | Healthy, onto +5 %, 111 passengers, 11 m/s | Latched 2.4 s in | Never |
  | Healthy, onto +5 %, 125 passengers, 11 or 15 m/s | Latched 2.4–2.5 s in | Never in 90 s |
  | Healthy, onto +5 %, 130 or more passengers | Latched 2.4–2.5 s in | Latched 7.4–10.2 s in |
  | Engine fails, flat, 5 or 15 m/s | Latched 2.0–4.8 s after | Latched 5.2–5.9 s after |
  | Engine fails, +2 % or +5 % | Latched 2.4 s onto the grade, before the failure | Latched 5.4 s after |

  So the port fixes the bug for every load up to about 125 passengers, and
  finds a real failure 0.4–3.9 s later than now. Above about 125 passengers
  the Train Model's 25.7 kN of traction cannot hold a train on a 5 % grade
  at all: it slows steadily and would stall and roll back, and the steady
  fall stops it on the emergency brake first (see
  [Notes for other modules](#notes-for-other-modules)).

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
| 2026-11-06 (to 10-31) | 0 | 0 | 2 | 3 |

Not counted in Reported: the gains hand-over (#16) and the 0/0 pickup rule,
whose first report is not dated in the record. Both are in the resolved
counts, so "Open at the end" is the open bugs above, not a running sum.
On 2026-10-31 four bugs left the count without being resolved: B4 became a
note for the CTC Office, and B5, B6 and B7 were in the numbers drawer.

**To resolve by 2026-11-06:** B1 and B2 are done (R40, R41). Left: B3 (port
from `460579b`, measured above), B8 (with `OPEN_ISSUES.md` #45), B9.

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
| A signal pickup failure never cleared under the harness (B1, F37) | 10-28 | 10-30 | 10-31 (R40) |
| A negative gain was saved as 0 without a word, for good (B2, F23) | 10-28 | 10-31 | 10-31 (R41) |

The seven texts count as seven bugs and review items 5–9 as five, so the
log's 18 rows are 24 resolved bugs.

## Notes for other modules

Questions and possible errors whose answer lies with another module. Not
counted as bugs.

### CTC Office

- **A Green train over its limit after dispatch** (TC-1, Kevin, native
  Windows, 2026-10-29; not reproduced). About 50 s after dispatch, G1 at
  34.9 mph against a 24.9 mph limit, commanded 22.4 mph, service brake on.
  One reading. Kevin's possible cause, not checked: Green 66 to 67 drops
  from 70 to 40 km/h, and a train braking at the service rate from the
  earlier block's speed reads like this for a few seconds. The CTC Office
  does not slow a train ahead of a lower limit (Kevin, 2026-10-21, Q-P4-4),
  and the controller brakes from the first tick in the slower block
  (`tests/test_harness_driven.py` `LowerLimitAheadTest`). Question: should
  the commanded speed drop before the slower block?

### Train Model

- **A loaded train cannot climb a 5 % grade.** With more than about 125
  passengers (of 222), the Train Model's maximum traction (`f_max_n`,
  25,717 N) is less than gravity and rolling resistance on Green's 5 %
  grade, so the train slows steadily under full power, then stalls and
  rolls back (measured with B3). Question: is that intended for Green 7?
