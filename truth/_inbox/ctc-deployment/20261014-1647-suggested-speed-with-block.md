**Target:** truth/signals/suggested-speed.md
**Action:** replace
**Proposed by:** Claude on ctc-deployment
**Provenance:** asserted by Landis 2026-10-02 (CTC architecture diagram, `ctc-architecture.html`); integer type asserted by Landis 2026-10-04; the block the train is in sent with it, agreed by Landis and Harry Tye (Track Controller SW) in chat 2026-10-14

---

# suggested-speed

**Status:** current
**Owner:** CTC Office
**Provenance:** asserted by Landis 2026-10-02 (CTC architecture diagram, `ctc-architecture.html`); integer type asserted by Landis 2026-10-04; the block the train is in sent with it, agreed by Landis and Harry Tye (Track Controller SW) in chat 2026-10-14
**Aliases:** Suggested Speed, CTC suggested speed
**Last updated:** 2026-10-14

## Definition

The speed the CTC Office suggests for one train, sent to the Track Controller as an
integer in m/s. One value per train, keyed by train ID, sent with the train's line and
the block the train is in, per `conventions/identifiers.md`.

The block is the one the train's head is in, as the CTC Office follows the train from
[block occupancy](block-occupancy.md); while the train crosses into the next block, it
is the block it is entering. The Track Controller sees only which blocks are occupied,
so the block tells it which track circuit the speed belongs to.

It is not the train's actual speed: it is the speed the CTC Office suggests the train
run at to keep a safe operating distance from other trains.

## Notes

- Sent together with [suggested-authority](suggested-authority.md), for the same train
  and block.
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
