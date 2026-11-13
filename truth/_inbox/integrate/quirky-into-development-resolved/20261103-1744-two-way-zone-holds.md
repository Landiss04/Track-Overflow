**Target:** truth/arbitration/two-way-zone-direction-reservation.md
**Action:** create
**Proposed by:** Claude on integrate/quirky-into-development-resolved
**Provenance:** Replaces the unpromoted proposal `20261025-2128-two-way-zone-direction-reservation.md` (on `claude/quirky-fermi-sickg4`), whose rules it keeps. Adds: trains held in the yard rather than queuing on the line for the first shared stretch on their way, asserted by Landis 2026-11-03 (answer "Hold in the yard" to the Green 77–85 queue question); waiting short of a shared stretch on one-way track, claiming only the next stretch, and a loop holding no more trains than fit in it, proposed by Claude 2026-11-03 to keep runs in the schedule's order (D020) from jamming, not yet confirmed by Landis.

---

# two-way-zone-direction-reservation

**Status:** current
**Owner:** Landis
**Provenance:** Landis, reply to module owner review CTC-1 and SW-2, relayed by Kevin Schillinger 2026-10-25; runs must not be scheduled to meet head-on, asserted by Landis 2026-10-15; held in the yard for the first shared stretch, asserted by Landis 2026-11-03; waiting short of a stretch, claiming only the next one, and loop capacity, proposed 2026-11-03 and awaiting Landis's confirmation
**Aliases:** two-way zone, shared stretch, zone reservation, direction reservation, head-on protection, Red concurrency, yard hold, loop capacity
**Last updated:** 2026-11-03

## Definition

Automatic dispatch never sends trains to meet head-on. Track the scheduled runs
cross in both directions is a shared stretch, reserved by direction, not by train:

- Several trains may hold a shared stretch at once if they all travel it the same
  way. A train that needs it the other way waits until no train holds it in the
  opposing direction.
- A train waits in the yard while the first shared stretch on its way out is held
  the other way, so the line does not fill up with trains queuing for it. Further on,
  it waits on one-way track a block short of a stretch held the other way, or at its
  last stop where there is no such track.
- A train claims a shared stretch only when it is the next one ahead of it, never one
  it is still far from.
- A loop a train runs out and back through (Green 86–100 and 1–12, Red 53–66) is its
  own one-way section, not part of the shared stretch. A train that has turned waits a
  block short of the loop's end until the trains following it have cleared the stretch
  outbound; then they come home together in the same direction. No more trains go
  into a stretch toward a loop than the loop holds, a block apart.
- The yard block is part of a stretch the runs cross both ways. A returning train
  holds the stretch inbound until it is retired into the yard, so a new train is
  released only while the stretch is empty or already held outbound.
- Once a train is waiting to come back over a stretch, no further train is
  released into it outbound, even when due.
- A train is never dispatched into a head-on deadlock.

## Notes

- Following trains are kept apart by
  [one-train-per-block](one-train-per-block.md),
  [exclusive-authority](exclusive-authority.md) and
  [authority-stops-before-obstruction](authority-stops-before-obstruction.md),
  not by this rule.
- Applies to the CTC Office's automatic dispatch from the schedule (D020).
