# train-tracking-from-occupancy

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-12 (CTC module feedback: the CTC Office knows only block occupancy and its own plans, never a train's actual speed, and infers from the last state whether a train or a failure occupies a block; the waiting train most behind schedule leaves the yard first; orders into an inferred failure are kept); the train leaving the yard known from the CTC Office's own release, agreed in the CTC Office's answers of 2026-10-20, relayed by Kevin Schillinger
**Aliases:** train tracking, occupancy inference, failure inference, last-state logic, yard exit
**Last updated:** 2026-10-20

## Definition

The CTC Office works out where its trains are from
[block occupancy](../signals/block-occupancy.md) alone, comparing each update with the
last, its trains' assigned routes and its suggested speeds:

- **Leaving the yard.** The CTC Office releases one train per line at a time from the
  yard ([D022](../decisions/D022-yard-black-box.md)), so the train in a line's yard exit
  block (Green 63, Red 9) is the one it last released there.
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
a failure. Orders into it are kept, and a dispatch into it is not refused: the train
waits short of it and goes on once it clears.

## Notes

- The CTC Office never knows a train's actual speed. It shows the speed it suggests.
