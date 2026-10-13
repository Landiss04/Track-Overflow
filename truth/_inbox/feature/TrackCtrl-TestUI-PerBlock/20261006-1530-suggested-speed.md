**Target:** truth/signals/suggested-speed.md
**Action:** create
**Proposed by:** GitHub Copilot on feature/TrackCtrl-TestUI-PerBlock
**Provenance:** asserted by Braden 2026-10-06 (Track Controller test UI review); conflicting value asserted by Landis 2026-10-02 (CTC architecture diagram, `ctc-architecture.html`), carried by the pending proposal `truth/_inbox/ctc-interfacing/20261002-1129-suggested-speed.md`

Note for the promoter: this supersedes the pending `ctc-interfacing` proposal of
the same target. That proposal says the Track Controller owner had not confirmed
the signal. He now has, and he disagrees with it on both type and keying, so the
entry below carries a `## Conflict` section instead of one value. **Do not
promote either proposal until the conflict is resolved.**

---

# suggested-speed

**Status:** current
**Owner:** CTC Office
**Provenance:** asserted by Landis 2026-10-02 (CTC architecture diagram,
`ctc-architecture.html`); conflicting value asserted by Braden 2026-10-06
(Track Controller test UI review)
**Aliases:** Suggested Speed, CTC suggested speed
**Last updated:** 2026-10-06

## Definition

The speed the CTC Office suggests, in m/s, sent to the Track Controller. What
the value is keyed by, and whether it is an integer, is in conflict — see below.

## Notes

- Distinct from the commanded speed in [track-signal](track-signal.md), which
  the Track Model sends to the Train Model.
- Both sides agree the unit is m/s.

## Conflict

**Resolution owner:** Kevin.

**Type and keying. Open.**

| Value | Provenance |
|-------|------------|
| `float`, one value per **train**, keyed by train ID | Landis 2026-10-02, choosing `conventions/units.md` over the CTC architecture diagram's `int` |
| `int`, one value per **block**, because the value reaches a train down the track circuit of the block it occupies | Braden 2026-10-06, Track Controller owner |

The two disagree on two separate things and may be resolved separately. The
keying question is the consequential one: it decides whether the Track
Controller receives a per-train table or a per-block table from the CTC Office.
