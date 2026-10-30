**Target:** truth/arbitration/engine-failure-detection.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** Replaces proposal `20261021-1220-engine-failure-steady-fall-accepted.md` (Codex), whose accepted steady-fall detector and its acceptance are merged into this entry. Kevin Schillinger's direct statement of 2026-10-21 in the integration session, fixing the HW Train Controller's engine-failure detector after it latched a false engine failure while holding a steady 5 m/s up the grade at Green 93 (the round trip of `common/harness/tests/test_harness_train_loop.py::ReturnToYardTest`). No truth entry records how the Train Controller detects an engine failure; `modules/train-model.md` records only that an engine failure zeroes traction and is not reported, and `signals/failure-status` is withdrawn.

---

# engine-failure-detection

**Status:** current
**Owner:** Train Controller
**Provenance:** asserted by Kevin Schillinger 2026-10-21: "Never flag while the train is holding its target: if the speed is within the control band of the commanded speed, it is doing what it was told." "Flag on falling speed, not on 'not rising': latch only if power is commanded above zero and speed has dropped by more than a small threshold over the window. No brake (service or emergency) must be applied at any time during that window, so braking isn't mistaken for a failure." "Use a longer window: a few seconds more than 2 s, so a slow fall on the flat is still caught without trips from tick noise."; subsequently "Accept the steady-fall check as built", in answer to the question describing the additional straight-line check and Green 7's recoverable grade-entry sag, accepting the additional shape check and its as-built parameters (Kevin Schillinger 2026-10-21)
**Aliases:** engine detection, engine failure detector, inferred engine failure, engine stall detection, steady-fall check
**Last updated:** 2026-10-21

## Definition

The Train Model does not report an engine failure, so the Train Controller infers it
from the speed it reports back:

1. A train holding its target is never flagged: while the actual speed is within the
   control band of the commanded speed, the train is doing what it was told.
2. An engine failure is flagged on falling speed, not on speed that fails to rise. It
   latches only if power is commanded above zero and the speed has dropped by more than
   a small threshold over the detection window, with no brake, service or emergency,
   applied at any time during that window.
3. The detection window is a few seconds longer than 2 s, so a slow fall on the flat is
   still caught without trips from tick noise.

## Accepted steady-fall detector

The accepted detector under review, in the shared `Train-Ctrl_HW` package, shall
never flag a train within 0.05 m/s of its target. Otherwise, it shall latch an
engine failure only when all of these conditions hold:

1. Power is commanded above zero on every tick of a 6 s simulation-time window.
2. Neither service nor emergency brake is commanded or reported applied on any tick
   of that window. A brake or zero commanded power clears the window.
3. Divide the window into consecutive half-second speed means. The first mean
   exceeds the last by more than 0.05 m/s, and every mean is within 10% of that total
   fall of the straight line joining the first and last means.

The falling-speed rule replaces a failure-to-rise rule. The additional steady-fall
shape check distinguishes a sustained fall from a recoverable grade-entry sag,
such as the approximately 0.51 m/s sag recovered in approximately 3 s at Green 7.
Acceptance of this detector does not assign its exact thresholds, control band,
window length or smoothing parameters to other independent variant implementations.

## Limits

- A stationary train with a dead engine is not flagged by this detector, because its
  speed does not fall.
- A heavily loaded train unable to hold speed on Green 7's 5% grade can satisfy
  these conditions and be flagged despite having a working engine. The rule does
  not distinguish that sustained loss of speed from a dead engine.

## Notes

- Supersedes, for the HW variant, its own earlier rule (not a truth entry): latch when,
  with power on and no brake, the speed did not rise for 2 s. That rule latched while
  the train held its target up a grade.
- An engine failure zeroes traction ([modules/train-model.md](../modules/train-model.md)),
  so on the flat the slowest fall it gives is rolling resistance alone.
- Not stated for the other variant: the threshold, the window's exact length, or the
  control band's width; those are each variant's own. The values of the accepted
  detector are stated above and are not assigned to other variant implementations.
- Applies to both Train Controller variants; the case that raised it was the HW variant.

## Supersedes

- Exact thresholds and window for the HW detector: previously unstated (rules 2 and 3
  above); now stated under Accepted steady-fall detector (Kevin Schillinger 2026-10-21,
  "Accept the steady-fall check as built").
- Sag versus failure: previously unstated whether a sag in speed running onto a grade
  may be told apart from a failure by the shape of the fall; now the steady-fall shape
  check does so (Kevin Schillinger 2026-10-21).
