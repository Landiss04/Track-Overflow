**Target:** truth/arbitration/suggested-speed-stops-within-authority.md
**Action:** replace
**Proposed by:** Claude on integrate/harness-into-development
**Provenance:** asserted by Landis 2026-11-09 (the suggested speed is to allow for each block's grade and a full train, with no added stopping margin, after a full train on a downhill block overran its authority); constants from `modules/train-model.md`

---

# suggested-speed-stops-within-authority

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-06 (issue a safe suggested speed so trains do not run up on each other); each block's grade and a full train asserted by Landis 2026-11-09; constants from `modules/train-model.md` (Datasheet, Design)
**Aliases:** safe suggested speed, authority-aware speed, braking speed
**Last updated:** 2026-11-09

## Definition

The CTC Office's suggested speed for a train is never more than the speed from which
a full train can stop, under the service brake, within its authority:
√(Σ 2 × aᵢ × dᵢ), rounded down to a whole m/s, summed over the blocks within its
authority, where dᵢ is a block's length and aᵢ is the deceleration on that block:

aᵢ = F ÷ m + g × sin(atan(grade ÷ 100))

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

- No stopping margin is added beyond this calculation (Landis 2026-11-09).
- The distance left in the train's own block is not counted, because the CTC Office
  does not know which way the train is heading through it. This is on the safe side.
- A block's grade is used as listed, whichever way the train runs through it, as the
  Track Model gives it to the Train Model.
- Rolling resistance, which helps a train stop, is not counted.

## Supersedes

- Deceleration: previously a fixed 1.2 m/s², the service deceleration on level track at 2/3 load; a full train on a downhill block stops more slowly and overran its authority.
