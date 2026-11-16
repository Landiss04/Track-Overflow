**Target:** truth/decisions/D043-ctc-manual-stop-queue.md
**Action:** create
**Proposed by:** Claude Code on integrate/harness-into-development
**Provenance:** Replaces the unpromoted proposal `20261116-0122-ctc-manual-stop-queue.md` on this branch, keeping all of it and adding how "return to yard" fits the queue. Landis asserted on 2026-11-16 that return to yard is queued like the other stations, and no longer replaces the stop the train is heading for and its queued stops.

---

# D043-ctc-manual-stop-queue

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-11-16 (design review feedback: the dispatcher should be able to dispatch and queue station stops in Manual mode; return to yard is queued like the other stations)
**Aliases:** stop queue, queued stops, queue stop, manual stop queue, manual itinerary, queued return to yard
**Last updated:** 2026-11-16

## Context

In Manual mode the dispatcher sent a train to one station (station and arrival time), and
the train stayed there until another command. The design review asked that the
dispatcher be able to dispatch a train and also queue its later station stops. "Return to
yard" then still replaced the stop the train was heading for and every stop queued after
it.

## Decision

- In Manual mode a train has a list of stops: the stop it is heading for, then the stops
  queued after it. Each stop uses the same station logic as a dispatch (a station and an
  arrival time). The train makes them in order.
- The list replaces the "dispatch to a block" area of the Manual view and scrolls.
- The action button reads **Dispatch train** while the train is not dispatched
  anywhere, and **Queue stop** while it is on its way to a station; Queue stop adds the
  stop after the last one.
- Each queued stop is a card with a control (×) that removes it from the queue.
- The dispatcher can reorder the stops by dragging a card and by up and down arrows.
- **Return to yard is queued like a station.** It adds the yard as the train's last
  stop, after the stop it is heading for and those queued after it, which the train still
  makes. A train with no stops goes back at once. Once the yard is the stop it is heading
  for, it is on its way back and is retired there (D022).
- The yard stays the last stop: a stop queued after it goes just before it, and neither
  the yard nor a stop after it can be moved. Removing the yard's card withdraws the
  return.

## Consequences

- REQ-FUNC-009 (dispatch to a block) is kept by letting a stop be a block of the line as
  well as a station; there is no separate block row.
- A change to a train's first stop is still subject to the CTC Office's safety checks:
  it is refused rather than leave a moving train an authority it cannot stop within.
- Not decided here: when the dwell at a queued stop is timed from, whether block stops
  get the 45 s dwell, whether a train's only stop may be removed (see the
  no-dispatcher-order-cancel proposals), and whether queues advance in Automatic mode.
