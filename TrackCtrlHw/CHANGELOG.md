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

## 2026-10-22 — Green-style Red integration routing

Kevin authorized reusing Braden's real Green PLC routing pattern in the
Red integration test programs. All seven switches now obey CTC overrides when
free, otherwise select a reverse approach or route around a closed normal
leg using AUTO/WANT logic. Occupied points hold their reported position;
switches 15, 32 and 43 also retain the listed-joint lock used by Green's
pattern. Point 9 never selects the yard automatically. Signals follow the
reported selected leg, remain red for mismatch/occupied points or a
blocked route, and show caution for reverse or maintenance.

Switch 52 selects REVERSE for a train on 66 and returns to NORMAL for an
outbound train on 51. No automatic train reversal or course data edit is
added. All test-copy declarations and Braden owner-review requirements
remain. The wayside split is unchanged: Red-1 1–24/73–76, Red-2
25–45/67–72, Red-3 46–66.

Kevin explicitly approved shared read-only neighbor closure inputs. The
same adjacency helper now defines both `OCC_n` and `CLOSED_n` input scope;
the scan image reads line-scoped full occupancy/closure sets. Switch 27
therefore receives `CLOSED_76` and can route and protect its reverse leg.
Foreign output ownership remains rejected. Missing occupancy still counts
as clear under the existing contract; Braden and Harry's review remains.

Routing checks cover normal/automatic/CTC selection, blocked approaches,
closed legs, occupied-point holds, selected-leg aspects and correspondence.
The existing Red speed/crossing/separation checks remain. A separate Green
snapshot test reuses the existing SW starter helper to record the
75/76 follower issue for Harry and Landis, without changing owner rules.

The round-trip regression reuses the existing seven-core `RedLoop` helper:
9 … 16 outbound, then an explicit return request through 17 … 66 → 52 … 9,
retired exactly once. It passes in 26.69 s; the helper checks emergency
brake and signal pickup every tick. No second launcher is introduced.
