**Target:** truth/signals/maintenance-mode.md
**Action:** replace
**Proposed by:** Claude on ctc-interfacing
**Provenance:** asserted by Landis 2026-10-02 (CTC architecture diagram, `ctc-architecture.html`); withdrawn from the interface in favor of the closed-blocks list, asserted by Landis 2026-10-06

---

# maintenance-mode

**Status:** superseded
**Owner:** CTC Office
**Provenance:** asserted by Landis 2026-10-02 (CTC architecture diagram, `ctc-architecture.html`); withdrawn from the interface in favor of the closed-blocks list, asserted by Landis 2026-10-06
**Aliases:** Maintenance Mode, maintenance
**Last updated:** 2026-10-06

## Definition

No longer sent. The CTC Office does not tell the Track Controller whether the
dispatcher is in maintenance mode. It sends the list of blocks closed in maintenance
mode instead: [closed-blocks](closed-blocks.md).

## Notes

- Maintenance mode still exists inside the CTC Office as the dispatcher's mode for
  closing blocks and setting switches. It is not a signal.

## Supersedes

- Previously a boolean sent from the CTC Office to the Track Controller, true while the
  dispatcher had the system in maintenance mode (Landis 2026-10-02). Withdrawn because
  the Track Controller needs to know which blocks it may not override, not the mode
  (Landis 2026-10-06).
