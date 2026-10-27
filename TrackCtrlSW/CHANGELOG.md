# TrackCtrlSW — changes for review

Changes to the owners' module code during Phase 5 integration, for review.

---

## 2026-10-27 — Harry's development version taken (review SW-1)

The integration branch now carries Harry Tye's `development` TrackCtrlSW
(`f796f49`: generated vital PLC code attached to every program, HW's program
language, no auto-loaded starters), as Braden asked under SW-1. Merged against
base `f590f41`. Kept from the integration branch: `track_ctrl/module_process.py`
and its tests (the harness adapter), and in `track_ctrl/state.py` the `lines`
argument and `loadStarterPrograms` (the harness has no programmer; the UI never
calls them). `tests/test_starter_switches.py` is removed: it tested the
integration branch's starter switch rules, which Harry's generator replaces.

One change to Harry's code, approved by him: `default_program_source` now holds
only a block with a train in it, `AUTH_n := NOT (OCC_n AND (OCC_n-1 OR OCC_n+1))`.
Before, `AUTH_n := NOT (OCC_n-1 OR OCC_n+1)` held the block a train was about to
enter (its neighbour is that train's block), so every train got one tick of
speed 0 and authority 0 on entering a block, which the Train Controller latches
as a signal pickup failure. Root cause traced 2026-10-27.

Open for Harry: a not-ready wayside transmits nothing, so the Track Model keeps
its crossings' last state; the harness test that expects them held down is
marked expected-failure. `tests/test_hw_language.py` fails 3 tests against
Braden's 2026-10-26 Red programs (HW now declares `CTCSW_s`/`CTCREV_s`), as it
already did on `development`.

## 2026-10-22 — Red yard and integration inputs

Correction commit: `5d51051` (course data restoration and reader agreement).

`track_ctrl/layout.py` gained the Red-9 interpretation in `f27ba4e`
(Phase 5 K2, Kevin Schillinger 2026-10-21). This changes Harry Tye's layout
reader so the physical yard connection is at block 9 in section C.

The 2026-10-22 correction preserves the course file exactly and interprets
the stale block-75 yard adjacency in the reader. The current assumption is
point 9, NORMAL to 8, REVERSE to yard, fixed side 10 and light on 10, so a
train leaving the yard proceeds 9 → 10. The Track Model owner and Braden
must confirm these legs; Kevin's statement establishes the yard location
and immutable data, not those detailed switch semantics.

The SW vital layer remains a separate follow-up requested by Kevin; this
entry records the reader change and does not remove that layer.
