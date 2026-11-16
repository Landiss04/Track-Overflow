**Target:** truth/arbitration/suggested-speed-stops-within-authority.md
**Action:** replace
**Proposed by:** Claude on integrate/harness-into-development
**Provenance:** Replaces the unpromoted proposal `20261109-1135-suggested-speed-full-train-grade.md` on this branch. It keeps its full-train, per-block-grade calculation and replaces its "no stopping margin" with a 3 s reaction allowance, asserted by Landis 2026-11-12 ("deploy subagents to fix this issue"). That came after Red locked up in the Schedule v4 full-system run of 2026-11-12: R7, suggested the exact full-train stopping speed for its last block, rolled one block past its authority beside R1, and the Red Track Controller held both trains for good. The 3 s value was measured on `CTC-Office/tests/realistic_railway.py`.

---

# suggested-speed-stops-within-authority

**Status:** current
**Owner:** Landis
**Provenance:**
- Issue a safe suggested speed so trains do not run up on each other: asserted by Landis 2026-10-06.
- Each block's grade and a full train: asserted by Landis 2026-11-09.
- A 3 s reaction allowance: asserted by Landis 2026-11-12.
- Constants from `modules/train-model.md` (Datasheet, Design).
**Aliases:** safe suggested speed, authority-aware speed, braking speed, stopping margin, reaction allowance
**Last updated:** 2026-11-12

## Definition

The CTC Office's suggested speed for a train is never more than the speed v from which
a full train, running on at v for T before its service brake takes hold, stops within
its authority:

v × T + v² ÷ (2 × a) = D, so v = −a × T + √((a × T)² + 2 × a × D)

The result is rounded down to a whole m/s. D is the length of the blocks within the
train's authority, and a is their deceleration weighted by length, Σ(aᵢ × dᵢ) ÷ D. For
each block, dᵢ is its length and aᵢ its deceleration:

aᵢ = F ÷ m + g × sin(atan(grade ÷ 100))

- T is 3 s.
- F is the service brake force, 61,720 N.
- m is the mass of a full train, 58,404 kg: the empty mass, 40,900 kg, plus 222
  passengers and 5 crew at 77.1107 kg each. F ÷ m is 1.06 m/s².
- g is 9.81 m/s².
- grade is the block's grade in percent as listed in the track layout file: positive
  uphill, negative downhill.

With an authority of 0 the suggested speed is 0.

It is also never more than the limit in
[suggested-speed-under-block-limit](suggested-speed-under-block-limit.md); the lower of
the two applies.

## Notes

- Why T: the train controllers keep the commanded speed and brake only when their
  authority drops to 0. Any lag before the brake takes hold then carries a train
  beyond the end of its authority. The waysides hold two trains in neighbouring blocks,
  and a train stopped on a switch's block locks that switch, so one block too far can
  stop a line for good.
- 3 s covers a 2 s reaction and a step's lag. On a flat 100 m block it gives 11 m/s,
  where the bare stopping speed is 14 m/s.
- The distance left in the train's own block is not counted, because the CTC Office
  does not know which way the train is heading through it. This is on the safe side.
- A block's grade is used as listed, whichever way the train runs through it, as the
  Track Model gives it to the Train Model.
- Rolling resistance, which helps a train stop, is not counted.

## Supersedes

- Deceleration: previously a fixed 1.2 m/s², the service deceleration on level track
  at 2/3 load. A full train on a downhill block stops more slowly, and overran its
  authority.
- Stopping margin: previously none (Landis 2026-11-09). With none, trains rolled one
  block past a stop and the Red line locked up (2026-11-12).
