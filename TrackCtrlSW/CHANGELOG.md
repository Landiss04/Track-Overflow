# TrackCtrlSW — changes for review

Changes to the owners' module code during Phase 5 integration, for review.

---

## 2026-10-28 — vital code clamps the speed; crossings default to armed

`track_ctrl/vital.py`, `track_ctrl/controller.py` and the tests.

- **Posted-limit clamp in the vital code.** A suggestion over a block's posted
  limit used to pass down the circuit unchanged (the CTC Office was to keep it
  under). The vital program now clamps it. `build_scan_inputs` gives the vital
  code the suggested speed as bits no user program can declare (`SUGSPD_n_b`,
  whole m/s, least significant first, saturated to the width the fastest posted
  limit needs); the vital code compares it with the block's limit in Boolean
  code (`V_GT_n`) and writes `OUT_SPD_n_b`; `encode_outputs` reads the speed from
  those bits, then halves it under yellow as before. RUN shows the override
  `speed_clamped`. A user program still never sees or sets a speed.
- **Crossings default to armed.** `TrackController.idle()` (no program, or the
  line not ready) now commands every crossing active, lights on and gates down.
  Switches, signals and track circuits are still absent.
- `test_world.py`: the clamp is checked against `min(speed, limit)` for every
  block and speed; the crossing default is checked; two tests that asserted the
  old behaviour were rewritten.

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

Superseded on 2026-10-28 by Harry's `e5e51d4`, cherry-picked from
`Track-Ctrl-SW`: his starter switch rules and `tests/test_starter_switches.py`
are back, with HW's input names, and a not-ready wayside now arms its
crossings. The separation rule above is his too. On this branch the layouts stay
in `TrackModel/`, as on `development`: `default_layout_dir()` points there, not at
`Track_layout/`, which came from `Train_Ctrl_integration`.

---

## 2026-10-23 — data-only classes folded into the classes that own them

`track_ctrl/controller.py`, `vital.py`, `plc.py`, `layout.py`, `module.py`,
`state.py`, `stimulus.py`, `module_process.py` and the tests. No behaviour
changes; the boundary types in `interface.py` are untouched.

A class that only held fields (or fields and a naming property) is now an
attribute set on the class that uses it:

- `ControllerInputs`, `ControllerOutputs`, `TrackCircuit`, `ScanReport` and
  the wayside's own `Suggestion` are attributes of `TrackController`
  (`occupancy`, `suggestions`, `track_circuits`, `switch_commands`,
  `crossing_commands`, `aspects`, `overrides`, `warnings`, `log`, ...). A
  suggestion and a track circuit are `(speed_mps, authority_blocks)` tuples.
  RUN's sandbox is `TrackController.trial(program)`, which returns a copy of
  the wayside scanned once, in place of `run_program(program, inputs.copy())`.
- `Iteration` is folded into `Program`, which now carries `number`,
  `file_name` and `committed_at`; the history is a list of `Program`s.
- `Assignment` and `ScanResult` are folded into `Program` (`scan` returns
  `(values, warnings)`).
- `_Wayside` is folded into `TrackController` (`line`, `key()`).
- `Switch`, `WaysideSignal` and `Crossing` are folded into `ControllerConfig`,
  which holds ids (a switch maps to `(point, normal end, reverse end)`) and
  names the PLC outputs (`switch_output`, `aspect_outputs`, `crossing_output`,
  `crossing_approach`). Each id is the block the device stands on.
- `ParsedLayout` is folded into `LineLayout`: a layout file reads into an
  undivided line, and `LineLayout.divide()` replaces `build_line()`.

Kept, because they do more than hold data: `Diagnostic` and `VitalOverride`
(each formats itself for the terminal), `Block` (its label and whole-m/s
limit), `Program`, `LineLayout`, `ControllerConfig`, and every type in
`interface.py` (the contract with the harness and the HW variant).

`common/harness/tests/test_harness_edges.py` read `ParsedLayout.switches`; it
now reads the folded form.

---

## 2026-10-22 — PLC input names back to HW's

`track_ctrl/controller.py`, `track_ctrl/layout.py`, `tests/test_starter_switches.py`.

The Q7 starter-switch merge (`629fe07`) replaced the HW-matching inputs
(`FAIL_n`, `SWREV_s`, `MAINT`) with `SUG_n`, `FAULT_s`, `MOVING_s` and `REV_s`,
which HW's programs do not have (REQ-INTF-009), and left `build_scan_inputs`
reading an `inputs.switch_moving` that `ControllerInputs` does not have, so no
scan could run. Restored:

- `input_names` and `build_scan_inputs` are HW's again, with the hand-set bits
  `HAND_s` and `HANDREV_s` that the merge had dropped for the vital code.
- The starter reads `SWREV_s` where it read `REV_s`, and no longer reads a
  suggestion: facing is `NOT OCC_p AND OCC_f`, and a trailing leg also counts
  the block before it. It cannot tell which way a train on a leg is heading, so
  three direction tests in `test_starter_switches.py` were changed to say so.
- `default_layout_dir()` points at `Track_layout/`, where the layouts now live.

HW's own language has since changed (`SPD_n_b`, `CMD_n_b`, `CTCSW_s`, no
`FAIL_n` or `MAINT`), so three tests that compare the two variants still fail
until the owners agree one language.

---

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
