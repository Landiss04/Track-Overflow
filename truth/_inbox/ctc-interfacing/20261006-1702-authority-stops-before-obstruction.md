**Target:** truth/arbitration/authority-stops-before-obstruction.md
**Action:** create
**Proposed by:** Claude on ctc-interfacing
**Provenance:** asserted by Landis 2026-10-06 (authority shrinks for a train ahead that is not moving and for block closures; the CTC Office recomputes it from current train locations and occupied and closed blocks; switches count only as reported; manual Set authority picks a block; direction of travel omitted for now)

---

# authority-stops-before-obstruction

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-06 (authority shrinks for a train ahead that is not moving and for block closures; the CTC Office recomputes it from current train locations and occupied and closed blocks; switches count only as reported; manual Set authority picks a block; direction of travel omitted for now)
**Aliases:** authority update, authority truncation, safe authority, blocks remaining
**Last updated:** 2026-10-06

## Definition

The CTC Office recomputes every dispatched train's authority (a count of blocks, see
[D013](../decisions/D013-authority-block-count.md)) from the current reports, every
step, for as long as the train is on the track. The count runs along the train's route
from its current block toward its destination and ends at the earliest of:

- the destination block;
- the block before the first block ahead that is occupied, closed, closing, or failed;
- the block before a switch that is not reported set for the route. A switch whose
  position has not been reported counts as not set.

A train in block 1 with a destination of block 8 and another train standing in block 3
has an authority of 1. When the other train moves on, the authority grows again.

## Notes

- In manual mode the dispatcher's Set authority picks the block the train is to reach;
  the CTC Office converts it to a count, under the same limits.
- Direction of travel is not modeled yet. Until it is, the route is the shortest path
  through the track layout files in `TrackModel/`, switch connections included.
- Dispatches into unusable blocks are still refused:
  [no-authority-into-unusable-block](no-authority-into-unusable-block.md).
