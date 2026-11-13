# Plan (rev 2): signal aspects to the CTC, and HW/SW on either line

Revised 2026-11-12 after four Sonnet prototypes in scratch copies. Nothing in the repo
has changed. Prototype patches (reference, not for applying blind):

| Prototype | Patch | Size | Result |
| --- | --- | --- | --- |
| Aspects to CTC | `scratchpad/p1-aspects.patch` | 763 lines, 21 files | works; CTC suite 350 → 353 OK |
| Whole-line swap | `scratchpad/p2-swap.patch` | 622 lines, 10 files | works; default and swapped headless runs clean |
| Green HW data | `scratchpad/p3-green-data.patch` | 4053 lines (≈3400 generated), 8 files | works in-process; 13 new tests OK |
| Per-train mix | `scratchpad/p4-mix.patch` (on top of p2) | 722 lines, 17 files | works; one SW + one HW Green train ran end to end |

`scratchpad` = `/tmp/claude-1000/-home-kevin-Documents-Trains-Track-Overflow/29bb3311-c381-4b2e-b754-1aa48e1f2de6/scratchpad` (on Kevin's machine; the patches are not in the repo)

## Context

- **R1.** The CTC Office receives the wayside signal aspects (RED / YELLOW / GREEN /
  SUPER_GREEN) and shows them as markers on the track map.
- **R2.** The HW and SW variants of the Track Controller and the Train Controller can
  run on either line. D021 fixes HW→Red, SW→Green today. Whole-line swap is planned as
  the core; per-train mix is planned as an optional add-on.

## What the prototypes changed in this plan

1. **Baseline is not green.** Before any change: harness suite has 7 import errors
   (test modules import `pytest`, not installed) and 1 failure
   (`test_the_ctc_office_takes_the_track_models_sales`); TrackCtrlSW has 3 failures in
   `test_hw_language`; TrackCtrlHw has 1 `pytest` import error. `PyInstaller` is also
   missing from `TrainModel/.venv` (toolchain minimum 6.22.2). → new Phase 0a.
2. **Marker letters are unreadable at the default zoom.** The map renders at ≈0.75×;
   at "Fit" the R/Y/G/SG letters cannot be read, so colour is the only cue, which the
   style guide forbids. → Phase 1c now requires a shape cue.
3. **The Green HW data should be generated, not hand-written.** One script reproduces
   the committed Red databases byte-for-byte and the Red PLC programs
   statement-for-statement, then emits Green. → Phase 3 ships the generator.
4. **Green needs PLC logic Red has no model for** (switch 76, yard switch 62, the 13–28
   two-way section). → owner review is a gate, not a footnote.
5. **Per-train mix does not need the CTC.** Automatic dispatch omits the field and the
   harness defaults it. A harness flag covers it in ≈20 lines; the CTC field + toggle
   costs ≈65 more and changes the wire format. → Phase 4 mechanism changed.
6. Smaller corrections are folded into the phases below and marked **(rev)**.

## Phase 0a — baseline (rev, new)

- Install `pytest` and `PyInstaller` into the project venv (user's call; agents did not
  install anything).
- Re-run all suites and record the baseline. The eight harness modules and one
  TrackCtrlHw module that need `pytest` have never run against these prototypes — they
  include `test_harness_hw_system`, `test_review_scenarios` and `test_harness_red_loop`,
  which pin Red→HW.
- Decide what to do about the pre-existing failures (fix first, or carry as known).

## Phase 0b — truth proposals (before code)

To `truth/_inbox/integrate/harness-into-development/`, one file each, committed and
pushed in the same session. Provenance "asserted by Kevin Schillinger 2026-11-12".

1. `decisions/D021-…` — replacement: variant per line selected at launch, default
   HW→Red; `## Supersedes` names the fixed assignment.
2. `decisions/D027-…` — replacement dropping "runs every Red Line train".
3. `signals/signal-aspect-report.md` — new: `{line, signal_id, aspect}`, signal ID = its
   switch ID, Track Controller → CTC; value is the lamp the Track Model reports lit; a
   signal with no read-back is not reported; a repeated identical report is accepted, a
   contradictory one rejected **(rev)**.
4. `decisions/D025-…` — replacement adding signal aspects to the CTC test UI's inputs.
5. `ui/style-guide.md` — aspect colour tokens and the marker rule **(rev: moved up from
   "deferred"; the prototype needed it)**. Five proposals → present for review before
   continuing, per AGENTS.md.

## Phase 1 — signal aspects reach the CTC (R1)

**1a. Harness edge** — `common/harness/wayside_edges.py`: `signals` list in
`track_controller_to_ctc` (aspect upper-cased), `"signals": []` in `merge_ctc_inputs`,
docstring fix. `hw_wayside_edges.py` unchanged (confirmed).
- **(rev)** The pass-through test belongs in `common/harness/tests/test_harness_edges.py`.
  `TrackCtrlSW/tests/test_ctc_edge.py` tests the opposite direction; an end-to-end case
  there is optional and must feed `TrackModelInputs(signal_aspects=…)`, because the
  controller reports an aspect only for read-back blocks (`module.py:478`).
- **(rev)** `test_hw_wayside_edges.py` is bare-`assert` functions; only pytest collects it.

**1b. CTC data path** — as before (`interface.py`, `wire.py`, `model.py`, `ctc_host.py`),
copying crossings. **(rev)** validation uses `_no_conflict`, not "no duplicates".
**(rev)** more tests pin the input shape than the plan listed: `tests/occupancy.py`
(`reports()` helper), `test_ctc_boundary.py:332,391`, `test_socket_link.py:195`,
`test_module_process.py`.

**1c. Display and test UI**
- `track_map.py` adds signal positions; switches are not drawn today, so the marker sits
  at the switch block's midpoint, offset to the side away from the block number **(rev)**.
- `Main.qml` → `TrackViewPanel.qml` → `TrackMap.qml`: one marker per signal, plus a
  legend entry. An unreported signal draws hollow with "?" **(rev)**.
- **(rev) Readability gate:** the aspect must be distinguishable without colour at the
  default "Fit" zoom. Use a distinct shape per aspect (or a marker that does not scale
  below the 12 px label floor); letters alone failed. Check contrast of letter on fill
  and overlap in dense areas (Red 9 by the yard).
- **(rev)** `aspect_yellow` / `aspect_super_green` go in the shared `ui/theme.py`;
  `TrackCtrlSW/track_ctrl/theme.py` then reads them instead of holding its own copy.
- `test_harness.py`: `signal_states` row reusing the `"switch"` field kind.
- **(rev)** update the input lists in `ctc_ui/README.md:265`, `ctc/interface.py:12`,
  `ctc/module_process.py:17`.

## Phase 2 — whole-line swap (R2)

One harness flag `--hw-line {Red,Green}`, default `Red`. Confirmed sufficient; nothing
pushed toward per-pair flags.

- `common/harness/edges.py`: tables built in `SystemEdges.__init__(hw_line=…)`.
  **(rev)** nothing outside the file imports the old constants — remove them rather than
  keep exported defaults.
- `common/harness/app.py`: flag, `hw_line` into `SystemEdges`, `--line` to the four
  controller modules.
- **(rev)** `common/harness/measure.py:194-201` hard-codes the assignment; give it the
  same flag (needed for the Pi-load measurement below).
- `TrackCtrlSW/track_ctrl/module_process.py`: `--line`, `line_layout(line)`; keep
  `green_line()` as a wrapper (two tests import it).
- `common/hw_link/host.py`: `--line`; starters matched by
  `{line}_*_integration_test.json` **(rev: not `{line}_*`, which also catches the
  partial Green fixtures)**; refuse to start when the set does not cover the line.
  **(rev)** report that refusal through the harness event log, not only stderr — the
  prototype's harness showed just `STARTUP_TIMEOUT`.
- Train controller console (`train_ctrl/app.py`, `backend.py`, `module_process.py`): no
  line filter under the harness; `--line` titles the window.
- Tests: new swapped-assignment test class; `Train-Ctrl_HW` self-check is
  `python main.py --check` **(rev)**. Stale "SW = Green" wording in `wayside_edges.py`
  docstrings, `ConsoleWindow.qml:22`, READMEs, `REQUIREMENTS.md` M13.

## Phase 3 — Green data for the Track Controller HW (rev)

- Ship the generator (`TrackCtrlHw/tools/gen_waysides.py`) and its output:
  `green_wayside_{1,2,3}_integration_test.json/.plc`, marked `integration_test_only`.
  Cut: Green-1 = 1–50 + 145–150, Green-2 = 51–101, Green-3 = 102–144, chosen so each
  switch's point and legs sit in one wayside. No per-wayside limit exists in the code.
- `territory.py` needs no change (its Red special cases are gated on the line).
- Tests: `tests/test_integration_sets.py` — coverage for both lines, every PLC loads
  clean, Green behaviour scenarios; plus a test that the generator reproduces Red.
- **Owner review gate (Track Controller HW owner) before HW-on-Green is used in a demo:**
  1. Switch 76: reverse leg leads away from the points; prototype makes it request-only
     and refuses while 76 is occupied.
  2. Yard switch 62: maintenance command only, like Red's 9.
  3. Blocks 13–28 two-way section: no wayside-level head-on protection; SW's loop/count
     guards are not ported (the cut keeps them expressible in one wayside).
  4. Inherited from Red: a train facing a moving switch keeps authority.
  5. Signal look-ahead for 62, 76 and 85.

## Phase 4 — per-train mix (optional; build only on Kevin's go) (rev)

Train controllers only. Additive to Phase 2; forces no rework of it.

- `common/harness/roster.py`: `TrainEntry.controller`, default = the line's variant.
- `common/harness/edges.py`: route on `entry.controller`; take each train's commands
  only from its assigned controller.
- **(rev) Selection by harness flag:** `--hw-trains G2,G4` (IDs listed go to HW,
  the rest follow `--hw-line`). ≈20 lines, no CTC, UI or wire change. *This variant was
  estimated, not prototyped;* the roster and edge parts were.
- Console title names the lines its trains are actually on.
- `TRAIN_ADDED` log line names the controller **(rev: always, and update the
  exact-match assertions — the prototype's "only when non-default" is ambiguous under
  `--hw-line Green`)**.
- Test: two Green trains, one per variant; stale reports from the wrong controller are
  ignored; ID reuse on the other variant.

## Open items (not decided here)

- **Red guards under SW** — `TrackCtrlSW/track_ctrl/layout.py` has loop/count guards for
  Green only. Red runs (5 waysides, single train to block 45) but multiple trains and
  the two-way sidings are untested. Track Controller owner (Harry Tye).
- **Green PLC logic** — the five review points above.
- **Pi load** — Green HW step ≈3.3 ms vs ≈1.8 ms for Red in-process; USB time with a
  full Green fleet unmeasured.
- **Pre-existing test failures** — who owns the `test_hw_language` and ticket-sales
  failures.
- **Layout duplication** — `Track_layout/` vs `TrackModel/` JSON; the generator and the
  host coverage check read `Track_layout/`.

## Ideas rejected

| Idea | Why rejected |
| --- | --- |
| Feed the CTC from the Track Model's `signal_states` | Bypasses the Track Controller; the data is already in its report. |
| Report the commanded aspect instead of the lamp lit | Contradicts the recorded boundary; they differ only for a tick or under a lamp failure, where the lit lamp is what a dispatcher should see. |
| Send both commanded and lit | Nothing asks for it. |
| `aspect` on each occupancy entry | Changes the shape of `block-occupancy`; mixes two facts. |
| Separate top-level CTC input for signals | Same size, second field to keep in step. |
| Aspect in the switch detail panel only | Kevin chose map markers. |
| Train interior/exterior lights to the CTC | Kevin confirmed wayside signals. |
| **(rev)** Letter-only markers (R/Y/G/SG on a coloured disc) | Prototyped; unreadable at the default zoom, leaving colour as the only cue. |
| **(rev)** Hiding signals that have not reported | A missing marker reads as "no signal here"; hollow "?" shows the gap. |
| **(rev)** "No duplicates" validation for signals | The CTC's existing rule accepts identical repeats; two waysides can legitimately report the same block. |
| Separate `--track-hw-line` / `--train-hw-line` | Prototype confirmed one flag suffices; the pairs stay independent in code, so splitting later is cheap. |
| Line assignment in `config/pi-testing.json` | Strict schema for Pi test modes; different concern. |
| Swap which executable runs under each module name | Breaks the codec split and the fixed Pi identity per module. |
| Both lines in each track controller, filtered in the harness | Two reports per line at the CTC merge. |
| **(rev)** Keeping the old tables exported as module constants | No importer exists; a stale default table invites wrong use. |
| **(rev)** Globbing starters as `{line}_*.json` | Picks up the partial Green fixtures alongside the full set. |
| Reuse HW's Red wayside files for SW on Red | Different cut and format; SW generates Red from the layout. |
| Reuse SW PLC programs for HW on Green | Do not load on HW; different cut and device names. |
| **(rev)** Hand-writing the Green HW files | The generator reproduces Red exactly; hand-typing 150 blocks is slower and unverifiable. |
| **(rev)** SW's six-wayside cut for HW Green | Splits switch 28's and 76's legs across waysides, so a moving switch cannot hold all its blocks. |
| **(rev)** Copying Red's "train on reverse leg ⇒ reverse" rule to switch 76 | Its reverse leg leads away from the points; the rule would throw the switch under an approaching train. |
| **(rev)** Porting SW's loop/count guards into the Green HW PLCs now | A safety design choice with no source; left to the owner, with the cut keeping it possible. |
| **(rev)** Per-train choice as a CTC field + dispatch toggle | Prototyped and works, but ≈65 extra lines, a wire-format change (`"controller": null` on every new train), and an unrendered QML toggle — for a choice automatic dispatch never makes. Build only if a dispatcher must pick at run time. |
| **(rev)** Naming the controller in `TRAIN_ADDED` only when non-default | Ambiguous once `--hw-line` can change the default. |
| Port `TrainController/` to Red | Unused by the harness; both variants share one code base. |
| Runtime reassignment of a running train | Needs controller-state handover. |
| Mixed lines inside one Track Controller HW | Refused by design; not required. |
| Fixing the `Track_layout/` duplication here | Unrelated; listed as an open item. |

## Verification

- All suites under pytest once it is installed, compared with the Phase 0a baseline.
- New tests: aspect pass-through (SW and HW), CTC `signals` validation and host property,
  swapped-assignment class, integration-set coverage for both lines, generator
  reproduces Red, mixed-controller class (if Phase 4).
- Headless with simulated Pis: `track_overflow.py --headless --speedup --test-pi process
  --load-starters --engineer-gains 400000 8000 --dispatch … --run-seconds 60` — gains
  are required or trains do not move **(rev)**. Run default, `--hw-line Green`, and (if
  Phase 4) `--hw-trains`.
- Windowed: CTC map at "Fit" zoom shows aspects readable without colour; CTC test UI
  `signal_states` row changes a marker; train controller console titles.
- Still not covered by any prototype: a physical Pi, pty mode, the windowed UIs, the CTC
  test-UI row on screen, a train entering/leaving the Green yard on HW, multi-train Red
  on SW, mixed fleet on Red, and every pytest-only test module.
