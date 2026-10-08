# one-train-per-block

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-04 (a safety requirement, so that trains cannot collide; enforced by the CTC Office by rejecting the input)
**Aliases:** one train per block, block exclusivity, no two trains in a block, collision avoidance
**Last updated:** 2026-10-04

## Definition

At most one train may occupy a block at a time, so that trains cannot collide. A block
is identified by its line and block number (`conventions/identifiers.md`), so the same
block number on two lines names two different blocks.

## CTC Office

The CTC Office rejects Track Controller input that reports two trains in the same block,
or one train twice, as invalid. Nothing in a rejected input is applied.

## Notes

- The rule covers reported positions. Two trains may still be dispatched to the same
  destination block.
- Open: how the other modules enforce it, and what the CTC Office does at integration
  when it receives such a report beyond rejecting it, are not decided.
