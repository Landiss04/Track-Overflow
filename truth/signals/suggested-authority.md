# suggested-authority

**Status:** current
**Owner:** CTC Office
**Provenance:** asserted by Landis 2026-10-02 (CTC architecture diagram, `ctc-architecture.html`); authority as a count of blocks per D013 (team decision including Kevin, asserted by Landis 2026-10-06)
**Aliases:** Authority (CTC), CTC authority, suggested authority, blocks remaining
**Last updated:** 2026-10-06

## Definition

The number of blocks the CTC Office suggests one train may still enter before it must
stop, sent to the Track Controller as a non-negative integer. One value per train,
keyed by train ID.

The count is of the blocks ahead of the train's current block, along its route; the
current block is not counted. 0 means the train must stop before leaving its current
block. See [D013](../decisions/D013-authority-block-count.md).

## Notes

- Distinct from the authority in [track-signal](track-signal.md), which the Track Model
  sends to the Train Model. Both are block counts.
- The Track Controller owner has not confirmed it.

## Supersedes

- Type: previously a block ID string naming the destination block (Landis 2026-10-02);
  now a count of blocks, per D013 (2026-10-06).
