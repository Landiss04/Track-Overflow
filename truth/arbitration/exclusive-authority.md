# exclusive-authority

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-06 (trains must not collide; a contested block goes to the train most behind schedule; a granted block is kept until the train has passed through it)
**Aliases:** block reservation, no overlapping authority, collision avoidance, contested block
**Last updated:** 2026-10-06

## Definition

No block is within the authority of two trains at once. Two trains can therefore never
be cleared into the same block, whatever speeds they run at.

- **Kept until passed.** Once a block is within a train's authority, it stays with that
  train until the train has passed through it. Another train cannot take it, whatever
  its priority. Occupied, closed, closing and failed blocks, and switches not set for
  the route, still cut the authority short
  ([authority-stops-before-obstruction](authority-stops-before-obstruction.md)).
- **Contested blocks.** A block no train holds yet goes to the train most behind
  schedule: the one with the least slack between its requested arrival and the time it
  needs to run the rest of its route at each block's speed limit. A train with no
  requested arrival comes after every train with one. Ties go to the train with the
  lower train ID.

## Notes

- Another train's authority stops a train's authority like an occupied block does.
- Which train gives way decides only who waits. Slowing trains down to meet the
  schedule is not covered by this entry.
