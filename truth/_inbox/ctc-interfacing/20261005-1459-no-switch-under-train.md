**Target:** truth/arbitration/no-switch-under-train.md
**Action:** create
**Proposed by:** Claude on ctc-interfacing
**Provenance:** asserted by Landis 2026-10-05 (safety rules for the CTC Office, answered during the CTC bug review)

---

# no-switch-under-train

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-05 (safety rules for the CTC Office, answered during the CTC bug review)
**Aliases:** switch interlock, no switch move under a train
**Last updated:** 2026-10-05

## Definition

The CTC Office never commands a switch while the block the switch is listed on is
occupied, that is while a train is reported on that block or the block is reported
occupied. Such a switch command is refused.

## Notes

- A switch is identified by its line and the block it is listed on in the track layout
  file (`conventions/identifiers.md`).
- Switch commands are also maintenance-mode only ([switch-command](../signals/switch-command.md)).
