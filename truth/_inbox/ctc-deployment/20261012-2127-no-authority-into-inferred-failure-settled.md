**Target:** truth/arbitration/no-authority-into-unusable-block.md
**Action:** replace
**Proposed by:** Claude on ctc-deployment
**Provenance:** replaces pending proposal `20261012-2122-no-authority-into-inferred-failure.md` (orders into inferred failures settled); asserted by Landis 2026-10-05 (safety rules for the CTC Office, answered during the CTC bug review); failed blocks inferred by the CTC Office from occupancy rather than reported, asserted by Landis 2026-10-12

---

# no-authority-into-unusable-block

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-05 (safety rules for the CTC Office, answered during the CTC bug review); failed blocks inferred by the CTC Office from occupancy rather than reported, asserted by Landis 2026-10-12
**Aliases:** no authority into closed block, no dispatch into failed block, authority safety
**Last updated:** 2026-10-12

## Definition

The CTC Office never gives a train authority into a block that is unusable: a block
closed for maintenance, a block waiting to close (see
[block-closure](block-closure.md)), or a block the CTC Office infers has failed (see
[train-tracking-from-occupancy](train-tracking-from-occupancy.md)). A dispatch, reroute
or set-authority into a closed or closing block is refused, and nothing is sent to the
Track Controller. One into an inferred failure is not refused: authority stops short
of the block until it clears.

## Existing orders

When a block is closed or a closure is requested on it, every order whose destination
is that block is cancelled, and the dispatcher is told. Orders into an inferred failure
are kept: the UIs show it only as an occupied block.

## Notes

- A train is also never dispatched to a block on another line than the one it is
  reported on: [authority-on-own-line](authority-on-own-line.md).

## Supersedes

- Failed blocks: previously reported by the Track Controller with their kind (broken
  rail, track circuit or power), refused as destinations and cancelling orders into
  them. Now inferred by the CTC Office from occupancy, because a failure is reported
  only as an occupied block; such orders are kept (Landis 2026-10-12).
