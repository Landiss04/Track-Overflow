# suggested-speed

**Status:** current
**Owner:** CTC Office
**Provenance:** asserted by Landis 2026-10-02 (CTC architecture diagram, `ctc-architecture.html`); integer type asserted by Landis 2026-10-04; the block the train is in sent with it, agreed by Landis and Harry Tye (Track Controller SW) in chat 2026-10-14, and confirmed by Kevin Schillinger 2026-10-16; a second value for the next block on the train's route, agreed in the CTC Office's answers of 2026-10-20, relayed by Kevin Schillinger
**Aliases:** Suggested Speed, CTC suggested speed
**Last updated:** 2026-10-20

## Definition

The speed the CTC Office suggests for one train, sent to the Track Controller as an
integer in m/s. Up to two values per train, each sent with the train's ID and line and
the block it is for, per `conventions/identifiers.md`:

- one for the block the train is in; and
- while the train's authority is at least 1, one for the next block on its route.

The speed for the next block is worked out for that block, from its own speed limit
and the stopping distance left with one block less authority. It is not a copy of the
speed for the block the train is in.

The block the train is in is the one its head is in, as the CTC Office follows it from
[block occupancy](block-occupancy.md); while the train crosses into the next block, it
is the block it is entering. The Track Controller sees only which blocks are occupied,
so the block tells it which track circuit the speed belongs to.

It is not the train's actual speed: it is the speed the CTC Office suggests the train
run at to keep a safe operating distance from other trains.

## Notes

- Sent together with [suggested-authority](suggested-authority.md), for the same train
  and block.
- The next-block value closes the gap between a train entering a block and the CTC
  Office seeing it there, during which that block would otherwise carry no values.
- The next block always lies within the train's own exclusive authority
  ([exclusive-authority](../arbitration/exclusive-authority.md)), so no two trains'
  values name the same block.
- The Track Controller derives the commanded speed it sends down that block's track
  circuit from it (Harry Tye, 2026-10-14).
- Distinct from the commanded speed in [track-signal](track-signal.md), which the Track
  Model sends to the Train Model.
- The unit is m/s per `conventions/units.md`; UIs show it in mph.
- Confirmed by the Track Controller SW owner; the Track Controller HW owner has not
  confirmed it.

## Supersedes

- Keyed by train ID alone, with no position. Now sent with the train's line and the
  block its head is in, because the Track Controller cannot tell which occupied block
  a train ID is in (Landis and Harry Tye, 2026-10-14).
- One value per train: now up to two, adding the next block on the train's route (2026-10-20).
