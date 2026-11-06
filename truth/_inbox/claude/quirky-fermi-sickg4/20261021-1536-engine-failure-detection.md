**Target:** truth/arbitration/engine-failure-detection.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** Kevin Schillinger's direct statement of 2026-10-21 in the integration session, fixing the HW Train Controller's engine-failure detector after it latched a false engine failure while holding a steady 5 m/s up the grade at Green 93 (the round trip of `common/harness/tests/test_harness_train_loop.py::ReturnToYardTest`). No truth entry records how the Train Controller detects an engine failure; `modules/train-model.md` records only that an engine failure zeroes traction and is not reported, and `signals/failure-status` is withdrawn.

---

# engine-failure-detection

**Status:** current
**Owner:** Train Controller
**Provenance:** asserted by Kevin Schillinger 2026-10-21: "Never flag while the train is holding its target: if the speed is within the control band of the commanded speed, it is doing what it was told." "Flag on falling speed, not on 'not rising': latch only if power is commanded above zero and speed has dropped by more than a small threshold over the window. No brake (service or emergency) must be applied at any time during that window, so braking isn't mistaken for a failure." "Use a longer window: a few seconds more than 2 s, so a slow fall on the flat is still caught without trips from tick noise."
**Aliases:** engine detection, engine failure detector, inferred engine failure, engine stall detection
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

## Notes

- Supersedes, for the HW variant, its own earlier rule (not a truth entry): latch when,
  with power on and no brake, the speed did not rise for 2 s. That rule latched while
  the train held its target up a grade.
- An engine failure zeroes traction ([modules/train-model.md](../modules/train-model.md)),
  so on the flat the slowest fall it gives is rolling resistance alone.
- Not stated: the threshold, the window's exact length, or the control band's width;
  those are each variant's own. Not stated either: whether a sag in speed running onto a
  grade, which the speed law recovers within a few seconds, may be told apart from a
  failure by the shape of the fall.
- Applies to both Train Controller variants; the case that raised it was the HW variant.
