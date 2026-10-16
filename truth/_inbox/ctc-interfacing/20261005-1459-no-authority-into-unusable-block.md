**Target:** truth/arbitration/no-authority-into-unusable-block.md
**Action:** create
**Proposed by:** Claude on ctc-interfacing
**Provenance:** asserted by Landis 2026-10-05 (safety rules for the CTC Office, answered during the CTC bug review)

---

# no-authority-into-unusable-block

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-05 (safety rules for the CTC Office, answered during the CTC bug review)
**Aliases:** no authority into closed block, no dispatch into failed block, authority safety
**Last updated:** 2026-10-05

## Definition

The CTC Office never gives a train authority into a block that is unusable: a block
closed for maintenance, a block waiting to close (see
[block-closure](block-closure.md)), or a block the Track Controller reports as failed
(broken rail, track circuit or power). A dispatch, reroute or set-authority into such a
block is refused, and nothing is sent to the Track Controller.

## Existing orders

When a block is closed, a closure is requested on it, or a failure is reported on it,
every order whose destination is that block is cancelled, and the dispatcher is told.

## Notes

- A train is also never dispatched to a block on another line than the one it is
  reported on: [authority-on-own-line](authority-on-own-line.md).
