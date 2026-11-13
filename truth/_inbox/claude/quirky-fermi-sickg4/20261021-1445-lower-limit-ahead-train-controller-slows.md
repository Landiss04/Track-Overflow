**Target:** truth/arbitration/lower-limit-ahead.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** Kevin Schillinger's direct statement of 2026-10-21 in the integration session, deciding open question Q-P4-4 of `documents/integration-handover-phase-4.md`: "for overspeed the train controller will handle slowing down immediately after entering the blcok". It declines the handover's proposal that the CTC Office cap a block's suggestion so a train can brake to the next block's limit beforehand.

---

# lower-limit-ahead

**Status:** current
**Owner:** Train Controller
**Provenance:** asserted by Kevin Schillinger 2026-10-21, deciding Q-P4-4 of `documents/integration-handover-phase-4.md`: "for overspeed the train controller will handle slowing down immediately after entering the blcok"
**Aliases:** overspeed into a slower block, lower speed limit ahead, slower block ahead, speed limit drop, no look-ahead speed cap, Q-P4-4
**Last updated:** 2026-10-21

## Definition

When the next block on a train's route has a lower speed limit than the block it is in,
the CTC Office does not lower the train's suggested speed ahead of that block to account
for it, so the train may enter the slower block above that block's limit. The Train
Controller slows the train down immediately after it enters the slower block.

## Notes

- The CTC Office's caps are unchanged: the suggested speed for a block stays under that
  block's own limit ([suggested-speed-under-block-limit](suggested-speed-under-block-limit.md))
  and lets the train stop within its authority
  ([suggested-speed-stops-within-authority](suggested-speed-stops-within-authority.md)).
- The case that raised it: on the Green Line a train leaves block 66 (70 km/h) at about
  18 m/s and enters block 67 (40 km/h, about 11.1 m/s).
- Speed regulation and enforcement of commanded and permitted speeds belong to the Train
  Controller (D009).
- Not stated: which brake the Train Controller uses, or a distance or time within which
  the train must be back under the limit.
