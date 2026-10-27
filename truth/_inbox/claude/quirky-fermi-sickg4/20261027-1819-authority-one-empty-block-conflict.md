**Target:** truth/arbitration/authority-stops-before-obstruction.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** `documents/module-owner-review-braden.md` (branch `feature/TrackCtrl-HW-vital`, `a5bd465`), CTC-1 and CTC-2: decision by Braden Bosilovich and Harry Tye 2026-10-26; current entry asserted by Landis 2026-10-06

---

# authority-stops-before-obstruction

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-06 (authority shrinks for a train ahead that is not moving and for block closures; the CTC Office recomputes it from current train locations and occupied and closed blocks; switches count only as reported; manual Set authority picks a block); route follows the direction of travel in the layout files, supplied by Landis 2026-10-06; one empty block between trains, decided by Braden Bosilovich and Harry Tye 2026-10-26 (module owner review CTC-1, CTC-2), not yet agreed by Landis
**Aliases:** authority update, authority truncation, safe authority, blocks remaining, one empty block between trains, train separation gap
**Last updated:** 2026-10-27

## Definition

The CTC Office recomputes every dispatched train's authority (a count of blocks, see
[D013](../decisions/D013-authority-block-count.md)) from the current reports, every
step, for as long as the train is on the track. The count runs along the train's route
from its current block toward its destination and ends at the earliest of:

- the destination block;
- the block before the first block ahead that is closed or closing, or within another
  train's authority ([exclusive-authority](exclusive-authority.md));
- before the first block ahead that is occupied or failed: see Conflict;
- the block before a switch that is not reported set for the route. A switch whose
  position has not been reported counts as not set.

## Notes

- The route is the shortest path a train can run through the track layout files in
  `TrackModel/`, switch connections included, keeping each block's direction of travel
  (`conventions/files-and-paths.md`) and never turning back.
- In manual mode the dispatcher's Set authority picks the block the train is to reach;
  the CTC Office converts it to a count, under the same limits.
- Dispatches into unusable blocks are still refused:
  [no-authority-into-unusable-block](no-authority-into-unusable-block.md).
- Why a gap: a wayside has no direction and no memory between scans, so it holds a
  train while a block the train could move into is occupied. Two trains in adjacent
  blocks on two-way track hold each other, leader and follower alike.

## Conflict

- **One block short (Landis 2026-10-06):** the count ends at the block before the
  first occupied or failed block. A train in block 30 with a destination of block 37
  and another train standing in block 32 has an authority of 1.
- **One empty block between trains (Braden Bosilovich and Harry Tye 2026-10-26):** the
  count ends two blocks before the first occupied or failed block. A train in block 30
  with another standing in block 33 has an authority of 1 (to 31); with the other in
  block 32, 0.
- **Owner to resolve:** Landis.

## Supersedes

- Route: previously the shortest path with no direction of travel (pending proposal
  `20261006-1702`); now it keeps the layout files' direction of travel.
