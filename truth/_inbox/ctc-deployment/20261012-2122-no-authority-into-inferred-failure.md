**Target:** truth/arbitration/no-authority-into-unusable-block.md
**Action:** replace
**Proposed by:** Claude on ctc-deployment
**Provenance:** asserted by Landis 2026-10-05 (safety rules for the CTC Office, answered during the CTC bug review); failed blocks inferred by the CTC Office from occupancy rather than reported, asserted by Landis 2026-10-12

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
or set-authority into such a block is refused, and nothing is sent to the Track
Controller.

## Existing orders

When a block is closed or a closure is requested on it, every order whose destination
is that block is cancelled, and the dispatcher is told. What happens to orders into an
inferred failure is open: see the conflict in
[train-tracking-from-occupancy](train-tracking-from-occupancy.md).

## Notes

- A train is also never dispatched to a block on another line than the one it is
  reported on: [authority-on-own-line](authority-on-own-line.md).

## Supersedes

- Failed blocks: previously reported by the Track Controller with their kind (broken
  rail, track circuit or power). Now inferred by the CTC Office from occupancy, because
  a failure is reported only as an occupied block (Landis 2026-10-12).
