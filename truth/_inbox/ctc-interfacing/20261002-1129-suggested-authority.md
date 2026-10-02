**Target:** truth/signals/suggested-authority.md
**Action:** create
**Proposed by:** Claude on ctc-interfacing
**Provenance:** asserted by Landis 2026-10-02 (CTC architecture diagram, `ctc-architecture.html`); types per `conventions/identifiers.md` and `conventions/units.md`, chosen by Landis 2026-10-02 over the diagram's int types

---

# suggested-authority

**Status:** current
**Owner:** CTC Office
**Provenance:** asserted by Landis 2026-10-02 (CTC architecture diagram, `ctc-architecture.html`); types per `conventions/identifiers.md` and `conventions/units.md`, chosen by Landis 2026-10-02 over the diagram's int types
**Aliases:** Authority (CTC), CTC authority, suggested authority
**Last updated:** 2026-10-02

## Definition

The block ID up to which the CTC Office suggests one train may travel, sent to the Track Controller. One value per train, keyed by train ID.

## Notes

- Authority is a block ID string per `conventions/identifiers.md`. The diagram typed it as `int [2]`; what the second element meant is open.
- Distinct from the authority in [track-signal](track-signal.md), which the Track Model sends to the Train Model.
- The Track Controller owner has not confirmed it.
