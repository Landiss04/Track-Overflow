# TrackCtrlSW — changes for review

Changes to the owners' module code during Phase 5 integration, for review.

---










## 2026-11-13 — Count guard: GTC-04 crowded holds GTC-03's train on 75

Simplified from loop guard N. GTC-04 tells GTC-03, over the link between track
controllers, how many of its blocks (76..100) are occupied, as a whole number in
5 bits (`PEER_CNT_GTC04_0..4`, least significant first; `layout.CountGuard`,
`COUNT_GUARDS`). The starter compares it in Boolean code
(`FULL_GTC04 := count > 5`, `vital.greater_than_bits`) and holds block 75:
`AUTH_75 := NOT FULL_GTC04`. Loop guard N is removed: no switch forcing at 76/85,
and GTC-04 is no longer told 71..75. The top-loop guard (DEF) stays. Tests:
`test_boundary.CountGuardGtc04` (4, including every count from 0 to 25); the
N loop-guard tests and the test-ranking test that relied on GTC-04 seeing 75 are
removed.

---
## 2026-11-13 — Loop guard N watches 82..87 and needs a train on 99

`DRAIN_N := (82..87 occupied) AND OCC_99 AND (71..75 occupied)`: the approach is
held only while a train is in 82..87 and another waits on 99. `LoopGuard.required`
holds the blocks that must all be occupied. GTC-03 is now told 82..87 and 99. The
switches still move only while 76..85 is clear (`SET_N`). 2 tests added.

---
## 2026-11-13 — Test ranking restored: the wayside's own rule over a route request

Back in, for testing alongside the relaxed vital lock: while the starter sees a
train it sets a switch for, or holds it (`ACT_s`), its own rule outranks the CTC
Office's route request; with no train seen the request sets the switch. A leg's
approach block is read over the peer link (GTC-04 sees 75 for switch 76). Switch
order: points lock (vital), maintenance command, loop guard, own rule while
active, route request, own rule at rest.

---
## 2026-11-13 — Vital lock: a train held on a switch's listed block no longer locks it

