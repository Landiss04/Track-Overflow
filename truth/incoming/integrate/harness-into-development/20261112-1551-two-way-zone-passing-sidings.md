**Target:** truth/arbitration/two-way-zone-direction-reservation.md
**Action:** create
**Proposed by:** Claude on integrate/harness-into-development
**Provenance:** Replaces the unpromoted proposal `20261112-1433-two-way-zone-pass-can-stop.md` on this branch (which replaced `-1334-` and `-1045-`). It keeps every rule of 1433 and adds three things:
- The passing sidings, turned on: Landis asserted 2026-11-03 that a run comes back over the parallel track so those stretches are one way, and 2026-11-12 ("lets turn on the passings").
- Which way each one-way stretch is run.
- Room on one-way track between two shared stretches.

The last two are proposed by Claude, awaiting Landis's confirmation. Each one stopped a whole line on the CTC Office tests' railway: without the fixed direction Red kept one shared stretch, 16–52, and without the room rule all ten Red runs stood still at 06:00.

---

# two-way-zone-direction-reservation

**Status:** current
**Owner:** Landis
**Provenance:**
- Landis, reply to module owner review CTC-1 and SW-2, relayed by Kevin Schillinger 2026-10-25.
- Runs must not be scheduled to meet head-on: asserted by Landis 2026-10-15.
- Held in the yard for the first shared stretch: asserted by Landis 2026-11-03.
- Waiting short of a stretch, claiming only the next one, and loop capacity: proposed 2026-11-03, awaiting Landis's confirmation.
- A train not yet in the stretch gives up its claim to a train waiting to come back, if it can still stop short of it; and four trains in Green's loop through section N: asserted by Landis 2026-11-12.
- Back over a parallel track, so those stretches are one way: asserted by Landis 2026-11-03. Turned on: asserted by Landis 2026-11-12.
- Which way each one-way stretch is run, and room on one-way track: proposed 2026-11-12, awaiting Landis's confirmation.
**Aliases:** two-way zone, shared stretch, zone reservation, direction reservation, head-on protection, Red concurrency, yard hold, loop capacity, loop limit, passing siding, passing loop
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
- **Passing sidings.**
  - Where a parallel track runs beside the main line (Red 72–76 beside 28–32, 67–71
    beside 39–43), the runs go out toward the loop on the main line and come back on the
    parallel track. Those stretches are then one way each, and the shared stretches
    between them are short: Red 9–27, 33–38 and 44–52, not 16–52. Trains going opposite
    ways pass there.
  - Which track each way takes is the same for every run. Avoiding only track a run has
    already run does not keep them one way: a run's first leg can go out and back.
  - The CTC Office asks the Track Controller to set each switch for the run's way
    (route requests). A run keeps to that way while a train stands on it; it takes
    another way only past a closed or failed block.
- **Loops.**
  - A loop a train runs out and back through (Green 86–100 and 1–12, Red 53–66) is its
    own one-way section, not part of the shared stretch. Every run goes round it the
    same way (Red: in at 53, out from 66).
  - A train that has turned waits a block short of the loop's end until the trains
    following it have cleared the stretch outbound; then they come home together in the
    same direction.
  - No more trains go into a stretch toward a loop than the loop holds, a block apart.
  - Green's loop through section N (77–85 and 86–100) takes no more than four. The
    Green Track Controller holds the train on 75 while more than five of blocks 76–100
    are occupied, a hold the CTC Office cannot see. While trains come back down N no
    train goes up it, so four keeps 76–100 under that limit.
- **Room beyond a stretch.** No train is sent through a shared stretch onto one-way
  track before the next shared stretch unless that track has room for it: as many trains
  as it holds a block apart, counting those on it and those in the stretch heading onto
  it. Otherwise a train would stand in the stretch, holding it, while the trains it waits
  for wait for that stretch.
- **The yard block** is part of a stretch the runs cross both ways. A returning train
  holds the stretch inbound until it is retired into the yard, so a new train is
  released only while the stretch is empty or already held outbound.
- **A train waiting to come back has its stretch next.**
  - No further train is sent into that stretch outbound for the first time, even when
    due. Trains whose way out starts with another stretch still go.
  - A train already sent into it outbound but not yet in it gives up its claim. One
    not yet released from the yard waits in the yard. One on the track waits short of
    the stretch, where it would have been held, but only if it can stop there at the
    speed it was last suggested.
  - A train that cannot stop in time keeps its claim and goes through, and so does a
    train already in the stretch. A train cut off too late would stop on the block
    beyond, which can be the block a switch into the stretch is listed on; the train
    coming back would then need that switch, and the wayside will not move it under a
    train.
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
- "Can stop" uses the CTC Office's own suggested speed: the speed it was last given is
  no more than the speed it would be given with its authority ending at the wait block.
- The Red Track Controller follows route requests at switches 15, 27, 32, 38, 43 and 52
  (PR #58).

## Supersedes

- Trains on the track: previously only a train still in the yard gave up its claim. In
  the Schedule v4 full-system run of 2026-11-12, G10 had claimed 13–28 inbound and was
  held on 148 by the Green Track Controller's loop guard, while G1 waited at 2 to come
  back. Neither moved again.
- Loop capacity on Green section N: previously as many as the loop holds, seven.
- Passing sidings: previously off, so Red was one shared stretch, 16–52, and its runs
  went one at a time.
