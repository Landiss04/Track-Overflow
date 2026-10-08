**Target:** truth/signals/suggested-authority.md
**Action:** create
**Proposed by:** GitHub Copilot on feature/TrackCtrl-TestUI-PerBlock
**Provenance:** asserted by Braden 2026-10-06 (Track Controller test UI review); conflicting value asserted by Landis 2026-10-02 (CTC architecture diagram, `ctc-architecture.html`), carried by the pending proposal `truth/_inbox/ctc-interfacing/20261002-1129-suggested-authority.md`

Note for the promoter: this supersedes the pending `ctc-interfacing` proposal of
the same target. The conflict below also reaches
`truth/conventions/identifiers.md` and `truth/conventions/units.md`, both of
which record authority as a block ID on Kevin's 2026-09-30 resolution. **Do not
promote either proposal until the conflict is resolved**, and expect the
resolution to require an edit to those two conventions if Braden's value wins.

---

# suggested-authority

**Status:** current
**Owner:** CTC Office
**Provenance:** asserted by Landis 2026-10-02 (CTC architecture diagram,
`ctc-architecture.html`); conflicting value asserted by Braden 2026-10-06
(Track Controller test UI review)
**Aliases:** Authority (CTC), CTC authority, suggested authority
**Last updated:** 2026-10-06

## Definition

The authority the CTC Office grants a train, sent to the Track Controller. What
the value *is* — a destination block ID or a count of blocks — is in conflict;
see below.

## Notes

- Distinct from the authority in [track-signal](track-signal.md), which the
  Track Model sends to the Train Model.
- Both sides agree there is exactly one authority value, not two. The CTC
  architecture diagram's `int [2]` does not stand.

## Conflict

**Resolution owner:** Kevin.

**What authority is. Open.**

| Value | Provenance |
|-------|------------|
| A **block ID string**, naming the destination block up to which the train may travel. One value per train, keyed by train ID | Kevin 2026-09-30, recorded in `conventions/units.md` `## Resolved` and `conventions/identifiers.md`; adopted by Landis 2026-10-02 |
| An **integer count of the blocks remaining** in the train's authority. One value per block, because the value reaches a train down the track circuit of the block it occupies | Braden 2026-10-06, Track Controller owner |

This is not a presentation difference. A block ID and a remaining-block count
are different quantities, and `conventions/identifiers.md` currently forbids the
second by stating that authority is an identifier and never arithmetic. If
Braden's value is adopted, `conventions/identifiers.md` and
`conventions/units.md` both have to be edited, and Kevin's 2026-09-30
resolution recorded as superseded.