The deadlock: a train stood on 76 (switch 76's listed block; its points are on 77)
with speed and authority 0, and the vital lock kept switch 76 reverse for good,
so the train it was held for could never be given its route. The vital lock now
reads, for a switch listed on a block other than its points,
`V_LOCK_s := OCC_point OR (OCC_s AND NOT (NOT AUTH_s OR CLOSED_s OR speed 0))`:
a train on the points always locks the switch; a train on the listed block locks
it only while it is commanded a speed (the program gives it authority, the block
is open, and the suggested speed is not 0). Applies to Green 12, 58, 62, 76 and
Red 15, 32, 43. Also: the test ranking above is undone, so the CTC Office's route
request again ranks above the starter's own rule. 2 tests in
`test_starter_switches.py`.

---
## 2026-11-13 — Test: the wayside's own switch rule outranks a route request

A test ranking, after a deadlock with switch 76 held reverse by a CTC route
request while the train on 75 needed normal. The starter writes
`ACT_s := HOLD_s OR WANT_N_s OR WANT_R_s` (it sees a train it sets the switch for,
or holds it) and, while `ACT_s`, its own rule wins over the CTC Office's route
request; with no train seen the request still sets the switch. A train coming off
a leg is also read from the block before the leg over the peer link where the
wayside is told it, so GTC-04 sees a train on 75 for switch 76. This reverses the
order in the route-request change list (request above the program's own rule).
Switch order: points lock (vital), maintenance command, loop guard, own rule while
active, route request, own rule at rest. 2 tests in `test_starter_switches.py`.

---
## 2026-11-13 — Loop guards over a peer link between waysides

A worst-case guard behind the CTC Office, so a loop cannot back up into the
two-way section it drains through. `layout.LOOP_GUARDS` (Green): loop 86..100
through section N, watched on 86..91, approach 71..75, switches 85 and 76 reverse;
loop 12..1 through 13..28, watched on 12..7, approach 145..150, switch 12 reverse
and 28 normal. The waysides involved are told the blocks they do not own
(`ControllerConfig.peer_blocks`, program input `PEER_OCC_n`). In the starter,
`DRAIN_g` is a train in the watched loop blocks AND one on the approach; then the
approach blocks' `AUTH_n` are 0. The switches are forced only while the two-way
section is also clear (`SET_g`: 76..85 for N, 13..28 for the top loop), so a
train already in it, or on 76 (which locks switch 76), finishes first; 76 is not
in N's approach for the same reason (71..75). Precedence for the switches: train
on the points (vital), maintenance command, the guard, route request, the
starter's own rule. 9 tests (`test_boundary.LoopGuards`).

---
## 2026-11-13 — S1: the starter no longer throws a switch behind an outbound train

From the Schedule v4 findings (S1): the starter generated `WANT_R_76 := NOT OCC_77
AND OCC_78`, reading any train on 78 as coming to 77, but 77..85 is run both ways
and outbound trains run 77 to 78. It threw switch 76 reverse behind them and
started the Green lockup. A facing term (a train on the fixed side, points clear)
is now written only where the layout runs the fixed block one way into the
points. Where it runs both ways the program cannot tell direction, and the CTC
Office's route request sets the switch (it ranks above the program's own rule).
This also drops the same guess at Green 12, 28 and 85 and at Red where it held.
`tests/test_starter_switches.py` updated (Switch76, Switch28, Maintenance).

---
## 2026-11-12 (last) — The peer occupancy link is removed

With the section N priority rules gone from the starter, nothing used the
wireless link between track controllers. It is removed: `PEER_OCC_n`,
`TrackController.peer_occupancy` and `set_peer_occupancy`, the module's pass of
occupancy between waysides, `ControllerConfig.peer_blocks` and `contested`, and
`layout.ContestedSection` / `CONTESTED_SECTIONS`, with their 1 test class. The
CHANGELOG entries above for them describe code that is no longer there.

---
## 2026-11-12 (later) — Section N priority taken out of the starter

The priority rules added earlier today fought the CTC Office: with G1 on 99 and G6
on 75 the CTC gave G1 speed 0 and G6 a speed, while the wayside held G6 and set
the switches for G1, so neither moved. Which train goes first through a
bidirectional section is the CTC Office's. The starter no longer holds 75/76 or
sets switches 76 and 85 by priority; it is back to its 2026-11-10 text. Kept: the
peer occupancy link (`PEER_OCC_n`, `ControllerConfig.peer_blocks`,
`layout.CONTESTED_SECTIONS`) as program inputs a program may read.

---
## 2026-11-12 — Priority for a train waiting at contested section N

Green section N (77..85) is single track used both ways. GTC-03 is now told the
occupancy of blocks 98, 99, 100 and 76, and GTC-04 of block 75 (`PEER_OCC_n`, a
program input; `ControllerConfig.peer_blocks`, `layout.CONTESTED_SECTIONS`), as if
over the wireless link between track controllers. In the starter: a train on 99 or
100 goes first; one on 98 goes unless one is on 76; otherwise one on 75/76 goes.
While the 98..100 side goes, `AUTH_75` and `AUTH_76` are 0 and switches 76 and 85
are set reverse; while 75/76 goes they are set normal. A maintenance command and a
route request still win over it, and a train on the points still locks a switch.
9 tests (`test_boundary.ContestedSectionN`).

---
## 2026-11-10 — Route requests (`route_requests`) reach the program

The CTC Office's `route_requests` (the switch position each routed train
needs) are now an input: `CtcInputs.route_requests`, in `inputs.ctc` on the wire
(same shape as `switch_commands`), and `REQSW_s` / `REQREV_s` in the program.
A request is not a command: it does not set maintenance mode, which stays keyed
on `switch_commands` only, and it is not cleared when maintenance ends. For a
switch the first rule that applies wins: a train on the points locks it (vital
code), then a maintenance command, then the request, then the program's own
rule. The starter generator does this and skips a request whose target leg is
closed. The wire decoder accepts `route_requests` when sent and treats it as
none when a sender leaves it out. The harness now carries the field
(`wayside_edges.py`, `hw_wayside_edges.py` in the HW shape, `edges.py` `_NO_CTC`
and the typed `ctc_edges.py`), as its own list, never merged into
`switch_commands` and not filtered against them. Tests added:
`test_boundary.RouteRequests` (7), two in `test_harness_edges.py` and one in
`test_ctc_edge.py`.

