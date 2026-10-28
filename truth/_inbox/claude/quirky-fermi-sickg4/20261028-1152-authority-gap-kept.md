**Target:** truth/arbitration/authority-stops-before-obstruction.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** Landis's reply relayed by Kevin Schillinger 2026-10-28 ("we need to keep that one block gap and ensure that the two trains are never given authority that would put them in adjacent blocks"; "the CTC should prevent a train from receiving authority to move into a position that would eliminate the required gap"), and Kevin Schillinger 2026-10-28 ("the gap should be kept"); resolves the Conflict in proposal `20261027-1819-authority-one-empty-block-conflict.md`; rest of the entry as on origin/truth

---

# authority-stops-before-obstruction

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-06 (authority shrinks for a train ahead that is not moving and for block closures; the CTC Office recomputes it from current train locations and occupied and closed blocks; switches count only as reported; manual Set authority picks a block); route follows the direction of travel in the layout files, supplied by Landis 2026-10-06; one empty block between trains, decided by Braden Bosilovich and Harry Tye 2026-10-26 and agreed by Landis 2026-10-28, relayed by Kevin Schillinger; no authority that would put two trains in adjacent blocks, asserted by Landis 2026-10-28
**Aliases:** authority update, authority truncation, safe authority, blocks remaining, one empty block between trains, train separation gap, required gap
**Last updated:** 2026-10-28

## Definition

The CTC Office recomputes every dispatched train's authority (a count of blocks, see
[D013](../decisions/D013-authority-block-count.md)) from the current reports, every
step, for as long as the train is on the track. The count runs along the train's route
from its current block toward its destination and ends at the earliest of:

- the destination block;
- the block before the first block ahead that is closed or closing, or within another
  train's authority ([exclusive-authority](exclusive-authority.md));
- the block before the first block ahead that is occupied or failed;
- the block before a switch that is not reported set for the route. A switch whose
  position has not been reported counts as not set.

One empty block always stays between trains: no train receives authority that would
put it in a block adjacent to another train. Authority never ends in a block next to a
block that another train occupies (or a failed block) or that another train's
authority holds. A train in block 30 with another in block 32 and block 31 empty has
an authority of 0; with the other in block 33, 1 (to 31).

## Notes

- The route is the shortest path a train can run through the track layout files in
  `TrackModel/`, switch connections included, keeping each block's direction of travel
  (`conventions/files-and-paths.md`) and never turning back.
- In manual mode the dispatcher's Set authority picks the block the train is to reach;
  the CTC Office converts it to a count, under the same limits.
- Dispatches into unusable blocks are still refused:
  [no-authority-into-unusable-block](no-authority-into-unusable-block.md).
- Why a gap: a wayside has no direction and no memory between scans, so it holds a
  train while a neighbouring block is occupied. Two trains in adjacent blocks hold
  each other, leader and follower alike, and deadlock.

## Supersedes

- Occupied block ahead: previously the count ended at the block before it (Landis
  2026-10-06); now no authority ends next to another train, so one empty block stays
  between trains (Braden Bosilovich and Harry Tye 2026-10-26, agreed by Landis
  2026-10-28).
- Conflict between those two values resolved by Landis 2026-10-28.
- Route: previously the shortest path with no direction of travel (pending proposal
  `20261006-1702`); now it keeps the layout files' direction of travel.
