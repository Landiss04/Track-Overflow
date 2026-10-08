# authority-stops-before-obstruction

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-06 (authority shrinks for a train ahead that is not moving and for block closures; the CTC Office recomputes it from current train locations and occupied and closed blocks; switches count only as reported; manual Set authority picks a block); route follows the direction of travel in the layout files, supplied by Landis 2026-10-06
**Aliases:** authority update, authority truncation, safe authority, blocks remaining
**Last updated:** 2026-10-06

## Definition

The CTC Office recomputes every dispatched train's authority (a count of blocks, see
[D013](../decisions/D013-authority-block-count.md)) from the current reports, every
step, for as long as the train is on the track. The count runs along the train's route
from its current block toward its destination and ends at the earliest of:

- the destination block;
- the block before the first block ahead that is occupied, closed, closing, or failed,
  or within another train's authority
  ([exclusive-authority](exclusive-authority.md));
- the block before a switch that is not reported set for the route. A switch whose
  position has not been reported counts as not set.

A train in block 30 with a destination of block 37 and another train standing in block
32 has an authority of 1. When the other train moves on, the authority grows again.

## Notes

- The route is the shortest path a train can run through the track layout files in
  `TrackModel/`, switch connections included, keeping each block's direction of travel
  (`conventions/files-and-paths.md`) and never turning back.
- In manual mode the dispatcher's Set authority picks the block the train is to reach;
  the CTC Office converts it to a count, under the same limits.
- Dispatches into unusable blocks are still refused:
  [no-authority-into-unusable-block](no-authority-into-unusable-block.md).

## Supersedes

- Route: previously the shortest path with no direction of travel (pending proposal
  `20261006-1702`); now it keeps the layout files' direction of travel.
