# TrackCtrlHw — changes for review

Changes to the owners' module code during Phase 5 integration, for review.

---

## 2026-10-22 — Red yard and integration inputs

Correction commit: `5d51051` (course data restoration and reader agreement).

`f27ba4e` (Phase 5 K2/K4, Kevin Schillinger 2026-10-21) changed Braden's
`track_ctrl_hw/territory.py` to interpret the Red yard at block 9 and added
cross-wayside neighbour occupancy inputs in `track_ctrl_hw/wayside.py`.
A PLC can read `OCC_n` for declared adjacent blocks outside its own
wayside; the harness supplies the full occupancy set.

**Safety note for Braden and Harry Tye:** an occupied block missing from
the inputs counts as clear. A partial occupancy set can therefore let a
PLC clear an unsafe movement. Owners must review the input completeness
contract and the PLC programs; this changelog item makes no core change.

The 2026-10-22 yard correction preserves the course source and its
integration territory copy, interpreting the stale block-75 yard adjacency
at block 9 in the reader. Assumption for Braden and the Track Model owner:
point 9, NORMAL to 8, REVERSE to yard, fixed side 10 and light on 10.
This lets a yard release proceed 9 → 10 and requires owner confirmation.

Real Red PLC programs remain Braden's work. The test PLC programs do not
route Red switches: return through 66 → 52 needs REVERSE at 52, while the
outgoing 52 → 53 route needs NORMAL. No switch-routing or automatic
reversal workaround is added.