---
## 2026-11-04 — PLC expressions compile once (Landis)

`61e7796` (10x headroom on hybrid Windows laptops). The outputs and
warnings are unchanged. For Harry to review.

- `track_ctrl/plc.py`: each expression compiles once into an evaluator
  (`compile()` on `Literal`, `Reference`, `Not` and `BinaryOp`;
  `Program._evaluators`, made on the first scan and cached), in place of
  the per-scan `evaluate()` walk and `_Scope`. An undefined read still
  warns once per scan with the same text, and both sides of every
  operator are still evaluated, so the warnings do not depend on the
  inputs. The program is still pure.
- Checked against the code before it: 205,982 live scans from the
TrackCtrlHw and TrackCtrlSW suites and 8,000 random programs gave
identical values and warnings; 1,500 captured Pi steps gave identical
outputs.

---

## 2026-11-03 — The starter's separation rule is direction-aware

`AUTH_n := NOT (OCC_n AND <next blocks of n>)`, from the layout's `next_blocks`.
Before, a train was held when either neighbour was occupied, so trains in
adjacent blocks (Green 62, 63, 64, found in the stress test) held each other
and none could move. Now only the train behind is held. In a bidirectional
section (Green 13..28, 77..85) the direction is unknown to the program and each
block still holds for the other. The CTC-command wrapper in the starter's switch
rule is also now parenthesised. `tests/test_boundary.py` and `tests/test_world.py`
updated; a convoy test was added.

---
## 2026-11-03 — A wayside is ready when its layout is present and a program is committed

`ready` is now per wayside: track layout present AND committed program. A
ready wayside runs and transmits whatever the others are doing; before, one
unprogrammed wayside held every wayside on its line. A wayside with no program
still transmits nothing but its armed crossings. The module-level `ready` (the
header, `not_ready_reasons`) is still every wayside's, and the CTC Office still
sees each wayside's own report. `test_one_missing_program_stalls_every_wayside`
became `test_a_wayside_with_a_program_runs_without_waiting_for_the_rest`.

---

## 2026-10-30 — Harry's `829c842` taken: CTC switch command, points lock, window

Cherry-picked from `Track-Ctrl-SW` (`829c842`), TrackCtrlSW files only.
The commit's shared `ui/` changes only cleared merge-conflict markers on
Harry's branch. The result is identical to this branch's `ui/`, so they
were left out.

- **The program obeys the CTC Office's switch command.** The CTC's command
  is now a program input, `CTCSW_s` and `CTCREV_s` (Braden's HW names).
  The starter obeys it before anything else. The vital code no longer
  applies it, and only the programmer's hand-set position overrides the
  program.
- **The switch lock covers the points block.** The vital code holds a
  switch while a train is on its listed block or on its points block
  (`V_LOCK_s`), as the HW vital code does. This replaces the local branch
  `claude/sw-points-block-lock`, which was waiting for Harry's yes.
- **The window scales.** It is now the shared `ScaledWindow`, with the
  16:10 aspect lock installed in `main.py` and `module_process.py`. It no
  longer opens at a fixed 1440 × 926 (GUI report F1/F38).
- **`loadStarterPrograms` slot** on the window's state. No control in the
  window calls it yet (GUI report F8).
- **`STARTER_LOG.md`.** Harry keeps the current starter, and the log
  records its fingerprint per wayside. All 11 fingerprints match on this
  branch.
- Tests: SW suite 222 passed. The same 3 `test_hw_language` failures as
  before remain (HW programs use `SPD_n_b` and `FAIL_n`, which are not SW
  inputs). Harry's own tree fails 9.

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
