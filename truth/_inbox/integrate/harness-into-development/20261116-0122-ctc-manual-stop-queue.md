**Target:** truth/decisions/D043-ctc-manual-stop-queue.md
**Action:** create
**Proposed by:** Claude Code on integrate/harness-into-development
**Provenance:** asserted by Landis 2026-11-16 (design review feedback relayed to the CTC Office owner)

---

# D043-ctc-manual-stop-queue

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-11-16 (design review feedback: the dispatcher should be able to dispatch and queue station stops in Manual mode)
**Aliases:** stop queue, queued stops, queue stop, manual stop queue, manual itinerary
**Last updated:** 2026-11-16

## Context

In Manual mode the dispatcher sent a train to one station (station and arrival time), and
the train stayed there until another command. The design review asked that the
dispatcher be able to dispatch a train and also queue its later station stops.

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

## Consequences

- REQ-FUNC-009 (dispatch to a block) is kept by letting a stop be a block of the line as
  well as a station; there is no separate block row.
- A change to a train's first stop is still subject to the CTC Office's safety checks:
  it is refused rather than leave a moving train an authority it cannot stop within.
- Not decided here: when the dwell at a queued stop is timed from, whether block stops
  get the 45 s dwell, whether a train's only stop may be removed (see the
  no-dispatcher-order-cancel proposals), and whether queues advance in Automatic mode.
