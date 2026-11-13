# TrackCtrlHw — changes for review

Changes to the owners' module code during Phase 5 integration, for review.

---

## 2026-11-05 — CTC route requests at the Red passing sidings (Braden)

Branch `feature/TrackCtrl-HW-route-requests-pr56`, rebased onto the harness
integration branch. Landis's request of 2026-11-03; design and plan in `docs/`.

- `CtcInputs.route_requests`: the position each switch should take for the
  train routed over it. Validated like `switch_commands`; on the wire as
  `ctc.route_requests` entries `{line, switch_id, position}`; a sender without
  the field decodes as no requests.
- Every switch gets two PLC inputs, `REQSW_n` and `REQREV_n`. A request is not
  a command: the program decides, and the vital block does not read it.
- Red-2 (`red_wayside_2_integration_test.plc`): at 27, 32, 38 and 43 a request
  picks the leg, never a closed one; without one, the rule is unchanged. A
  train on the points and a maintenance command still win. `CAUTION_n` does
  not read requests.
- 2026-11-11: the same rule on Red-1 switch 15 and Red-3 switch 52. Switch 9
  (the yard) ignores requests and moves only on a maintenance command.
- The test UI sends route requests per switch.
- The harness carries `route_requests` to both Track Controllers (Harry's
  `746b2ce`).

---

## 2026-11-04 — Cheaper PLC scans (Landis)

`61e7796` (10x headroom on hybrid Windows laptops). The outputs are
unchanged. For Braden to review.

- `track_ctrl_hw/plc.py`: channel A turns each statement's tree into
  nested functions once per program (`_walker`, made on the first scan
  and cached) instead of walking the tree node by node on every scan;
  its AND and OR may now stop early, since reads have no side effects.
  Channel B runs its postfix code with the stack top replaced in place.
  Both channels still run on every scan and are compared. The cached
  functions are left out of pickles and copies (`__getstate__`), so a
  Pi's checkpoint makes its own on its first scan.
- `track_ctrl_hw/wayside.py`: the input-image names for the blocks,
  their neighbours and the switches, and the vital block's output
  names, are worked out once per territory, not on every scan.
- A wayside step on a P-core: 5.1 → 3.1 ms. Checked against the code before it: 205,982 live scans from the
TrackCtrlHw and TrackCtrlSW suites and 8,000 random programs gave
identical values and warnings; 1,500 captured Pi steps gave identical
outputs.

---

## 2026-10-28 — Red switch test reads the SW layout's new form (integration)

`tests/test_red_integration.py` only. Harry's `e5e51d4` folds the SW reader's
`Switch` class into a `(point, normal end, reverse end)` tuple per switch id, so
the test that checks every Red switch against all the readers now compares with
that tuple. Nothing it checks has changed, and no module code was touched. For
Braden to review.

---

## 2026-10-26 — Vital block and Braden's Red programs (Braden)

Branch `feature/TrackCtrl-HW-vital`, from `claude/quirky-fermi-sickg4`.

- New `track_ctrl_hw/vital.py`: a read-only vital block generated from each
  wayside's database and scanned after the user's program on both channels
  (Braden and Harry Tye, 2026-10-26: both variants append one). It only
  restricts: closures, separation over `next_blocks` (route-aware at points),
  moving switches, the speed limit, CTC switch commands and locking, one-aspect
  signals and crossings. A vital channel disagreement is a latched channel
  fault. Withdraws the 2026-10-16 "no vital layer" design (proposal D019).
- `wayside.py` drives the vital block's `OUT_` outputs; the snapshot carries
  `vital` (checksum, counts) and `overrides`; the PLC details window shows
  both and the vital source.
- The three Red PLCs are now Braden's (HW-1). File names are unchanged so the
  harness and its tests are untouched. Against Kevin's copies: `AUTO_9 := 0`
  replaces the undeclared `FALSE`; the points count only the leg the switch
  reports; speed passes
  through with authority and the vital block caps it; comments throughout.
- Tests: `tests/test_vital.py`; `NothingAboveTheProgram` becomes
  `VitalBlockOverAProgram`; a program can no longer ignore a CTC switch
  command.

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
Red integration test programs, superseding the old instruction to wait for real
Red programs. All seven switches now obey CTC overrides when
free, otherwise select a reverse approach or route around a closed normal
leg using AUTO/WANT logic. Occupied points hold their reported position;
switches 15, 32 and 43 also retain the listed-joint lock used by Green's
pattern. Point 9 never selects the yard automatically. Signals follow the
reported selected leg, remain red for mismatch/occupied points or a
blocked route, and show caution for reverse or maintenance.

Switch 52 selects REVERSE for a train on 66 and returns to NORMAL for an
outbound train on 51. No automatic train reversal or course data edit is
added. All test-copy declarations remain, and **Braden is the required
reviewer of this Red integration work as his module's owner**; his acceptance
remains pending. The wayside split is unchanged:
Red-1 1–24/73–76, Red-2 25–45/67–72, Red-3 46–66.

**Neighbor closure input extension and its review status.** The same
adjacency helper now defines both `OCC_n` and `CLOSED_n` input scope; the
scan image reads line-scoped full occupancy/closure sets. Switch 27 therefore
receives `CLOSED_76` and can route and protect its reverse leg. Foreign
output ownership remains rejected.

- **Approval:** Kevin explicitly authorized these shared read-only neighbor
  closure inputs before implementation, as confirmed on 2026-10-24.
- **Required review:** Asked on 2026-10-24 whether Braden accepted, Kevin answered
  "he didnt i did. ensure it is documented". Approval belongs to Kevin;
  Braden's acceptance remains pending. Braden's owner
  review of these test programs and the input extension is still required and
  remains open (see HW-1 in [module owner review](../documents/module-owner-review.md)).

Missing occupancy still counts as clear under the existing contract; Braden
and Harry's review of that completeness question also remains (INPUT-1).

Routing checks cover normal/automatic/CTC selection, blocked approaches,
closed legs, occupied-point holds, selected-leg aspects and correspondence.
The existing Red speed/crossing/separation checks remain. A separate Green
snapshot test reuses the existing SW starter helper to record the
75/76 follower issue for Harry and Landis, without changing owner rules.

The round-trip regression reuses the existing seven-core `RedLoop` helper:
9 … 16 outbound, then an explicit return request through 17 … 66 → 52 … 9,
retired exactly once. It passes in 26.69 s; the helper checks emergency
brake and signal pickup every tick. No second launcher is introduced.
