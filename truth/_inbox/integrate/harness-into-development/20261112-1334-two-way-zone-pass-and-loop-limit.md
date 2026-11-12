**Target:** truth/arbitration/two-way-zone-direction-reservation.md
**Action:** create
**Proposed by:** Claude on integrate/harness-into-development
**Provenance:** Replaces the unpromoted proposal `20261112-1045-two-way-zone-yard-pass.md` on this branch, whose rules it keeps except one: a train already released from the yard but not yet in the stretch now gives up its claim too, and Green's loop through section N takes four trains. Both asserted by Landis 2026-11-12. The first approves the fix for the Schedule v4 full-system run, where the Green Track Controller's D–F loop guard held a train coming to 13–28 that kept its claim while trains waited at block 2 to come back, and nothing moved again. The second: "only 4 trains to be allowed in that loop that way the track control softwares rule of 5 holds still".

---

# two-way-zone-direction-reservation

**Status:** current
**Owner:** Landis
**Provenance:**
- Landis, reply to module owner review CTC-1 and SW-2, relayed by Kevin Schillinger 2026-10-25.
- Runs must not be scheduled to meet head-on: asserted by Landis 2026-10-15.
- Held in the yard for the first shared stretch: asserted by Landis 2026-11-03.
- Waiting short of a stretch, claiming only the next one, and loop capacity: proposed 2026-11-03, awaiting Landis's confirmation.
- A train not yet in the stretch gives up its claim to a train waiting to come back, and four trains in Green's loop through section N: asserted by Landis 2026-11-12.
**Aliases:** two-way zone, shared stretch, zone reservation, direction reservation, head-on protection, Red concurrency, yard hold, loop capacity, loop limit
**Last updated:** 2026-11-12

## Definition

Automatic dispatch never sends trains to meet head-on. Track the scheduled runs
cross in both directions is a shared stretch, reserved by direction, not by train.

- **Same direction shares.** Several trains may hold a shared stretch at once if they
  all travel it the same way. A train that needs it the other way waits until no train
  holds it in the opposing direction.
- **Where a train waits.** A train waits in the yard while the first shared stretch on
  its way out is held the other way, so the line does not fill up with trains queuing
  for it. Further on, it waits on one-way track a block short of a stretch held the
  other way, or at its last stop where there is no such track.
- **Claims.** A train claims a shared stretch only when it is the next one ahead of it.
- **Loops.**
  - A loop a train runs out and back through (Green 86–100 and 1–12, Red 53–66) is its
    own one-way section, not part of the shared stretch.
  - A train that has turned waits a block short of the loop's end until the trains
    following it have cleared the stretch outbound; then they come home together in the
    same direction.
  - No more trains go into a stretch toward a loop than the loop holds, a block apart.
  - Green's loop through section N (77–85 and 86–100) takes no more than four. The
    Green Track Controller holds the train on 75 while more than five of blocks 76–100
    are occupied, a hold the CTC Office cannot see. While trains come back down N no
    train goes up it, so four keeps 76–100 under that limit.
- **The yard block** is part of a stretch the runs cross both ways. A returning train
  holds the stretch inbound until it is retired into the yard, so a new train is
  released only while the stretch is empty or already held outbound.
- **A train waiting to come back has the stretch next.**
  - No further train is sent into the stretch outbound for the first time, even when
    due.
  - A train already sent into it outbound but not yet in it gives up its claim. One
    not yet released from the yard waits in the yard; one on the track waits short of
    the stretch, where it would have been held.
  - A train already in the stretch keeps its claim.
- A train is never dispatched into a head-on deadlock.

## Notes

- Following trains are kept apart by
  [one-train-per-block](one-train-per-block.md),
  [exclusive-authority](exclusive-authority.md) and
  [authority-stops-before-obstruction](authority-stops-before-obstruction.md),
  not by this rule.
- Applies to the CTC Office's automatic dispatch from the schedule (D020).
- The Green Track Controller's loop guard for 1–12 holds a train on 145–150 while a
  train is in 7–12, and sets switches 12 and 28 for the loop's way out once 13–28 is
  clear. Giving up the claim keeps the CTC Office in step with it.

## Supersedes

- Trains on the track: previously only a train still in the yard gave up its claim. In
  the Schedule v4 full-system run of 2026-11-12, G10 had claimed 13–28 inbound and was
  held on 148 by the Green Track Controller's loop guard, while G1 waited at 2 to come
  back. Neither moved again.
- Loop capacity on Green section N: previously as many as the loop holds, seven.
