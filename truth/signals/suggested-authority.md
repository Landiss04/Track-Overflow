# suggested-authority

**Status:** current
**Owner:** CTC Office
**Provenance:** asserted by Landis 2026-10-02 (CTC architecture diagram, `ctc-architecture.html`); authority as a count of blocks per D013 (team decision including Kevin, asserted by Landis 2026-10-06); the block the train is in sent with it, agreed by Landis and Harry Tye (Track Controller SW) in chat 2026-10-14, and confirmed by Kevin Schillinger 2026-10-16; a second value for the next block on the train's route, agreed in the CTC Office's answers of 2026-10-20, relayed by Kevin Schillinger
**Aliases:** Authority (CTC), CTC authority, suggested authority, blocks remaining
**Last updated:** 2026-10-20

## Definition

The number of blocks the CTC Office suggests one train may still enter before it must
stop, sent to the Track Controller as a non-negative integer. Up to two values per
train, each sent with the train's ID and line and the block it is for, per
`conventions/identifiers.md`:

- one for the block the train is in; and
- while that count is at least 1, one for the next block on the train's route, one
  less than the count for the block the train is in.

The block the train is in is the one its head is in, as the CTC Office follows it from
[block occupancy](block-occupancy.md); while the train crosses into the next block, it
is the block it is entering. The Track Controller sees only which blocks are occupied,
so the block tells it which track circuit the authority belongs to.

The count is of the blocks ahead of that block, along the train's route; that block is
not counted. 0 means the train must stop before leaving it. See
[D013](../decisions/D013-authority-block-count.md).

## Notes

- Sent together with [suggested-speed](suggested-speed.md), for the same train and
  block.
- At 0 nothing is sent for the next block: the train must not enter it.
- The next block always lies within the train's own exclusive authority
  ([exclusive-authority](../arbitration/exclusive-authority.md)), so no two trains'
  values name the same block.
- The Track Controller passes the authority for that train down that block's track
  circuit (Landis and Harry Tye, 2026-10-14).
- Distinct from the authority in [track-signal](track-signal.md), which the Track Model
  sends to the Train Model. Both are block counts.
- Confirmed by the Track Controller SW owner; the Track Controller HW owner has not
  confirmed it.

## Supersedes

- Keyed by train ID alone, with no position. Now sent with the train's line and the
  block its head is in, because the Track Controller cannot tell which occupied block
  a train ID is in (Landis and Harry Tye, 2026-10-14).
- One value per train: now up to two, adding the next block on the train's route (2026-10-20).
