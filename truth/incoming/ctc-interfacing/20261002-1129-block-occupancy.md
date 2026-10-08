**Target:** truth/signals/block-occupancy.md
**Action:** create
**Proposed by:** Claude on ctc-interfacing
**Provenance:** asserted by Landis 2026-10-02 (CTC architecture diagram, `ctc-architecture.html`); types per `conventions/identifiers.md` and `conventions/units.md`, chosen by Landis 2026-10-02 over the diagram's int types

---

# block-occupancy

**Status:** current
**Owner:** Track Controller
**Provenance:** asserted by Landis 2026-10-02 (CTC architecture diagram, `ctc-architecture.html`); types per `conventions/identifiers.md` and `conventions/units.md`, chosen by Landis 2026-10-02 over the diagram's int types
**Aliases:** Block Occupancy, occupancy
**Last updated:** 2026-10-02

## Definition

Occupancy of each block as a boolean, keyed by block ID, sent from the Track Controller to the CTC Office.

## Notes

- Asserted from the CTC side. The Track Controller owner has not confirmed it.
- How the Track Controller learns occupancy from the Track Model is outside this entry.
