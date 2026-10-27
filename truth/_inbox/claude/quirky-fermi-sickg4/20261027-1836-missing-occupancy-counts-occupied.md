**Target:** truth/arbitration/missing-occupancy-counts-occupied.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** `documents/module-owner-review-braden.md` (branch `feature/TrackCtrl-HW-vital`, `a5bd465`), INPUT-1: decided by Braden Bosilovich 2026-10-26 for Track Controller HW; Harry Tye to agree for SW

---

# missing-occupancy-counts-occupied

**Status:** current
**Owner:** Track Controller
**Provenance:** Braden Bosilovich 2026-10-26 (module owner review INPUT-1), `documents/module-owner-review-braden.md` (branch `feature/TrackCtrl-HW-vital`, `a5bd465`); SW not yet agreed by Harry Tye
**Aliases:** missing occupancy, absent block, unreported block, fail-safe occupancy, INPUT-1
**Last updated:** 2026-10-27

## Definition

A block a wayside expects to hear about (one it owns, or a declared neighbour) that
the inputs do not report counts as occupied, as a failed track circuit does. The
wayside reports it to the CTC Office as occupied too.

## Notes

- This needs the inputs to carry every reported block, not only the occupied ones; as
  of 2026-10-27 the harness sends only occupied blocks, so absence still means clear.
- Freshness is the harness's barrier: a late or down module holds the clock.
- Applies to Track Controller HW. Harry Tye decides for SW.
