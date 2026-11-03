**Target:** truth/arbitration/no-authority-into-unusable-block.md
**Action:** replace
**Proposed by:** Claude on claude/ctc-harness-findings
**Provenance:** follows from Landis's 2026-10-30 decision that a block closes at once, with no pending state (proposal `20261030-1447-block-closure-closes-at-once.md`, review of F32 in `documents/central-harness-windows-gui-2026-10-28.md`); the rest of the entry is unchanged

---

# no-authority-into-unusable-block

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-05 (safety rules for the CTC Office, answered during the CTC bug review); failed blocks inferred by the CTC Office from occupancy rather than reported, asserted by Landis 2026-10-12; no closing state, asserted by Landis 2026-10-30
**Aliases:** no authority into closed block, no dispatch into failed block, authority safety
**Last updated:** 2026-10-30

## Definition

The CTC Office never gives a train authority into a block that is unusable: a block
closed for maintenance (see [block-closure](block-closure.md)), or a block the CTC
Office infers has failed (see
[train-tracking-from-occupancy](train-tracking-from-occupancy.md)). A dispatch, reroute
or set-authority into a closed block is refused, and nothing is sent to the Track
Controller. One into an inferred failure is not refused: authority stops short of the
block until it clears.

## Existing orders

When a block is closed, every order whose destination is that block is cancelled, and
the dispatcher is told. Orders into an inferred failure are kept: the UIs show it only
as an occupied block.

## Notes

- A train is also never dispatched to a block on another line than the one it is
  reported on: [authority-on-own-line](authority-on-own-line.md).

## Supersedes

- Closing blocks: previously a block waiting to close (a closure requested while a
  train was in it) was unusable too, and dispatches into it were refused. A block now
  closes at once, so there is no such block (Landis 2026-10-30).
