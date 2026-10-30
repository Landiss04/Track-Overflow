**Target:** truth/arbitration/authority-stops-before-obstruction.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** Replaces pending proposal `20261028-1152-authority-gap-kept.md`, whose entry it repeats with one addition: a switch's blocks are next to each other whatever position it reports. That option, put to them in module owner review CTC-3 (`documents/module-owner-review.md`), agreed by Landis and Harry Tye 2026-10-28, relayed by Kevin Schillinger ("both harry and landis agree to this option"); Landis's CTC-only table of switch 76 positions, 2026-10-28, relayed by Kevin Schillinger

---

# authority-stops-before-obstruction

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-06 (authority shrinks for a train ahead that is not moving and for block closures; the CTC Office recomputes it from current train locations and occupied and closed blocks; switches count only as reported; manual Set authority picks a block); route follows the direction of travel in the layout files, supplied by Landis 2026-10-06; one empty block between trains, decided by Braden Bosilovich and Harry Tye 2026-10-26 (module owner review CTC-1 and CTC-2, `documents/module-owner-review-braden.md`) and agreed by Landis 2026-10-28, relayed by Kevin Schillinger; no authority that would put two trains in adjacent blocks, asserted by Landis 2026-10-28; a switch's blocks adjacent whatever its reported position, agreed by Landis and Harry Tye 2026-10-28 (module owner review CTC-3), relayed by Kevin Schillinger
**Aliases:** authority update, authority truncation, safe authority, blocks remaining, one empty block between trains, train separation gap, required gap, gap at a switch
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
an authority of 0; with the other in block 33, 1 (to 31). When the other train moves
on, the authority grows again.

Blocks joined by a switch are adjacent whatever position the switch reports, so the gap
is kept at a switch too, including where the count ends because the switch is not set
for the route. On the Green Line, switch 76 reverse joins 77 to 101; a train on 77 is
still adjacent to 76, so a train on 75 bound through 76 has an authority of 0.

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
- Why at a switch whatever its position: a wayside locks a switch while the block it is
  listed on is occupied. A follower let into Green 76 while switch 76 is reverse for a
  train on 77 holds the switch reverse once that train has gone into 101, and its route
  to 77 never opens.

## Supersedes

- Occupied block ahead: previously the count ended at the block before it (Landis
  2026-10-06); now no authority ends next to another train, so one empty block stays
  between trains (Braden Bosilovich and Harry Tye 2026-10-26, agreed by Landis
  2026-10-28).
- Conflict between those two values resolved by Landis 2026-10-28.
- Gap at a switch: previously the count stopped at a switch not set for the route
  without the gap; now the gap is kept there too (Landis and Harry Tye 2026-10-28).
- Route: previously the shortest path with no direction of travel (pending proposal
  `20261006-1702`); now it keeps the layout files' direction of travel.
