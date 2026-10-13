**Target:** truth/signals/closed-blocks.md
**Action:** create
**Proposed by:** Claude on ctc-interfacing
**Provenance:** asserted by Landis 2026-10-02 (CTC architecture diagram, `ctc-architecture.html`); sent as the full list, which the Track Controller queries and may not override, a closing block listed as soon as its closure is requested, asserted by Landis 2026-10-06. Supersedes the pending proposal `20261002-1129-closed-blocks.md`

---

# closed-blocks

**Status:** current
**Owner:** CTC Office
**Provenance:** asserted by Landis 2026-10-02 (CTC architecture diagram, `ctc-architecture.html`); sent as the full list, which the Track Controller queries and may not override, a closing block listed as soon as its closure is requested, asserted by Landis 2026-10-06
**Aliases:** Block Open / Close, block closure, closed blocks, maintenance closures, maintenance block list
**Last updated:** 2026-10-06

## Definition

The list of blocks the dispatcher has closed in maintenance mode, sent from the CTC
Office to the Track Controller every step as the full set. Each block is identified by
line and block ID per `conventions/identifiers.md`. A block that is not listed is open.

- A block goes on the list as soon as its closure is requested, including a block
  that still has a train in it.
- A block comes off the list only when the dispatcher reopens it. Leaving maintenance
  mode does not remove it.

The Track Controller queries the list and may not override a listed block. See
[maintenance-closure-lock](../arbitration/maintenance-closure-lock.md).

## Notes

- Replaces the [maintenance-mode](maintenance-mode.md) boolean as what the CTC Office
  tells the Track Controller about maintenance.
- Switch positions set in maintenance mode are not on this list; they go out as switch
  commands.
- The Track Controller owner has not confirmed it.

## Supersedes

- Form: the diagram's per-block open or close command (`cmd`) was left open against
  the full set (Landis 2026-10-02); now the full set, sent every step (Landis
  2026-10-06).
