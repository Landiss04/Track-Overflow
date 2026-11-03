**Target:** truth/arbitration/two-way-zone-direction-reservation.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** Landis's replies to `documents/module-owner-review.md` CTC-1 and SW-2, relayed by Kevin Schillinger 2026-10-25

---

# two-way-zone-direction-reservation

**Status:** current
**Owner:** Landis
**Provenance:** Landis, reply to module owner review CTC-1 and SW-2, relayed by Kevin Schillinger 2026-10-25; runs must not be scheduled to meet head-on, asserted by Landis 2026-10-15
**Aliases:** two-way zone, shared stretch, zone reservation, direction reservation, head-on protection, Red concurrency
**Last updated:** 2026-10-25

## Definition

Automatic dispatch never sends trains to meet head-on. Track the scheduled runs
cross in both directions is a shared stretch, reserved by direction, not by train:

- Several trains may hold a shared stretch at once if they all travel it the same
  way. A train that needs it the other way waits until no train holds it in the
  opposing direction.
- A loop a train runs out and back through (Red 53–66) is its own one-way section,
  not part of the shared stretch. A train that has turned waits there until the
  trains following it have cleared the stretch outbound; then they come home
  together in the same direction.
- The yard block is part of a stretch the runs cross both ways (Red 9 on a course
  out and back over 9–52). A returning train holds the stretch inbound until it is
  retired into the yard, so a new train is released only while the stretch is
  empty or already held outbound.
- Once a train is waiting to come back over a stretch, no further train is
  released into it outbound, even when due.
- A train waits to be released toward the yard until that is safe, or is routed
  around oncoming trains. It is never dispatched into a head-on deadlock.

## Notes

- Following trains are kept apart by
  [one-train-per-block](one-train-per-block.md),
  [exclusive-authority](exclusive-authority.md) and
  [authority-stops-before-obstruction](authority-stops-before-obstruction.md),
  not by this rule.
- Applies to the CTC Office's automatic dispatch from the schedule (D020).
