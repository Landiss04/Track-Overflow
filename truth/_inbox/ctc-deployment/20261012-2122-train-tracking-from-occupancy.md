**Target:** truth/arbitration/train-tracking-from-occupancy.md
**Action:** create
**Proposed by:** Claude on ctc-deployment
**Provenance:** asserted by Landis 2026-10-12 (CTC module feedback: the CTC Office knows only block occupancy and its own plans, never a train's actual speed, and infers from the last state whether a train or a failure occupies a block); which waiting train leaves the yard first proposed by Claude on ctc-deployment 2026-10-12 for Landis to confirm

---

# train-tracking-from-occupancy

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-12 (CTC module feedback: the CTC Office knows only block occupancy and its own plans, never a train's actual speed, and infers from the last state whether a train or a failure occupies a block); which waiting train leaves the yard first proposed by Claude on ctc-deployment 2026-10-12 for Landis to confirm
**Aliases:** train tracking, occupancy inference, failure inference, last-state logic, yard exit
**Last updated:** 2026-10-12

## Definition

The CTC Office works out where its trains are from
[block occupancy](../signals/block-occupancy.md) alone, comparing each update with the
last, its trains' assigned routes and its suggested speeds:

- **Leaving the yard.** When a line's yard exit block (Green 63, Red 9) becomes
  occupied while a train dispatched on that line is waiting in the yard, that train has
  left the yard into it.
- **Moving.** A train moves into the next block on its assigned route when that block
  becomes occupied, and leaves a block when that block clears. While crossing a block
  boundary it occupies both blocks.
- **Too early is a failure.** If the next block on a train's route becomes occupied
  sooner than the train could reach it at its suggested speed, it is a failure, not the
  train. The margin is generous: sooner than half the time the train would need.
- **Unexplained occupancy is a failure.** A block that becomes occupied and is not
  explained by any train is a failure.
- **Lost trains are dropped quietly.** When a train's blocks all clear and no next
  block becomes occupied, outside the yard, the CTC Office stops tracking it. Its order
  stays.

## Failures

An inferred failure is treated as a failed block: no authority is given into it and
routes go around it. The CTC Office's UIs show it only as an occupied block, never as
a failure.

## Notes

- The CTC Office never knows a train's actual speed. It shows the speed it suggests.
- If several trains on a line are waiting in the yard, the one dispatched first leaves
  first (proposed by Claude, to confirm).

## Conflict

**Resolution owner:** Landis.

**Orders into an inferred failure. Open.**

| Value | Provenance |
|-------|------------|
| Cancelled, and the dispatcher told, as for any failed block | [no-authority-into-unusable-block](no-authority-into-unusable-block.md) `## Existing orders` |
| The UIs show an inferred failure only as an occupied block | Landis 2026-10-12, above |

Telling the dispatcher an order was cancelled because of a failure would show the
failure.
