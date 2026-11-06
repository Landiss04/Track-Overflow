# Integration handover

This document consolidates the integration phase handovers and session prompts for the Track Overflow system integration: the Phase 3 to Phase 7 handovers, the Phase 5 to Phase 8 prompts (including the Phase 5 fixes prompt), the session handover of 2026-10-22 and the next-session prompt. Each section is a copy of its original, with the headings moved down to nest under the section. The originals are kept unchanged in `documents/archive/handover/`.

## Table of contents

- [Phase 3](#phase-3)
- [Phase 4](#phase-4)
- [Phase 5](#phase-5)
  - [Phase 5 handover](#phase-5-handover)
  - [Phase 5 prompt](#phase-5-prompt)
  - [Phase 5 fixes prompt](#phase-5-fixes-prompt)
- [Phase 6](#phase-6)
  - [Phase 6 handover](#phase-6-handover)
  - [Phase 6 prompt](#phase-6-prompt)
- [Phase 7](#phase-7)
  - [Phase 7 handover](#phase-7-handover)
  - [Phase 7 prompt](#phase-7-prompt)
- [Phase 8](#phase-8)
- [Session handover 2026-10-22](#session-handover-2026-10-22)
- [Next session prompt](#next-session-prompt)

## Phase 3

Source: archive/handover/integration-handover-phase-3.md

### Integration handover: Phase 3 to Phase 4

Written 2026-10-20 at the end of the session that built Phase 3, on branch
`claude/quirky-fermi-sickg4`. It is for whoever picks the work up next, person or agent.
It says what Phase 3 built, how it was validated, the open questions, and how to begin
Phase 4. The plan and the history are in `documents/system-integration-design.md`
(v0.10; Phase 3 is section 5.4); how a module joins the harness is in
`common/harness/README.md`.

The first session stopped partway through validation, at Kevin Schillinger's request.
A second session on the same day finished it: the measurement runs, the frozen build
and the document updates (section 2).

#### 1. Phase 3 as built

Phase 3 in the plan: "Track Controller SW on Green: commanded speed and authority per
block, switches, signals, readiness, failures."

##### What runs

`python track_overflow.py` starts the harness and seven module processes. Four now run
as themselves: the Track Controller SW (new), the Track Model, the Train Model and the
Train Controller SW. Three are stubs: the CTC Office, the Track Controller HW and the
Train Controller HW.

1. The Track Controller SW runs the Green Line only (R77): six waysides, `GTC-01` to
   `GTC-06`, 25 blocks each. It starts **not ready**. A person loads a PLC program on
   every wayside in its window, either RUN then COMMIT on each, or **Load starters**
   (R44). `--load-starters` on the harness command line commits the generated starter
   programs at launch instead, for tests and demonstrations.
2. Until then the clock runs, nothing is released, and the harness logs
   `WAYSIDES_NOT_READY` with the waysides and the reason. Once all are ready, it logs
   `WAYSIDES_READY`.
3. A scripted CTC Office in the harness (`common/harness/ctc_script.py`) stands in for
   the CTC Office's dispatch and suggestions until Phase 4. It answers in the CTC
   Office's own output form, so its suggestions reach the Track Controller over the
   edge the real CTC Office will use. It releases G1 once Green is ready and its yard
   exit block (63) is clear. It follows G1 from occupancy. Each tick it suggests
   speed and authority for G1's block and, while authority is at least 1, for the
   next block with one block less (R49). Authority stops short of any occupied block
   ahead. The CTC Office's stub still presses Run and sets 10x.
4. The Track Controller passes each suggestion down that block's track circuit through
   its PLC program and vital layer. Switches, lights and crossings go to the Track
   Model, and the Track Model's read-back comes back to the Track Controller and on to
   the CTC Office's input. A failed block reads occupied on the way (R33, R69).
5. With starters loaded: release at tick 2. The Track Model takes G1 at tick 3, the
   Train Model at 4, the Train Controller at 5. G1 runs 63 to 73: it stops at
   GLENBURY (65) for the 45 s dwell, which the Train Controller enforces, and ends at
   DORMONT (73). There is no emergency brake and no pickup-failure latch on the way.

##### Changed, by file

| Where | What |
|---|---|
| `TrackCtrlSW/track_ctrl/module_process.py` (new) | The process the harness starts (`--module track-controller-sw`): Green only, the window, `--load-starters`, steps through the module's own JSON forms (`track_ctrl.wire`), and the step's unwrapped time as the module's. Bad input refuses the tick and changes nothing. No test link: the harness is the one driver. The header shows the clock paused once no step has come for 1 s; the 10x badge stays hidden. |
| `TrackCtrlSW/track_ctrl/state.py` | `TrackControllerState(lines=...)`: the lines to start with; defaults to Green and Red as before. |
| `TrackCtrlSW/track_ctrl/layout.py` | `default_layout_dir()` finds the layouts in a built executable's bundle too. |
| `TrackCtrlSW/track_ctrl/controller.py` | **Starter program, for the owners to review.** The separation rule held every block beside an occupied one, including the empty next block the CTC Office preloads for the train about to enter it (R49, truth `track-signal`). So a train read speed 0, authority 0 at every block it entered, and the Train Controller latched a pickup failure. Now only a block with a train in it is held: `AUTH_n := NOT (OCC_n AND (OCC_n-1 OR OCC_n+1))`. Two trains side by side are still both held. |
| `TrackCtrlSW/ui/components/SwitchDialog.qml`, `ProgramView.qml`, `StatusView.qml` | **For the owners to review.** The dialog's `applied` signal clashed with `Dialog.applied()`. PySide6 6.11 warns on every launch, and the harness test requires empty stderr. Renamed to `switchApplied`, and `released` to `switchReleased`. The warning did not stop the signal working. |
| `TrackCtrlSW/tests/test_module_process.py` (new), `test_boundary.py`, `test_world.py` | 6 tests for the process; 2 for the starter rule. Two world tests rewritten for the new rule: an empty block beside a train passes its suggestion; a train beside a train is held. |
| `common/harness/track_devices.py` (new) | Each switch's ID (the block it is listed on, truth `identifiers`, the Track Controller's name), its point (the Track Model's name) and the block of the Track Model's light, read from the layout files. Green: 12/13/14, 28/28/27, 58/57/56, 62/63/64, 76/77/78, 85/85/84. |
| `common/harness/wayside_edges.py` (new) | Four pure edges on JSON: CTC Office → Track Controller (train ID dropped, R48; of two suggestions for one block the lower of each wins), Track Model → Track Controller, Track Controller → Track Model, Track Controller → CTC Office (occupancy, switches, crossings, waysides). Also `line_ready`. |
| `common/harness/ctc_script.py` (new) | The scripted CTC Office (point 3 above). Replaces `wayside_script.py` (deleted). |
| `common/harness/edges.py` | Rewired: the stand-in steps on the Track Controller's outputs of the tick before (module timing, R1); readiness events; the Track Controller's commands to the Track Model; the roster takes the stand-in's release. |
| `common/harness/modules.py`, `track_overflow.py` | The Track Controller SW is wired and registered. |
| `common/harness/app.py`, `measure.py` | No stub release cue. `app.py --load-starters`. `measure.py --system` loads the starters. |
| `common/harness/track_edges.py` | The wayside-only helper `block_commands_to_track_model` is removed. |
| `common/harness/tests/` | `test_harness_edges.py` (55): the switch places checked against both modules' own layout readers on Green and Red, the four edges, and each edge's output fed to the receiving module's own decoder (`track_ctrl.wire`, `track_model.wire`, `ctc.wire`). `test_harness_train_loop.py` (21): the four modules' own code in one process, through JSON: readiness, the route, the dwell, switch and light read-back by both names, crossings, a broken rail ahead, the emergency brake. `test_harness_system.py` (11): end to end with real processes, plus a run with no programs loaded. `test_harness_window.py`: system mode passes `--load-starters` and expects `WAYSIDES_READY`. |

##### Behaviours worth knowing

- **Light on block 64.** Under the starter program the driver sees YELLOW on block 64.
  The Track Model stands the light of the yard switch (Green 62) there, and the starter
  shows it YELLOW while 63 or 64 is occupied, as it is with G1 in them. Phase 2's
  scripted wayside commanded GREEN.
- **Failure ahead.** With block 68 broken, the stand-in's authority drops from 9 to 3,
  then counts down to 0. G1 stops in 67 on the service brake, with no emergency brake
  and no latch, and goes on once the rail is repaired.
- **Crossings.** Not ready, every wayside holds its crossings down (fail-safe), and the
  Track Model shows Green 19 and 108 down. Once started up they lift.
- **Heaters.** The harness sends the Track Model no heater commands (D026). The Track
  Model still runs heaters only when commanded, so they never run; see Q6.

#### 2. Validation: done, and left to finish

##### Done in the first session

| Check | Result |
|---|---|
| `common/harness/tests`, by file | edges 55, loop 21, system 11 (15.5 s), window 2: all pass |
| `common/harness/tests`, all together | 140 passed, 1 failed before the window-test fix; that file passes on its own since. Not re-run as one suite. |
| `TrackCtrlSW`: `python -m unittest discover -s tests` | 194 pass (186 before: +6 process, +2 starter rule) |
| `TrackModel`: pytest | 309 pass |
| `utils`: pytest | 64 pass |
| mypy, the harness files changed | clean, apart from 2 errors already at HEAD in `app.py` and `measure.py` (`HarnessWindow` given a `QCoreApplication`; see Q11) |
| mypy, `TrackCtrlSW` (`mypy main.py test_main.py track_ctrl/ track_ctrl_test/`) | clean, 23 files |
| flake8 `--max-line-length=79`, every new or changed Python file | clean. Older lines in `TrackCtrlSW` tests and `state.py` still have pre-existing hits; that module runs only mypy (its D3). |
| Budget, `measure --system --seconds 15 --speed 10`, headless | 10.00x, 1,510 of 1,509 ticks, round trip mean 4.76 ms, median 3.59, p95 12.79, p99 19.85, max 94.65; 0 slipped, 0 late; ready after 1.03 s; harness CPU 25% (Phase 2: 3.5 to 3.8 ms mean, 17%) |

##### Finished in the second session

Run on 2026-10-20 in a Linux cloud container (`vm`, Ubuntu 24.04.5, four-core 2.1 GHz
Xeon), Python 3.13.16, PySide6 6.11.2, PyInstaller 6.22.2, with
`QT_QPA_PLATFORM=offscreen`, against commit `1a9ce27`. No code was changed.

| Step | Check | Result |
|---|---|---|
| 1 | `python -m pytest -q common/harness/tests`, in one run | 140 tests, not 141: edges 55, loop 21, system 11, window 2, and 51 from earlier phases. All passed in 4 of 8 runs. The other 4 failed one test, `test_harness_console.py::ConsoleFaultRunTest::test_startup_timeout_names_the_loading_module` (Q15). Older than Phase 3: the commit before (`c311800`) failed it in 4 of 12 runs. The file alone passed 10 of 10 at both. |
| 2 | `TrainModel`: `python -m pytest -q` | 855 passed, 13 skipped |
| 2 | `Train-Ctrl_HW`: `python main.py --check`, and `python -m pytest -q tests` | 0 QML warnings, 0 behaviour problems; 10 passed. (`python check.py` alone prints nothing and exits 0; the self-check runs through `main.py --check`.) |
| 2 | `CTC-Office`: `python -m pytest -q` | 208 passed, 251 subtests |
| 2 | `TrackCtrlHw`: `python -m unittest discover -s tests -t .` | 62 run, 1 failure: the known sample-wayside test (`test_territory.SampleWaysides.test_samples_match_the_course_layout_file`, `next_blocks`) |
| 2 | Also: `TrackCtrlSW` unittest, `TrackModel` pytest, `utils` pytest | 194 OK; 309 passed; utils 64 passed on the second and third runs, 1 failure on the first (not captured; the clock-driver test is the known one) |
| 3 | `measure --system --seconds 15 --speed 1` | 1.01x, 151 of 150 ticks, round trip mean 4.77 ms, median 4.53, p95 6.91, p99 8.28, max 10.21; 0 slipped, 0 late; ready after 1.36 s; CPU 3% |
| 3 | `measure --system --seconds 15 --speed 10 --window` | 10.00x, 1,508 of 1,508, mean 5.24 ms, median 4.22, p95 12.31, p99 18.62, max 82.53; 0 slipped, 0 late; ready after 1.38 s; CPU 26% |
| 3 | `measure --system --seconds 15 --speed 10`, repeat | 10.00x, 1,504 of 1,504, mean 4.35 ms, median 3.35, p95 11.97, p99 16.91, max 36.48; 0 slipped, 0 late; ready after 1.12 s; CPU 22% |
| 4 | Frozen build, with `--paths "$PWD/TrackCtrlSW"` and `--add-data "$PWD/TrackCtrlSW/ui:TrackCtrlSW/ui"`, output outside the checkout | Built, 483 MB. Alone, `--module track-controller-sw --harness <none>` loaded the Green layout and `_MEIPASS/TrackCtrlSW/ui/Main.qml`, then exited 2 (harness lost; 1 would mean no window). `--headless --speedup --load-starters --run-seconds 12` from outside the checkout, empty `PYTHONPATH`: `WAYSIDES_READY` and `TRAIN_ADDED` at tick 2, 974 ticks, no fault events, seven exits of code 0. |
| 5 | Documents | `documents/system-integration-design.md` v0.10 (section 5.4; G-CLK-6, G-LIFE-2, G-RUN-2, G-RUN-7, G-HW-2, G-SIG-1, -2, -3, -5, -8, -14, -18, G-NEW-1; Appendix A); `common/harness/README.md`; `TrackCtrlSW/README.md`; `TrackCtrlSW/INTEGRATION_DISCREPANCIES.md` (A3, C6, E1, E2; new E5 starter rule, E6 dialog rename); `TrackModel/README.md`; `TrackModel/INTEGRATION.md`; `TrainModel/docs/open-issues.md`. No truth proposal: nothing new was decided. |
| 6 | Commit and push | On `claude/quirky-fermi-sickg4`. |

The Track Controller's window ran offscreen in every measurement, with its 200 ms
refresh; no tick slipped at 10x with it.

#### 3. Open questions

Each is the user's or a module owner's to decide. Where there is a recommendation, it
comes first.

| # | Question | Who | Recommendation |
|---|---|---|---|
| Q1 | Keep the starter program's new separation rule? | Harry Tye (Track Controller) | Keep. The old rule contradicts truth `track-signal` and `suggested-speed` (the next block carries the train's values), and the run cannot pass a block without the change. |
| Q2 | Keep the switch dialog's signal rename? | Track Controller SW owners | Keep. |
| Q3 | The Track Model names a switch by its point (`GREEN D-13`); truth `identifiers` names it by the block it is listed on (Green 12). Should the Track Model change, or the harness keep mapping? | Track Model owner, Kevin | Keep the harness mapping (`track_devices`) for now; log the difference as a Track Model discrepancy. |
| Q4 | Lights: one per switch in both modules. The Track Controller names it by the switch; the Track Model stands it on the block before the point. Is the harness's mapping through the switch right? With the starter program, G1 leaving the yard sees the yard switch's light YELLOW, from a light that faces away from it (`TrackModel/BUGS.md` B1, second part). | Track Controller and Track Model owners | Accept the mapping; fix B1 in the Track Model. |
| Q5 | Red `75-yard` sits on block 9's row. The Track Controller reads its normal leg as 9, the Track Model as 76, so NORMAL means different blocks for that one switch. | Kevin, before Phase 5 | Settle the layout data before Phase 5. |
| Q6 | D026: the Track Model is to switch its heaters itself, but still runs them only when commanded, and nothing commands them now. What rule should it follow (D026 leaves it open)? | Track Model owner | Decide the rule, then implement it in the Track Model. |
| Q7 | The starter program never throws switch 58 (`57-yard`), so no train can be routed into the yard. A return to the yard needs a program that throws it, or a CTC switch command, which is maintenance-only. | Harry Tye, Landis | Needed for Phase 4's retire path; decide before building it. **Resolved:** Kevin Schillinger said "fix" on 2026-10-21; done in `234c353`. The starter sets each switch for the train coming to its points, and retirement needs only a stop at 57 (D022), so 58 stays normal. Left for Harry Tye and Landis (`TrackCtrlSW/INTEGRATION_DISCREPANCIES.md` E7): the new `SUG_n` and `REV_s` PLC inputs; switch 28 standing reverse at rest; whether the vital lock should also be on the points block; the follower case at 76; and Landis to confirm the CTC Office's two-way zone. |
| Q8 | Should `STEP` tell modules the clock's speed? The Track Controller's header infers "paused" from steps stopping and cannot show 10x. | Kevin | Low priority. If wanted, it is a protocol change to D005 (a truth proposal). |
| Q9 | The Track Controller still uses lower-case enumerated values (`normal`, `red`). The design document records all capitals as "already decided" for both variants. | Track Controller owners | The edges map either way; leave it to the owners. |
| Q10 | Should the operator window show each line's readiness? It is in the event log now. | Kevin | Optional. |
| Q11 | Two mypy errors already at HEAD in `common/harness/app.py` and `measure.py` (`HarnessWindow` typed for a `QGuiApplication`). | Kevin | Narrow the type with a `cast` or an `isinstance` check; trivial. |
| Q12 | Under the starter program, two trains in adjacent blocks hold each other forever. The CTC Office's exclusive authority should keep them apart; the starter cannot tell direction. | Harry Tye | Note it in the Track Controller's README; no change now. |
| Q13 | The CTC Office sends one suggestion per train, its head block only. R49 and truth `suggested-speed` need the next block too while authority is at least 1. Fix it in the CTC Office, as R82 was fixed in the Train Controller? | Landis, Kevin | Yes: it blocks Phase 4 (section 4). **Resolved:** Kevin Schillinger directed on 2026-10-20 "fix Q13 and Q14 in the CTC"; done in `9c440d6`. |
| Q14 | The CTC Office's outputs have no `new_trains` or `retired_trains`, which the roster needs (R35, R46, D022). Add them to its boundary? | Landis, Kevin | Yes: it blocks Phase 4. **Resolved** by the same direction; done in `9c440d6`. |
| Q15 | `test_harness_console.py`'s fault run fails now and then in the full harness suite: its 0.3 s startup timeout is meant to catch only the Train Model stub (600 ms delay), but the stubs take 0.13 to 0.27 s to be ready, so the Train Controller SW stub sometimes misses it too. Once that stub crashes at tick 8 by script it is not ready again, and `startup_timed_out_modules` still names it. Older than Phase 3 (section 2). | Kevin (harness) | None yet. The test needs a margin that does not depend on process start time. **Fixed** in `428852b`: a 2.0 s timeout, a 4.0 s late stub, and exactly the Train Model named. |

No truth proposal was filed in Phase 3: no new normative fact came from a decision or a
direct statement. `truth/_inbox/claude/quirky-fermi-sickg4/` holds 16 proposals from
earlier in the session, the D007 dwell among them, awaiting promotion by a person. If
Q1, Q3 to Q6, Q8, Q13 or Q14 is decided, file the decision as a proposal then. On
2026-10-21 one more was filed, for Phase 4 handover Q-P4-4
(`20261021-1445-lower-limit-ahead-train-controller-slows.md`); the inbox now holds 17.

#### 4. Phase 4: beginning

Phase 4 in the plan: "CTC Office: dispatch from the yard, suggestions, occupancy, ticket
sales and clock control. The Iteration 3 scenario on Green: dispatch a train from the
yard to a station (2026-11-12)."

##### What is ready for it

- **Edges built and checked against the CTC Office's own decoder:**
  - `wayside_edges.track_controller_to_ctc` makes the CTC Office's `track_controller`
    input (`ctc.wire.inputs_from_wire` accepts it);
  - `ctc_to_track_controller` takes the CTC Office's outputs as `ctc.wire.to_wire`
    makes them (`dataclasses.asdict`).
- **The harness reads the clock controls already:** `clock_paused` and `clock_speedup`,
  from the CTC Office's outputs and from `STATE` while paused (R51).
- **The roster** applies `new_trains` and `retired_trains` events exactly once.
- **The CTC Office module** (`CTC-Office/ctc/model.py`) has `step(dt, inputs)` and
  `snapshot()`. It already holds back everything for a line until every wayside on it
  reports ready (`_ready_lines`). It follows trains from occupancy (`ctc.tracking`),
  schedules and routes.

##### What it lacks (from the code, 2026-10-20)

1. **The next-block suggestion (Q13).** `CtcOffice._outputs` sends one
   `TrainSuggestion` per train, for its head block. Between a train entering a block and
   the CTC Office seeing it there (Track Model → Track Controller → CTC Office → Track
   Controller → Track Model, about 4 ticks), the new block carries nothing. The train
   then reads 0 and 0 and its Train Controller latches a pickup failure. Phase 3's
   stand-in shows what is needed (`ctc_script._suggest`): the next block with authority
   one less and that block's own speed, while authority is at least 1. Guard it with the
   loop test `test_authority_never_falls_from_two_blocks_to_none`.
2. **Train events (Q14).** The CTC Office creates a train when it releases it from the
   yard (R35, R46) and retires it at the yard entry block (Green 57, Red 9) at a stand
   with authority 0 (R46). Neither event is in `CtcOutputs`. The roster expects
   `new_trains: [{"train_id", "line"}]` and `retired_trains: [{"train_id"}]`. Release
   only when (R46):
   - the exit block is clear;
   - no train is authorized into it;
   - the line's waysides are ready;
   - the scheduler is not holding the run.
3. **A process for the harness.** There is no `--module ctc-office` process yet. The
   window (`ctc_ui`) owns a `SystemClock` and a `ClockDriver` (`sim_clock.py`), and
   serves the CTC test UI over `ctc.socket_link` and `ctc_ui/clock_link.py`. Under the
   harness:
   - the harness owns the clock (D005, D017);
   - the process steps the model once per `STEP`, shows the harness time, and reports
     Run, Pause and the speed through `clock_paused` and `clock_speedup`;
   - while paused it pushes `STATE` (R51);
   - it opens no test link, since the CTC test UI stands in for the Track Controller
     only (D025).

   Follow the Track Model's and the Track Controller's `module_process.py`. Tests need
   a way to press Run without a person, like the stub's `--run-on-ready`.
4. **Ticket sales.** Track Model `ctc.tickets_sold_now` → CTC Office
   `track_model.ticket_sales`, sales since the last report, exactly once per tick
   (R52). Only Green and Red stations reach it, since the Track Model loads no Blue
   Line (R67). Write the edge in `track_edges.py` or a new `ctc_edges` in JSON.
5. **The Train Model's view of the yard.** A released train is placed by the harness at
   the yard exit block (`placement_report`), as now. Check that the CTC Office's
   `ctc.tracking` finds it there ("found by leaving the yard") with the harness's
   latency, and that its too-early check is not set off by tick timing.

##### Plan

1. With Landis and Kevin: settle Q13 and Q14 (Q7 too, if the scenario returns trains to
   the yard). File the boundary additions as truth proposals once decided.
2. Add the next-block suggestion and the train events to `ctc/model.py`, with the CTC
   Office's own tests.
3. Write `CTC-Office/ctc/module_process.py` and register `ctc-office` in
   `track_overflow.py`. Add `CTC_OFFICE` to `WIRED_MODULES`.
4. In `SystemEdges`:
   - the CTC Office's inputs: `track_controller_to_ctc` of the Track Controller
     outputs, merged across the SW and the HW once Phase 5 wires the HW, and ticket
     sales;
   - the Track Controller's `ctc` input from `outputs[CTC_OFFICE]` instead of the
     stand-in;
   - the roster from the CTC Office's events only.

   Keep `ScriptedCtc` for the loop tests, or retire it with its tests.
5. Tests: the loop test with the CTC Office's own code; end to end with the Iteration 3
   scenario: dispatch G1 from the yard to a Green station, schedule or manual, with
   Run pressed by the test.
6. Measure, freeze, document (§5.5 "Phase 4 as built"), commit, push.

##### Risks

- The CTC Office's window is the heaviest UI; at 10x its redraw may hold up replies. The
  Track Model needed a deferred, throttled redraw (`WINDOW_REFRESH_MS`). Expect to do
  the same.
- Clock ownership moves from the CTC Office window to the harness. Its clock bridge and
  clock link must stand down under the harness without breaking standalone use.
- Release and retire timing against occupancy latency: test the too-early failure
  inference with real tick timing.

## Phase 4

Source: archive/handover/integration-handover-phase-4.md

### Integration handover: Phase 4, the CTC Office

Written 2026-10-20 at the end of the session that built Phase 4, on branch
`claude/quirky-fermi-sickg4`. It is for whoever picks the work up next, person or agent,
and for the merge of these notes into `documents/system-integration-design.md` (a §5.5
"Phase 4 as built") and `common/harness/README.md`. It follows
`documents/integration-handover.md#phase-3`.

Updated 2026-10-21 with Kevin Schillinger's answers to the open questions (section 4)
and the work done on them since `a55b8b9` (section 6), including the round-trip
unblock in `460579b` and the targeted verification recorded below.

Phase 4 in the plan: "CTC Office: dispatch from the yard, suggestions, occupancy, ticket
sales and clock control. The Iteration 3 scenario on Green: dispatch a train from the yard
to a station (graded 2026-11-12)."

The CTC Office's own changes for Q13 (the next-block suggestion) and Q14 (`new_trains`,
`retired_trains`) were made by the CTC Office's side in `9c440d6`. This file covers the
integration built on them.

#### 1. As built

##### What runs

`python track_overflow.py` starts the harness and seven module processes. Five run as
themselves: the CTC Office (new), the Track Controller SW, the Track Model, the Train
Model and the Train Controller SW. The two HW variants are stubs.

1. The clock starts paused (D017). The dispatcher presses Run in the CTC Office's
   window; a headless, `--stubs-only` or `--auto-run` run has the CTC Office press it
   once ready (`--run-on-ready`; Q-P4-1, R83). The harness reads Run,
   Pause and 1x / 10x from its outputs and its `STATE` (R3, R51).
2. A person loads the PLC programs (R44), or `--load-starters` commits the starters.
   Until every Green wayside is ready, the CTC Office sends nothing for Green and
   refuses a dispatch on it.
3. The dispatcher dispatches a train from the yard in the CTC Office window, or
   `--dispatch TRAIN:LINE:BLOCK` on the harness command line gives that dispatch once
   the line is ready, for a demonstration.
4. The CTC Office releases the train itself (D022, R46) and reports it once in
   `new_trains`. The harness places it on the yard exit block (Green 63), and it joins
   the Track Model, the Train Model and the Train Controller a tick apart, as before.
5. The CTC Office finds it at 63 when that block fills and follows it from occupancy.
   Its suggestions, the train's block and the next one (R49), reach the train through
   the Track Controller. The train moves once an engineer sets its gains (D024).

The Iteration 3 scenario, as tested (starters loaded, gains by test option, `--dispatch
G1:Green:65`): the waysides report ready at tick 1; the CTC Office reads that at tick 2,
takes the order, and releases G1 at tick 3. The Track Model has G1 at tick 4, the Train
Model at 5, the Train Controller at 6. G1 runs 63, 64, 65 at up to 18 m/s and stops in
GLENBURY with its right-hand doors open about 37 simulated seconds after the release. No
emergency brake, no pickup-failure latch, no fault event.

Automatic mode also runs (`--schedule utils/schedule_v4.json` on the CTC Office process,
checked in one process only): G1 is released at 05:00, G2 at 05:03, and both run their
first legs.

##### Changed, by file

| Where | What |
|---|---|
| `CTC-Office/ctc/module_process.py` (new) | The process the harness starts (`--module ctc-office`). One module in its window, stepped once per `STEP` on `ctc.wire` inputs; outputs by `ctc.wire.to_wire`. No `SystemClock`, `ClockDriver`, socket link or clock link (D005, D017, D025). Unknown input keys, a malformed entry, or anything the module refuses raise `TickRejectedError`; the module is unchanged. The window redraws at most every 200 ms (`WINDOW_REFRESH_MS`), after the reply. Layout files found from source or a built bundle. Test and demonstration options: `--run-on-ready`, `--speedup-at-tick N`, `--dispatch TRAIN:LINE:BLOCK`, `--schedule FILE`. |
| `CTC-Office/ctc_ui/harness_clock.py` (new) | `HarnessClockBridge`: the same QML face as `SimulationClockBridge` (`timeText`, `paused`, `speed`, `pause()`, `resume()`, `setSpeed()`). Shows the time of each step; each press sets the module's output and goes to the harness as `STATE`. A press before `READY` waits for it. |
| `CTC-Office/ctc_ui/ctc_host.py` | `CtcHost(serve_test_ui=False)` opens no test link. `step_at` steps the module for the harness and counts the step's ticket sales in its hour; `refresh` redraws; `start_at` starts the history at the harness's time; `module` exposes the module. Standalone use is unchanged. A pre-existing mypy error fixed (`bool(clock.paused)`). |
| `CTC-Office/ctc_ui/test_harness.py` | The test UI's outputs table names the next-block suggestion's rows `next_block[T]`, `next_suggested_speed[T]`, `next_authority[T]`, so a train no longer shows two rows of one name. `ctc_host._suggestions` keeps the train's own block (listed last), now commented. |
| `CTC-Office/ctc_ui/README.md` | Two suggestions per train, the train events, and a section on running under the harness. |
| `CTC-Office/tests/test_module_process.py` (new) | 13 tests: JSON form, no test link, refusal changes nothing (6 bad inputs and a bad dt), ticket sales counted once, header time, starts paused at 1x, Run/Pause/speed as `STATE` and not before `READY`, redraw after the reply, and the four test options. |
| `track_overflow.py` | `ctc-office` registered (`_import_from("CTC-Office")`). |
| `common/harness/modules.py` | `CTC_OFFICE` in `WIRED_MODULES`. |
| `common/harness/edges.py` | `SystemEdges()` no longer takes a stand-in. The CTC Office's inputs: every wired Track Controller's report joined, and ticket sales. The Track Controller's `ctc` from `outputs[CTC_OFFICE]`. The roster from the CTC Office's own events. Readiness events from each Track Controller's fresh outputs. |
| `common/harness/wayside_edges.py` | `merge_ctc_inputs`: joins Track Controllers' reports list by list, for the HW variant's Red reports in Phase 5. |
| `common/harness/track_edges.py` | `track_model_to_ctc` (stations that sold none left out; a count that is not a whole number is an error) and `TicketSales`: sales wait until the CTC Office replies with outputs to the tick they were sent on, so a refused or missed tick is sent again with the next, and a Track Model's repeated last outputs are never counted twice (R52). |
| `common/harness/ctc_script.py` | Deleted, with its tests: the CTC Office's own code replaces it in the loop and end-to-end tests. |
| `common/harness/app.py` | No stand-in; `--dispatch` passed to the CTC Office. (Minimal change; the bug-fix agent's `EventLog.create` change in the same file was committed separately, in `122b279`.) |
| `common/harness/measure.py` | `--system` runs the real CTC Office: Run (and 10x) and `--dispatch G1:Green:73`, so the train runs for the whole measurement. |
| `common/harness/tests/` | `test_harness_edges.py` (53): readiness events, the CTC Office's inputs, the Track Controller's `ctc` from the CTC Office, ticket sales once across accepted and refused ticks, `merge_ctc_inputs`, and the real Track Model's stations accepted by the CTC Office's own validator. `test_harness_train_loop.py` (23): the five modules' own code in one process, CTC Office included. `test_harness_system.py` (11): the Iteration 3 scenario end to end. `test_harness_window.py`: system mode passes `--dispatch`. |

##### The CTC Office's tracking under harness timing

- **Found at the yard exit.** The harness places a released train on 63 at the tick after
  the release; the Track Model reports it occupied that tick; the Track Controller a
  tick later; the CTC Office reads it a tick after that. It finds the train it released
  ("leaving the yard"), every time, in the loop and end to end.
- **Too-early inference.** Not tripped. The loop test follows the CTC Office's view of
  G1 block by block from 63 to 73 and checks the heads are exactly the route, with no
  train lost. The latency of about 3 ticks is the same for every block change, and the
  CTC's reach estimate uses the fastest speed it suggested, so a block is never reached
  "too soon".
- **A failure ahead** (68 broken while G1 is in 64): the CTC Office takes 68 as a
  failure, stops G1's authority short of it (`reason "occupied", at "68"`), G1 stops in
  67 on the service brake, and goes on once the rail is repaired.

#### 2. Validation

Scratch venv (Python 3.13, PySide6 6.11.2), `QT_QPA_PLATFORM=offscreen`, on a four-core
Linux VM, 2026-10-20. Runs include other agents' uncommitted work in `core.py`,
`supervisor.py`, `utils/` and the harness window.

| Check | Result |
|---|---|
| `python -m pytest -q common/harness/tests`, one run | 150 passed, 495 subtests (49 s) |
| by file: edges, loop, system, window | 53; 23 (13 s); 11 (8 s); passes |
| `CTC-Office`: `python -m unittest discover tests` | 244 OK |
| `TrackCtrlSW`: `python -m unittest discover -s tests` | 194 OK |
| mypy, harness files changed (`--explicit-package-bases --disallow-untyped-defs --follow-imports=silent --ignore-missing-imports`) | clean apart from the 2 known `HarnessWindow` errors in `app.py` and `measure.py` (Phase 3 Q11) |
| mypy, CTC files changed (`MYPYPATH=..`, `--disallow-untyped-defs`) | clean; the 17 errors in `routing.py`, `model.py` and `scheduler.py` were at HEAD. Without `MYPYPATH=..` mypy cannot find `utils` and `ui`. |
| flake8 `--max-line-length=79`, files changed | clean, apart from the `N815` Qt signal names already in `ctc_host.py` and `test_harness.py` |
| In-process step cost per tick (loop) | CTC Office 0.7 ms, Track Controller 1.5, Track Model 0.45, Train Model 0.25, Train Controller 0.08 |

**Budget** (`python -m common.harness.measure --system --seconds 15`), every window
offscreen, one train running, five real modules:

| Front end | Speed | Reached | Ticks | Round trip mean | median | p95 | p99 | max | Ready after | Harness CPU |
|---|---|---|---|---|---|---|---|---|---|---|
| Headless | 10x | 9.99x | 1,502 of 1,503 | 5.77 ms | 4.01 | 16.74 | 26.10 | 37.38 | 1.13 s | 22% |
| Headless | 10x | 10.00x | 1,505 of 1,505 | 5.14 ms | 3.36 | 16.20 | 24.54 | 46.22 | 1.41 s | 22% |
| Window | 10x | 9.99x | 1,503 of 1,505 | 5.82 ms | 4.05 | 17.00 | 26.09 | 45.92 | 1.02 s | 25% |
| Headless | 1x | 1.01x | 151 of 150 | 7.11 ms | 5.53 | 17.35 | 23.72 | 30.96 | 1.29 s | 3% |

No tick slipped and no reply was late. The mean is about 1 ms above Phase 3's (4.76 ms)
and p95 about 4 ms, from the CTC Office's step and its window redraw. One tick in about
twenty runs over 10 ms; the ticks after it make the time up.

The same suites re-run at `b65fd26`, with every fault fix committed, gave the same
counts: harness 150 (pytest, 495 subtests; unittest 150), utils 82 (37 subtests), CTC
Office 244, Track Controller SW 194.

**Frozen build** (G-RUN-2), done after this file was first written. The recipe in
`common/harness/README.md` with `--paths "$PWD/CTC-Office"` and
`--add-data "$PWD/CTC-Office/ctc_ui/ui:CTC-Office/ctc_ui/ui"` added, built outside the
checkout with PyInstaller 6.22.2 and the same scratch venv (483 MB). Nothing else was
needed: the window's QML imports the shared `ui/` folder and the layouts are the Track
Model's files, both bundled already.

| Check | Result |
|---|---|
| `track-overflow --module ctc-office --harness <none>`, alone | Loaded `_MEIPASS/CTC-Office/ctc_ui/ui/Main.qml`, then exited 2 (harness lost; 1 would mean no window). |
| `track-overflow --headless --speedup --load-starters --dispatch G1:Green:65 --run-seconds 15`, from `/tmp`, empty `PYTHONPATH` | `WAYSIDES_READY` at tick 1, `TRAIN_ADDED` G1 on Green at tick 3, 1,381 ticks, round trip mean 5.4 to 6.1 ms per 5 s; no fault events; seven exits of code 0. |
| The same, window mode, offscreen, `--run-seconds 8` | The same events, no faults, seven exits of code 0. |

`ctc.track_layout.LAYOUT_DIR` and `TrackMapModel()` with no layout, found from their
source files, are used only by the standalone window (`ctc_ui/__main__.py`), the test
UI and the tests. The process passes the layout to `CtcHost` and `TrackMapModel`, and
`CtcHost` passes it to the module, so no running path reads them in a build, and no
module code was changed. A schedule for `--schedule` is a file the user names; none is
bundled.

`app.py` has no option for the engineer's gains, so in these runs G1 stayed at the yard
exit (D024). A person sets them in the Train Controller's window; the tests use the
Train Controller's own `--engineer-gains`.

#### 3. Departures and design choices

- **Dispatch in the scenario.** A test option on the CTC Office process plays the
  dispatcher (`--dispatch`), given once the line is ready, as `--load-starters` plays
  the person loading programs. Manual dispatch to GLENBURY is the Iteration 3 scenario
  as stated; `--schedule` is there for automatic mode. See Q-P4-2.
- **Run on ready in a normal run.** Done in `68fcfa7` (Q-P4-1, R83): a window run waits for
  the dispatcher's Run in the CTC Office's window. `app.py` passes `--run-on-ready` only
  for a headless run, a `--stubs-only` run and a run with `--auto-run` (tests and
  demonstrations).
- **`STATE` on every press**, not only while paused: the harness reads it either way,
  and a Pause takes effect without waiting for the next reply. A scripted 10x press is
  sent after the reply, never inside a step, so a `STATE` never arrives before the reply
  it contradicts.
- **The CTC window's header** shows the dispatcher's Run/Pause and speed, not whether
  the harness clock is actually running (it also waits for every module, and for a late
  reply). The harness window gives the hold reason.
- **Readiness events** are now logged from the Track Controller's own outputs, the tick
  they come, not from a stand-in's view a tick later.
- **ScriptedCtc retired.** Every loop scenario (dwell, failure, emergency brake, switch
  and light) now runs on the CTC Office's own code; nothing needed the stand-in.

#### 4. Open questions

| # | Question | Who | Recommendation |
|---|---|---|---|
| Q-P4-1 | Should a normal run wait for the dispatcher's Run (D017), now that the CTC window has one? `app.py` presses Run automatically, as Phases 0 to 3 did. | Kevin, Landis | Keep `--run-on-ready` for headless and test runs; in window mode let the dispatcher press Run. A one-line change in `app.py`. **Decided:** Kevin Schillinger said "yes" on 2026-10-21: the harness presses Run automatically for headless and test runs only, and the dispatcher presses Run in the window otherwise (D017). Done in `68fcfa7`: `app.py` passes `--run-on-ready` only for a headless, `--stubs-only` or `--auto-run` run. |
| Q-P4-2 | For the graded Iteration 3 run, manual dispatch (the dispatcher in the CTC window, or `--dispatch`) or the course schedule in automatic mode? | Landis, Kevin | Manual dispatch to GLENBURY: it is the scenario as stated and needs no schedule. Both are tested to work. **Closed:** Kevin Schillinger said on 2026-10-21 "this should not matter for implementation". Both are supported. |
| Q-P4-3 | The "return to yard" action for manual trains (R66, D022) does not exist, and a scheduled run cannot reach the yard entry block in the full system: the starter program never throws switch 58 (Phase 3 Q7). So no train is ever retired in a real run. | Landis (CTC), Harry Tye (Track Controller) | Settle Q7 first, then add the action to the CTC Office. Not needed for Iteration 3, which ends at a station. **Done:** Kevin Schillinger said "yes add a button" on 2026-10-21; the action and a Return to yard button are in `4cc873b`. Phase 3 Q7 he answered "fix"; the starter sets each switch for the train coming in `234c353`, and retirement needs only a stop at 57 (D022). The full Green round trip and retirement at 57 now pass after `460579b` (Q-P4-8). |
| Q-P4-4 | Speed at a lower limit ahead: G1 enters block 67 (40 km/h, 11 m/s) at 18 m/s. The CTC Office suggests for 66 a little under 66's own limit (70 km/h), and nothing slows the train before 67. The Train Controller only follows the block it is in. | Landis (CTC), Train Controller owners | **Decided:** Kevin Schillinger on 2026-10-21: "for overspeed the train controller will handle slowing down immediately after entering the blcok". The CTC Office does not cap ahead. Already true: G1 enters 67 at 17.9 m/s, the service brake is on from the first tick, and it is under 11.1 m/s in 4.8 s, about 70 m, with no emergency brake. Tested in `0305d05`; proposal `20261021-1445-lower-limit-ahead-train-controller-slows.md` (`66aa348`) awaits promotion. |
| Q-P4-5 | The CTC Office keeps its own elapsed time (`StubCtcOffice._elapsed_s`) and does not read the step's simulation time. A refused tick puts its schedule one tick behind the harness's time, for good. | Landis | Take the time of day from the step's `sim_time_s` (D017). A model change; the process already has the time. **Done:** Kevin Schillinger said "use the harness clock" on 2026-10-21; in `4cc873b`. |
| Q-P4-6 | The test UI and `ctc_host._suggestions` key suggestions by train. The test UI now names the next block's rows `next_...`; the CTC window shows the train's own block. | Landis | Accept, or key both by train and block. **Decided:** Kevin Schillinger said "do not make any changes to uis" on 2026-10-21. No further UI changes; the naming stays as it is. |
| Q-P4-7 | Ticket sales: the Track Model sells with probability 0.02 per station per tick, so a station sells about 12 tickets a simulated minute. Is that the intended rate? | Track Model owner | Unrelated to the harness; flag only. **Open:** Kevin Schillinger said "add this to open questions" on 2026-10-21. |
| Q-P4-8 | The old detector falsely latched an engine failure at steady 5 m/s on Green 93, blocking the full round trip; `ReturnToYardTest` exposed it on 2026-10-21. | Train Controller owners (unassigned) | **Resolved by `460579b`:** the complete Green round trip and retirement at 57 pass with the detector enabled. Kevin accepted the extra steady-fall criterion as built on 2026-10-21 (design R91); known limits and fresh targeted verification are in section 6. |

At the original Phase 4 handover, no truth proposal was filed: nothing in that phase
came from a new decision or a direct statement. The behaviours above follow D005, D017, D022, D025, R46, R49, R51 and R52.
`truth/_inbox/claude/quirky-fermi-sickg4/` then held the 16 proposals from earlier in
the session, awaiting promotion by a person.

On 2026-10-21 one proposal was filed for the Q-P4-4 decision:
`20261021-1445-lower-limit-ahead-train-controller-slows.md`, for
`arbitration/lower-limit-ahead.md` (`66aa348`). That brought the inbox to 17 proposals.
Later, `91e8c0a` added `20261021-1536-engine-failure-detection.md`, targeting
`arbitration/engine-failure-detection.md`, from Kevin's three detector rules of
2026-10-21. It leaves exact constants and recoverable-sag shape unspecified and does
not record the later acceptance of the extra steady-fall criterion. That brought the
inbox to 18 proposals. Kevin's later direct decisions of 2026-10-21 are recorded in
[20261021-1220-engine-failure-steady-fall-accepted.md](../truth/_inbox/claude/quirky-fermi-sickg4/20261021-1220-engine-failure-steady-fall-accepted.md)
(target `truth/arbitration/engine-failure-detection.md`) and
[20261021-1220-harness-stubs-only-auto-run.md](../truth/_inbox/claude/quirky-fermi-sickg4/20261021-1220-harness-stubs-only-auto-run.md)
(target `truth/decisions/harness-stubs-only-auto-run.md`). The inbox now holds 20
proposals awaiting human review and promotion; earlier inbox files are unchanged.

Kevin also directly said "Keep automatic Run for --stubs-only" on 2026-10-21
(design R92): the stubs-only window exception is accepted and requires no
`--auto-run`. A real window run still waits for the dispatcher unless `--auto-run`
is given. No runtime code changed for either acceptance.

#### 5. What is left

1. **Documents.** Done: `documents/system-integration-design.md` v0.11 has §5.5
   "Phase 4 as built", the Phase 4 questions in §1.5, and the gaps and Appendix A
   updated; `common/harness/README.md` describes Phase 4, the fault fixes and the frozen
   build; `documents/integration-handover.md#phase-3` marks Q13 and Q14 resolved and
   Q15 fixed.
2. **Frozen build** (G-RUN-2). Done (section 2). Left: a Windows build.
3. **The CTC Office window at 10x by eye**: the measurement ran offscreen. Watch the map
   and tables with a real display; raise `WINDOW_REFRESH_MS` if replies lag.
4. **Phase 5**: the Track Controller HW's reports join the CTC Office's input through
   `merge_ctc_inputs` once its process returns `ctc_reports` in the SW variant's form.
5. **Run in window mode** (Q-P4-1): done in `68fcfa7`.
6. **The round trip** (Q-P4-8): unblocked by `460579b`. Kevin accepted the extra
   steady-fall detector criterion as built on 2026-10-21 (design R91); the two known
   limits remain for review (section 6).
7. **The Track Controller owners' decisions** on the starter's switch rule (Phase 3
   Q7; `TrackCtrlSW/INTEGRATION_DISCREPANCIES.md` E7), for Harry Tye and Landis.

#### 6. Since Phase 4 (2026-10-21)

Kevin Schillinger's answers of 2026-10-21, and the work on them since `a55b8b9`:

| Commit | What |
|---|---|
| `0305d05` | Q-P4-4. A Train Controller test under the harness (`Train-Ctrl_HW/tests/test_harness_driven.py`): a train entering a block whose commanded speed is below its own applies the service brake and cuts power on the first tick, and holds it until it is under the new speed, with no emergency brake. No code changed. |
| `66aa348` | Q-P4-4. The proposal `arbitration/lower-limit-ahead`, awaiting promotion. |
| `4cc873b` | Q-P4-3 (the CTC side) and Q-P4-5. The CTC Office's "return to yard" action, with one button, Return to yard, in the Selected train panel's Manual-mode row. It orders a manual train on the track to its line's yard entry block (Green 57, Red 9), through dispatch, and the existing path retires it once it has stopped there with authority 0. `CtcOffice.step` takes the step's `sim_time_s`, so a refused or missed tick no longer leaves its schedule behind. 15 new tests. |
| `234c353` | Phase 3 Q7. The starter program sets each switch for the train coming to its points. Two new PLC inputs, `SUG_n` and `REV_s`; existing programs are unaffected, and the vital layer is unchanged. Tests: `test_starter_switches.py` (18), and the harness's `ReturnToYardTest` (5, about 140 s, with `TRACK_OVERFLOW_ROUND_TRIP=1`), which initially stopped at Green 93 (Q-P4-8), before `460579b` unblocked it. |
| this update | `test_harness_window.py`: system mode runs for 8 s instead of 2. Seven real modules take about 2 s to be ready, so about one run in three stopped before `ALL_READY`. The `TIME_SLIPPED` in the short runs was logged at shutdown, as the pacer dropped the ticks it still owed, not at startup. |
| `68fcfa7` | Q-P4-1 (R83). A window run waits for the dispatcher's Run in the CTC Office's window; headless and `--stubs-only` runs press Run by themselves, and the new harness option `--auto-run` does in a window run, for tests and demonstrations. `AutoRunTest` (5 tests) checks the CTC Office's arguments. Ticks owed at shutdown are no longer logged as `TIME_SLIPPED` (`StopWithTicksOwedTest`). Harness tests: 156 passed, 5 skipped. |

Historical tests before `460579b`, on 2026-10-21, scratch venv (Python 3.13,
PySide6 6.11.2), offscreen:

| Suite | Result |
|---|---|
| `python -m pytest -q common/harness/tests` | 150 passed, 5 skipped (`ReturnToYardTest`), 495 subtests (65 s) |
| `CTC-Office`: `python -m unittest discover tests` | 259 OK |
| `TrackCtrlSW`: `python -m unittest discover -s tests` | 213 OK |
| `Train-Ctrl_HW/tests` | 12 |

##### Round trip unblocked (`460579b`)

Q-P4-8 and design gap G-NEW-6 are resolved as implementation defects: a Green train
completes the full round trip and is retired at 57 with the engine detector enabled.
The detector never latches a new engine failure within 0.05 m/s of target. Otherwise
it requires a steady fall of more than 0.05 m/s over 6 s of simulation time, with power
commanded above zero and no service or emergency brake commanded or reported
throughout. It compares half-second speed means, each within 10% of the total fall of
the straight line from the first to the last.

That extra straight-line check avoids latching on the recoverable Green 7 grade sag;
Kevin Schillinger directly accepted the steady-fall check as built on 2026-10-21
(design R91), including the half-second means and 10% straight-line criterion. See
`Train-Ctrl_HW/OPEN_ISSUES.md` #26 and the new accepted-check proposal
`truth/_inbox/claude/quirky-fermi-sickg4/20261021-1220-engine-failure-steady-fall-accepted.md`;
the earlier `20261021-1536-engine-failure-detection.md` remains unchanged.
The two known limits remain: a train at a stand with a dead engine is not flagged,
and a heavily loaded train that cannot hold speed on Green 7's 5 % grade is flagged.

Fresh targeted verification on 2026-10-21 was independently rerun by the orchestrator
with Python 3.14.4, PySide6 6.11.2 and `QT_QPA_PLATFORM=offscreen`: 258 passed and 66
subtests across CTC, Track Controller SW, engine/harness-drive, harness edges/faults/
system and the opt-in round trip. `ReturnToYardTest` passed five of five in 38.95 s,
with `TRACK_OVERFLOW_ROUND_TRIP=1`; the earlier environment took about 140 s. This is
not a whole-suite rerun or a new timing-budget measurement. Exact check scope is in
`documents/integration-summary.md`. The one-train result does not settle the starter's
follower, two-way-zone or vital-lock questions for Harry Tye and Landis.

## Phase 5

Source: archive/handover/integration-handover-phase-5.md, archive/handover/phase-5-prompt.md, archive/handover/phase-5-fixes-prompt.md

<a id="phase-5-handover"></a>

Source: archive/handover/integration-handover-phase-5.md

### Integration handover: Phase 5 software and simulated Pis

Written 2026-10-21; corrected 2026-10-22 on `claude/quirky-fermi-sickg4`, continuing the Phase 4
handover. Kevin authorized steps 1–9 and 13; no functional Pi was available.
The authoritative session prompt was attached by Kevin; the requested
`documents/phase-5 prompt.md` was absent at discovery. The older
`integration-handover.md#next-session-prompt` is not this session's Phase 5 scope.

#### 1. As built and verification boundary

Kevin authorized the software work in the attached Phase 5 session prompt,
with no functional Pis available. Software steps 1–9 and documentation
step 13 are complete against explicit simulated Pis. Real hardware steps
10–12 have not started. R93–R107 preserve the decisions. The two
source merges are `8407baf` (PR #43 source branch, GitHub PR unchanged) and
`2335197` (Braden's WP2 design). `f27ba4e` repairs the Green sample cuts,
adds Red integration test databases/PLCs and aligns the Red yard readers.
`cb8a326`/`d4db358` supply HW mappings, mixed-line routing and deferred replies.

**Red topology and safety.** The three test databases cover 76 blocks exactly
once: Red-1 has 1–24/73–76, Red-2 has 25–45/67–72, and Red-3 has 46–66.
9 and 75 share Red-1. Files say they are integration test copies, not
Braden's, for him to replace or approve. All rows include `next_blocks`.
Kevin superseded K2's data edit on 2026-10-22: "the track is a given data
point and can not be modified". `5d51051` restores `TrackModel/red_line.json`
byte for byte to before `f27ba4e` (SHA-256
`42afbb5505d4cb16e9efb8a3d995409973cd53fdafed4104be997a52c123ca33`).
The integration territory copy preserves the same course rows. The readers
interpret the yard at section-C block 9 and remove the stale yard adjacency
at 75. Assumption for the Track Model owner and Braden: point 9, NORMAL to
8, REVERSE to yard, fixed side 10 and light on 10. A yard release trails
through 9 toward 10. The original `75-yard` text remains unchanged.
HW territory,
Track Model, harness devices and SW topology readers agree. No SW vital
logic changed. Kevin subsequently confirmed the no-vital policy covers SW
too; its existing vital implementation is a deferred owner follow-up.

PR #43 has dual PLC channels and five-bit speed input/output, but no
read-only generated vital PLC block. The Red programs contain speed caps,
separation, closures, switch correspondence/occupied locking, signals and
crossings. Switches remain NORMAL at rest. Crossings 11/47 activate for own
or either-neighbor occupancy. Read-only `OCC_n` inputs extend across declared
neighbors without duplicating output ownership. The full Red occupied set
must reach the mapping; missing set membership has the existing meaning
clear, and a disconnected harness module stops clock advancement. The WP2
planned generated vital block remains for Harry and Braden to confirm;
K3b takes precedence for this implementation.

**Mixed-line run.** In the seven-core in-process scenario, R1 is released at
9 and traverses 9–16, with each module receiving the train one tick apart.
There is no emergency brake or signal-pickup latch, and Green G1 continues
under its SW controller. An onward order is issued immediately after the
Red doors open: first open tick 657, close tick 1107, exactly 45.0 s later.
Red return is not complete: the return request is accepted after the dwell,
R1 continues to 66 and is held by the NORMAL-only route at switch 52.
After 600 simulated seconds it has not retired at 9; no train-left-track,
removal, emergency-brake or pickup-failure event occurs. The return
diagnosis is covered by
`CTC-Office/tests/test_red_return.py`: arriving at 16 from 15, the route
continues 16 → 17 … 66 → 52 … 9. The shorter 16 → 15 … 9 path reverses
at 16, which truth `arbitration/no-automatic-reversal.md` forbids the CTC
Office to do automatically. CTC two-way zones cover the outbound/return
conflict; they do not command a reversal or align a switch. At 52 the
return leg from 66 requires REVERSE; outbound toward 53 requires NORMAL.
A correct return therefore needs Braden's real switch-routing programs,
or a separate dispatcher-controlled reversal decision. Kevin said "wait
for real" for the Red PLCs, so the test programs remain unchanged and
this return remains open.

**Pi link implementation and verification boundary.** `common/hw_link/`
contains a Qt-free Pi agent, strict newline framing and HELLO/ACTION/ACK/VIEW,
remote adapters, event-driven QSerialPort, explicit local QProcess agents
and Linux pty transports. The host's reply is deferred until the Pi answers.
USB discovery uses the assigned serial plus VID/PID, with HELLO module/version
validation and no production fallback. Agents run no clock. The current
recovery code and tests exercise reply caching, durable journal reconstruction,
loads, pending STEP replay, reconnect logging and gain replay policy.

The durable journal stores full accepted requests and replies per session;
the session cache/history grows with the run. Cold restart reconstructs the
core from that history, so replay cost grows too. The earlier in-process
core timings below
exclude disk synchronization, serial transit and replay. The October 22
process measurements include the existing durable journals and fsync.
A real Pi power-loss
and long-session journal test remains part of later hardware acceptance.
The relay implements the running-loss/paused-loss gain replay policy. Kevin
subsequently approved authoritative CLOCK_STATE metadata on the harness-to-HW
host channel (R107). Commit `9325523` implements that explicit protocol/core exception. The
orchestrator independently reran 34 focused clock/protocol/link/channel
checks with 22 subtests and the full Pi suite: 31 passed at `baed0cd`.
CLOCK_STATE has a strict schema and a pause notification never runs STEP.
Gain replay uses the current armed train roster, including rapid retirement/
ID reuse: running-loss replay is distinct from paused-loss non-application.

**Simulated cost groundwork (K9).** One 1,107-tick mixed run measured module
step plus wire encoding/compact JSON round-trip, without serial or windows:

| Module | Mean / p95 / maximum (ms) | Mean / maximum output bytes per tick |
| --- | --- | --- |
| Track Controller HW | 1.3453 / 1.3828 / 1.5307 | 12,410.48 / 12,428 |
| Train Controller HW | 0.02863 / 0.03258 / 0.04961 | 219.80 / 241 |

The two maximum outputs total 12,669 bytes/tick, about 1.27 MB/s at 100
ticks/second, before inputs, framing, VIEW traffic, journaling and recovery.
This sizes the workload; it establishes no actual USB latency or Pi 10x
feasibility result. G-CLK-6 remains open for the USB and Windows measurements.

#### 2. Original October 21 software verification

 The HW baseline after merges
was 73 passed/48,074 subtests and one known missing-`next_blocks` failure;
after the repair it is 80 passed/50,506 subtests. The orchestrator independently
reran that full HW suite and 14 mapping/mixed-loop/deferred-reply tests.
The delegated post-default harness+utils run reports 252 passed, 5 skipped
and 540 subtests in 99.69 s (harness 166 passed/5 skipped; utils 86 passed).
The broad module suites report CTC Office 259/284 subtests; Track Controller SW 213/16;
Track Model 309; Train Controller 23/18; Train Model 879 passed/13 skipped.
The Train Controller `main.py --check` exits zero, with zero QML warnings and
zero behaviour problems. The post-default opt-in Green round trip passes all five checks in 40.56 s.
The final independent slices below include the real-process Pi acceptance.

**Host/default acceptance.** The seven-real-process tests report
three passing scenarios: clean run, injected disconnect and injected reboot.
They assert Green/Red routes, seven zero exits and empty stderr. Journal
evidence records each STEP once, the repeated pending tick is served from
cache, and the harness logs REPLY_LATE followed by LATE_REPLY_RECEIVED.
The orchestrator independently checked these acceptance slices; overlapping
checks are not summed into a new suite total:

| Independent rerun | Result |
| --- | --- |
| Final default-tree faults, launcher arguments and all-seven-process clean/drop/reboot | 27 passed, 7 subtests, 33.42 s; strict empty stderr |
| Full Pi protocol/transport/recovery/window suite | 31 passed, 7.76 s |
| CLOCK_STATE schema, initial/change state, link and Pi channel | 34 passed, 22 subtests, 4.06 s |
| Full Track Controller HW | 80 passed, 50,506 subtests, 4.61 s |
| Mixed route, mappings and deferred replies | 14 passed, 4.62 s |


Kevin approved the concrete CLOCK_STATE exception to the otherwise unchanged
harness protocol/core. It supplies authoritative initial/change clock metadata
to HW hosts; the relay latches it at loss before late-reply timeout pauses the
clock. K11 and the production-default patch are now authorized. CLOCK_STATE is
implemented in `9325523`, and the final gain-cache/armed-roster behavior
is verified in `baed0cd`, including rapid train ID reuse. Both HW variants
are now real modules by default. `--test-pi process` or `--test-pi pty`
explicitly selects development agents; `--stubs-only` remains seven stubs.
Production hosts wait for their USB identities with no fallback. The final
post-default broad regression and Green round trip pass as recorded above.

**Static checks at the original October 21 checkpoint.** The original
claim that all 15 Pi Python files passed mypy was incorrect: the October
22 independent check found five errors (transport at 71/194/199, relay at
28, host at 104), including a real dict-versus-Mapping callback mismatch.
The correction and current verification are recorded below. The original
nine-file harness type check had one preexisting
`common/harness/app.py:106` Qt application argument mismatch; the other
eight checked files are clean. That unrelated UI-facing annotation was not
changed, and this is not a claim that all repository type checks are green.

**Proposals and deferred work.** Commit `17beefc` files five new full proposals
for K2, K5, K6, K7 and K11. Two further full proposals record the confirmed both-variant K3b policy
and approved CLOCK_STATE exception. This branch's inbox has 27 proposals,
plus four
owner-source proposals brought in under PR #43's original branch directory.
All await human promotion. On October 22, Kevin authorized amendments to
D028, D031 and the both-variant PLC-only proposal (`4b9536b`). D031 and
PLC-only provenance now quote his "yes" of 2026-10-22. The two D019 proposals
remain in explicit conflict, with Harry Tye as resolution owner and Braden
responsible for the HW interpretation; Braden's proposal is untouched.
D028 records the immutable course data decision without turning switch-leg
assumptions into normative facts. No proposal was deleted. Pi owner
setup is documented in `documents/pi-owner-setup.md`, untested on hardware.
Steps 10 (USB measurements), 11 (owner Pi provisioning) and 12 (packaging/
Windows builder/separate installs) have not started.


#### 3. Kevin's decisions of 2026-10-21

Kevin authorized steps 1–9 and 13 in the attached session prompt. K4 includes
Braden's answers relayed by Kevin. Quotes preserve their wording. These
implementation rulings do not promote proposals to `truth`.

| # | Source | Kevin's words | Effect |
| --- | --- | --- | --- |
| R93 | K1: Go and order | Steps 1–9 and 13 now; "no hardware is functional yet so that cant be tested" | Build against simulated Pis; steps 10–12 remain out of scope. |
| R94 | K2: Red yard (Phase 3 Q5) | "block 9 physically connects to the yard via a switch … note that block 9 is in section c" | Kevin confirmed on 2026-10-22: "the track is a given data point and can not be modified". Kevin established the physical yard connection at section-C block 9. Readers interpret the stale adjacency while preserving the given bytes; that interpretation and detailed switch legs remain owner assumptions. The earlier source-file edit was an implementation choice, not Kevin's instruction. |
| R95 | K3: PR #43 | "merge into this branch not devlopment leave the pr unmerged" | Merge the source into this branch with a merge commit. Do not merge/close/comment on the GitHub PR. |
| R96 | K3b: Vital layer | "the vital layer has been removed. everything is done by the plc code." | The no-vital policy covers both HW and SW, explicitly confirmed by Kevin: "yes", 2026-10-22. All safety belongs in PLC programs. Existing SW vital implementation is left unchanged under the original implementation scope, and is an owner follow-up. |
| R97 | K4: Red databases/programs, Braden relayed by Kevin | "use test only copies"; "it should be divided in any way that work, maybe 3 waysides. That's fine to keep 9 and 75 in the same wayside."; switches "yes"; crossings "Yes"; "Check the wp2/ branch that braden made. Many updates are found there as well." | Use about three integration test waysides, all 76 blocks once, 9/75 together. NORMAL starters, crossings 11/47 active for own/either-neighbor occupancy; take safety/speed-cap design from WP2. |
| R98 | K4b: WP2 design | The wp2/ branch has "many updates" | Merge `origin/wp2/TrackCtrl-HW-design` (f590f41) separately. Follow Braden's core-on-Pi/host-window split unless a ruling conflicts. Dual channels and five-bit speed exist in PR #43; the generated read-only vital PLC block does not. K3b puts safety in test programs; Harry confirms the planned vital block. |
| R99 | K5: Pis and USB identity | "Pi 5 set up by module owners. assign the both usb ident strigns" | Assign manufacturer/product/serial/VID:PID per module; owners provision the Pis. Write setup instructions without hardware execution. |
| R100 | K6: Pi-link additions | "accept" | Host-to-Pi HELLO (protocol/module/version/hash/session), ACTION/ACK before the next STEP, VIEW at most every 100–200 ms; harness protocol unchanged. |
| R101 | K7: Unplug or reboot recovery | "approved" | Hold the reply; reconnect by identity, redo HELLO, replay loads, re-send pending STEP, log stages. Pi caches `(id,tick)` and never advances that STEP twice. |
| R102 | K8: Pi missing at launch | "the whole clock should wait this will never happen" | No fallback. Missing Pi holds the clock; simulated agents require explicit development/test selection. |
| R103 | K9: Pi capacity at 10x | "agreed test when implemented" | Hardware USB/10x measurement is step 10 later. Record simulated output bytes/core time as groundwork only. |
| R104 | K10: Windows builder/separate installs | "kick this down the road" | Deferred; no Windows builder, separate-installer or packaging claim. |
| R105 | K11: Gains after reboot | "they should never loose connection mid run but add logic to check if connections are lost while the clock as running and if they are lost while the clock is running then the gains should be resent" | Re-send engineer gains only after a loss while running; no automatic gain application after a paused loss (D024). Log both. Kevin later explicitly approved the CLOCK_STATE exception (R107); implementation and integrated recovery checks follow that approval. |
| R106 | K12: Window Python | "any ui changes require permission" | No additional QML or Python-behind-window changes without permission. Use adapters through existing controller/fleet constructor parameters. K3 authorizes the existing owner-authored UI changes in the merge itself. |
| R107 | K11 clock metadata follow-up | Kevin explicitly approved the prepared CLOCK_STATE exception: "yes", 2026-10-22. | Add authoritative initial/change clock metadata on the harness-to-HW-host channels. Latch the state at Pi loss before timeout pause; verify running-loss gain replay and paused-loss non-application. |

#### 4. Open questions and owner review

| Item | Owner | State / next action |
| --- | --- | --- |
| Red-9 NORMAL leg and leftover `75-yard` text | Track Model owner, Braden | Physical connection to section C block 9 is settled. Point 9/NORMAL to 8/REVERSE yard/fixed side 10/light on 10 is an explicit implementation assumption; the course file and original switch text are preserved. |
| Red test copies | Braden | Replace or approve the three exact-cut databases and PLCs. |
| WP2 generated vital block and variant PLC differences | Braden, Harry Tye | Dual channel exists; generated vital PLC does not. HW K3b puts safety in test programs. |
| SW implementation of confirmed K3b policy | SW owner, Harry Tye | Policy scope is confirmed for both variants. Existing SW vital implementation remains under the original session scope; remove/migrate it in a separate owner follow-up. |
| Cross-wayside occupancy | Braden, Harry Tye | Read-only neighbor OCC is exposed; missing occupied membership still means clear. Review the extension and full-line mapping assumptions. |
| Red return and turnback | Braden, Track Model owner, Landis | Return from 16 follows 17 … 66 → 52 … 9 and needs REVERSE at 52; outgoing 52 → 53 needs NORMAL. Short 16 → 15 return is an automatic reversal forbidden by truth. Wait for Braden's real programs or an explicit dispatcher reversal decision. |
| K11 host clock-state path | Integration | CLOCK_STATE exception explicitly approved (R107), implemented in `9325523`; full Pi suite (31) and focused clock/channel checks (34) pass. Running/paused replay policy and rapid train ID reuse are covered. |
| USB/power/10x/journal persistence | Module owners, Kevin | Actual Pi tests have not started. Final simulated 10x reaches 9.69x headless / 9.42x offscreen window; reliable 10x remains open. Journals grow through a session and cold replay cost grows with history. |
| Earlier owner questions | Respective owners | All open questions in the earlier integration summary remain unless explicitly resolved here, including ticket rate, light-ahead B1, heaters and Green starter/follower decisions. |

#### 5. Commit checkpoints

| Commit | Change |
| --- | --- |
| `8407baf` | Merge PR #43 source (30 changed paths, +1,690/−840). GitHub PR remains unmerged. |
| `2335197` | Merge WP2 design (32 paths, +2,150). |
| `cb8a326` | HW boundary mappings, mixed-line routing, deferred replies and Red loop. |
| `f27ba4e` | Green repair, Red test databases/PLC, four reader agreement and neighbor occupancy (18 paths, +2,412/−62). |
| `17beefc` | Five new full-entry truth proposals (5 paths, +141). |
| `d4db358` | Typed mapping result and core API documentation. |
| `daaa3e7` | Pi agent, transports, host relay and remote adapters; focused protocol/recovery/window tests. |
| `78c470c` | Compound window action ordering ahead of STEP and raw-tty reconnect verification. |
| `9325523` | Approved CLOCK_STATE metadata and initial/change notification to HW hosts. |
| `8d15a69`, `c39a070` | Pi handshake/session and callback lifecycle hardening; seven-process system coverage. |
| `baed0cd` | Gain replay/cache follows current armed roster, including rapid retired-ID reuse. |
| `05369a5` | Stop fault-test fake-peer timers before socket teardown; no product or assertion relaxation. |
| `5d51051` | Preserve course Red bytes; align all yard readers and CTC metadata; test switch-dependent return without reversal or PLC routing. |
| `4b9536b` | Owner changelogs and the three authorized proposal corrections. |
| `6797a3a` | Explicit Pi measurement transport, startup discovery events, typed callbacks and approved constructor injection. |
| `02c2d7a` | Clean Phase 5 test formatting. |
| `c9498e4` | Bound periodic Pi VIEW traffic to the approved 200 ms cadence. |
| `1013fb2` | Wrap the approved state-factory expression to satisfy production flake8. |
| `f465c99` | Both HW variants real by default; explicit process/pty test agents; unchanged stubs-only mode. |

#### 6. October 22 correction and revalidation

Kevin approved the exact `TrackCtrlHw/ui/app.py` constructor change:
"Approve this exact constructor change". `6797a3a` adds the optional
keyword-only `state_factory: Callable[[], TrackControllerState] | None`
and constructs the existing state with `RemoteTrackController` in place
of the local core. The window's state is established before QML binding;
the host no longer swaps it after construction. No QML changed. Kevin's
SW-vital-layer answer was "Keep it open for separate follow-up".

`measure --system --test-pi process|pty` explicitly passes the chosen test
transport to both HW modules; omission keeps waiting for real Pis (K8).
System measurements load the Red test starters. Startup events name each
HW module and sought K5 identity, immediately and every five seconds,
including zero/multiple matching ports. The harness forwards these events
before READY while retaining its readiness barrier.

**Current static checks.** The orchestrator independently reran mypy
with `--explicit-package-bases --disallow-untyped-defs
--follow-imports=silent --ignore-missing-imports` on these 16 production
files: `common/hw_link/*.py`, harness `core.py`, `supervisor.py`,
`measure.py`, `track_devices.py`, and utils `module_link.py`, `harness_protocol.py`: success.
This is an explicit production-file scope. Checking the whole hw_link
directory including tests with the same no-untyped-defs rule reports
61 missing-annotation errors; test typing is not claimed clean.
The existing harness `app.py` mismatch is outside the changed-file check.

Production flake8 and the four Phase 5 harness test files pass `flake8 -j1`
with `--extend-ignore=N815` for Qt signal names in the orchestrator's rerun; `02c2d7a` cleans test E501/E402/N802 formatting
without changing assertions. The Red reader/data agent separately checked
all its changed Python files with `flake8 -j1`: clean.

**Current regression evidence.** The orchestrator independently reran all
Pi-link tests, the new startup diagnostics, and the three real-process
G1/R1 clean/disconnect/reboot scenarios: **44 passed in 34.64 s**.
The module agent ran the full suites separately, in sequence:

| Module | Result |
| --- | --- |
| Track Controller HW | 80 passed, 50,506 subtests, 4.15 s |
| Track Controller SW | 213 passed, 16 subtests, 10.49 s |
| Track Model | 310 passed, 2.48 s |
| CTC Office | 261 passed, 284 subtests, 21.76 s |

The orchestrator also independently reran the remaining broad suites:

| Area | Result |
| --- | --- |
| Harness + utils | 260 passed, 5 skipped, 540 subtests, 96.01 s |
| Train Controller SW | 24 passed, 0.05 s |
| Train Controller HW | 23 passed, 18 subtests, 0.16 s |
| Train Model | 879 passed, 13 skipped, 40.06 s |
| Opt-in Green round trip | 5 passed, 37.04 s |

The supported `Train-Ctrl_HW/main.py --check` reports zero QML warnings
and zero behaviour problems. The SW `TrainController/main.py` does not
support this self-check flag.

The HW suite's first sandbox attempt had five socket-startup failures
(`Operation not permitted`), then passed in full with local IPC available.
The orchestrator independently confirmed the pre-`f27ba4e` source hash and
reran focused Red agreement/retirement/route checks (HW six tests with
2,432 subtests, Track Model 20, CTC two). No automatic reversal or
test-program Red switch routing was added.

**End-to-end profile.** Instrumented process runs reached only 4.62–5.04x,
with 19.37–21.12 ms mean round trip and 200–201 slipped ticks in about
five seconds. Profiling itself materially changes the workload: the
earlier unprofiled headless measurement reached 10.00x; the final
200 ms VIEW-cadence run below did not reproduce that result. These inclusive per-call
timings come from the same instrumented host/agent run (Track host
`process-1767570.pstats`, Track agent `process-1767610.pstats`, Train agent
`process-1767602.pstats` in `/tmp/recoveryprofile/`). They locate work; they
are not additive critical-path latencies:

| Process / operation | Profiled mean per call |
| --- | --- |
| Track HW agent STEP (254 calls) | 8.101 ms |
| Track HW agent VIEW (55 calls) | 3.758 ms |
| Track HW journal record, including fsync | 0.18385 ms |
| Track HW fsync syscall alone | 0.001924 ms |
| Track HW JSON encode / decode | 0.29475 / 0.33089 ms |
| Track HW pipe write | 0.016652 ms |
| Train HW agent STEP | 0.05447 ms |
| Train HW journal record, including fsync | 0.08703 ms |
| Train HW fsync syscall alone | 0.001610 ms |
| Train HW JSON encode / decode | 0.04057 / 0.05909 ms |
| Host VIEW handling (same instrumented agent run) | 19.980 ms |
| Host remote snapshot unpack / state refresh (included in VIEW) | 11.053 / 5.961 ms |

The Track HW output remains roughly 12 KB per tick. Blocking pipe reads
include idle wait for work and cannot be called transport latency. The
deferred reply remains required to wait for the simulated agent's result.
Journal synchronization is a small measured component on this filesystem;
K7 full-request/reply journaling, fsync and replay guarantees remain intact.
`c9498e4` reduces periodic VIEW traffic from 100 ms to 200 ms, within K6's
approved 100–200 ms range. STEP replies and ACTION acknowledgments keep
their ordering and cadence; a boundary regression checks the VIEW period.
The snapshot unpack/refresh cost motivates this change without altering
the window's refresh implementation or reducing durability.
These results establish neither real USB buffering cost nor Pi performance.

**Final process measurement, 200 ms VIEW cadence.** Four sequential runs,
15 real seconds each, using `--system --test-pi process`, project Python,
and `QT_QPA_PLATFORM=offscreen`. "Headless" means the harness frontend is
hidden; `--system` still constructs module windows in both modes. "Window"
also constructs the harness window offscreen. This is not a visual
inspection or a visible-desktop responsiveness check.
The default measurement dispatches G1; the separate full-system acceptance
scenarios exercise G1 and R1 together.

| Front end | Requested | Completed / due | Achieved | Mean / median / p95 / p99 / max round trip (ms) | Startup | Harness CPU |
| --- | --- | --- | --- | --- | --- | --- |
| Headless | 1x | 151 / 150 | 1.01x | 20.74 / 19.45 / 31.69 / 35.27 / 38.21 | 0.57 s | 6% |
| Window, offscreen | 1x | 150 / 150 | 1.00x | 20.54 / 19.25 / 28.23 / 35.76 / 41.12 | 0.51 s | 9% |
| Headless | 10x | 1,455 / 1,502 | 9.69x | 10.00 / 8.41 / 21.83 / 29.02 / 62.28 | 0.49 s | 27% |
| Window, offscreen | 10x | 1,414 / 1,502 | 9.42x | 10.27 / 8.57 / 23.20 / 30.26 / 73.09 | 0.51 s | 29% |

Every final run reports zero explicit dropped-backlog (slip) events and
zero late replies. The headless 10x run completed 47 fewer ticks than due;
the offscreen window run completed 88 fewer. Those unfinished ticks are
not reported as dropped-backlog events. Zero slip events therefore does
not imply all due ticks completed. Both final 10x runs fail the
measurement's 99% completion criterion. Before the cadence change, a
separate unprofiled 100 ms run reached 10.00x headless (8.32 ms mean) and
9.70x with windows (9.24 ms mean). These samples show variability, not a
proven end-to-end speed improvement from the cadence change. VIEW traffic
is reduced; the remaining variation is unresolved.

Phase 4 measured 10.00x with 5.1–5.8 ms mean round trip; the final Phase 5
10x means are 10.00–10.27 ms. Phase 5 adds both HW host/agent paths and
durable journals, so these are different workloads. Reliable simulated
10x remains open. Work stops here with K7 intact: Kevin can accept the
observed rate for simulated demonstrations, authorize a separate focused
optimization/review of snapshot unpack and refresh, or wait for the real
Pi/USB measurements before selecting a performance target. No durability
relaxation is proposed or silently applied.

#### 7. Handoff

The initial 20 current-branch proposals and seven new proposals remain pending,
plus four PR #43 owner proposals under that source branch's inbox directory.
Only humans promote or delete them. No PR was opened or changed. The branch
never changed, and no worktree was created.

Two preexisting untracked files belong to earlier work and are preserved:
`common/harness/tests/adversarial_probe.py` and
`documents/central-harness-adversarial-2026-10-20.md`. They are outside this
session's commits. A clean session-owned diff must not be achieved by deleting
or staging them.

Run with the project virtual environment and `QT_QPA_PLATFORM=offscreen` when
headless. Host process/socket tests require local IPC permissions; sandbox
socket failures are not product regression evidence. This session checked
Python 3.14.4, PySide6 6.11.2 and PyInstaller 6.22.2 against the truth minima
on `kevin-framework`, Ubuntu 26.04.1 LTS, at 17:59 EDT on 2026-10-21.

October 22 correction work used the same toolchain on `kevin-framework`,
Ubuntu 26.04.1 LTS; system time was checked at 01:00 EDT on 2026-10-22.

#### Phase 6 follow-up

The [Phase 6 handover](#phase-6-handover) records Kevin's
subsequent authorization to reuse Green routing in all Red test switches,
the approved shared read-only neighbor closure inputs, the completed Red
return, fresh visible-window measurements and Linux build smoke. It also
records the three failing CTC multi-train acceptance probes. Phase 5's
historical wait for real Red programs is superseded for these test copies;
Braden's review and physical-Pi validation remain open.

<a id="phase-5-prompt"></a>

Source: archive/handover/phase-5-prompt.md

### Prompt: Phase 5, steps 1–9 and 13 (no hardware)

Paste everything below the line into a new Codex session.

---

You are continuing the Track Overflow system integration on branch
`claude/quirky-fermi-sickg4`. Never change branches, and open no pull request unless Kevin
Schillinger (the user) asks for one. This session builds **Phase 5, steps 1–9 and 13** of the
plan below. No Raspberry Pi is working yet, so nothing in this session may depend on real
hardware: steps 10 (USB measurement), 11 (Pi provisioning) and 12 (packaging) are out of
scope.

#### How you work

- **You are the orchestrator.** Delegate every piece of legwork (reading code, editing,
  testing, writing documents) to subagents running **sol 6.1 at medium effort**. You plan,
  write their prompts, review and validate their work (read each commit's
  `git show --stat`, re-run the key tests yourself), and report to Kevin. Say what you
  verified yourself and what you only have from an agent's report.
- **Agents share one working tree.** `AGENTS.md` forbids git worktrees for agents. Give each
  agent a separate set of files, and tell every agent:
  - stage explicit paths only, never `git add -A`, and check `git diff --cached --stat`
    before committing;
  - never touch another agent's uncommitted changes;
  - if `.git/index.lock` exists, wait and retry.
- **Commits and pushes.** End commit messages with the attribution lines your environment
  requires. Put no model identifier in any repository file. Push with
  `git push -u origin claude/quirky-fermi-sickg4`, retrying only on network errors.
- **UI changes need Kevin's permission, every time.** That includes QML and the Python
  behind a window (for example `TrackCtrlHw/ui/state.py` and
  `Train-Ctrl_HW/train_ctrl/backend.py`). Design so that none is needed. If one turns out to
  be unavoidable, stop and ask Kevin, showing the exact change.
- **`AGENTS.md` is binding.** At session start:
  - `git fetch origin truth`, then read `truth/INDEX.md` with `git show`;
  - check the toolchain against `truth/conventions/toolchain.md`;
  - report the date, time, machine and OS;
  - present this branch's inbox (`truth/_inbox/claude/quirky-fermi-sickg4/`), which holds 20
    proposals awaiting promotion.

  Truth is read with `git show` only; never write it into the repository. Write a proposal
  only for a normative fact decided by Kevin or a document, as a full entry in one new file
  per fact. Promotion is human-only.
- **Python:** use a project virtual environment (Python ≥ 3.10, `PySide6>=6.11`, pytest,
  mypy, flake8). Run Qt tests with `QT_QPA_PLATFORM=offscreen`.
- **Write documentation as you go**, matching each file's existing style.

#### Read first

- `AGENTS.md`.
- `documents/integration-summary.md`: everything since Phase 3, the open questions and the
  20 proposals.
- `documents/system-integration-design.md` (v0.14): §1.4 rulings, §4.5 (the process model,
  including the Pis), §5.4–5.5, the §6 gaps and Appendix A.
- `documents/integration-handover.md#phase-4` and `common/harness/README.md`.
- In truth: D005, D017, D021, D022, D024 and D027.
- `TrackCtrlHw/README.md` and its `docs/`.
- In `Train-Ctrl_HW/`: `REQUIREMENTS.md` and `HARNESS_INTEGRATION.md`.

#### State at the start (verified 2026-10-21 at `aa7776c`)

- **Track Controller HW** (`TrackCtrlHw/`, owner Braden; contract shard owner Harry Tye):
  - The core is pure Python with no Qt, and there is no serial, USB or Pi code.
  - The version on this branch is old. Its boundary keys blocks by `(line, section,
    block_id)`, still has `time_s`, `ctc.maintenance_mode` and `track_model.failures`, and its
    reports have no `line`, `ready` or `reason`.
  - It has three Green sample waysides, without `next_blocks`, so
    `tests/test_territory.py::SampleWaysides::test_samples_match_the_course_layout_file`
    fails. There is no Red data.
- **PR #43** (`origin/feature/TrackCtrl-Showcase-Feedback`, open, blocked) is not merged
  here.
- **Train Controller HW:** the same `Train-Ctrl_HW/train_ctrl` code runs Green today as
  `train-controller-sw`. Its fleet core has no Qt. The console (`backend.py`) reads and
  writes the train state directly, in the same process.
- **Harness:** already in place are `merge_ctc_inputs`, the per-line routing tables
  (`TRACK_CONTROLLER_FOR_LINE`, `CONTROLLER_FOR_LINE`), the Red yard exit at 9 and the
  Red switch mapping. Both HW modules still run as stubs. `utils/module_link.py` answers each
  `STEP` synchronously and cannot defer a reply.
- **Red data** (`TrackModel/red_line.json`): 76 blocks, all two-way. The yard is listed as a
  neighbour of block 75 (`75: [74, 76, "yard"]`). The switch text `75-yard` is on block 9's
  row. The readers disagree on what NORMAL means for it. **No Red train has ever run in the
  integrated system.**

#### Kevin's decisions of 2026-10-21

Record each one, in his words, in design §1.4 (next ruling numbers) and in the Phase 5
handover. File one truth proposal for each fact that is normative and new.

| # | Question | Kevin's answer | What it means for this work |
|---|---|---|---|
| K1 | Go and order | Steps 1–9 and 13 now; "no hardware is functional yet so that cant be tested" | Every Pi path runs against a simulated Pi in tests. |
| K2 | Red yard (Phase 3 Q5) | "block 9 physically connects to the yard via a switch … note that block 9 is in section c" | Fix `red_line.json` so the yard joins block 9, section C, through the switch listed on block 9. Remove `"yard"` from block 75's `next_blocks` and add it to block 9's. Assume point 9, normal along the main line, reverse to the yard; record that as an assumption for the Track Model owner and Braden to confirm. The leftover `75` in the switch text also goes to them. All three readers (Track Model, harness `track_devices`, Track Controller HW `territory`) must agree, enforced by a test. File a proposal. |
| K3 | PR #43 | "merge into this branch not devlopment leave the pr unmerged" | `git merge origin/feature/TrackCtrl-Showcase-Feedback` into this branch: a merge commit, never a rebase. Do not merge, close or comment on PR #43. |
| K3b | Vital layer | "the vital layer has been removed. everything is done by the plc code." | The HW variant has no vital layer (PR #43, its D019 proposal). Every safety rule lives in the PLC programs, so the Red programs must carry the speed caps, separation and crossing rules themselves. The SW variant still has a vital layer: do not change it, and ask Kevin whether this decision covers SW too. |
| K4 | The Red databases and programs (Braden's answers, relayed by Kevin 2026-10-21) | Who writes them: "use test only copies". The split: "it should be divided in any way that work, maybe 3 waysides. That's fine to keep 9 and 75 in the same wayside." Switches: leaving them normal for a first version is fine ("yes"). Crossings: "Yes", crossings 11 and 47 drop when either neighbouring block is occupied. Speed caps: "Check the wp2/ branch that braden made. Many updates are found there as well." | Integration writes the Red databases and PLC programs as test-only copies, clearly marked as not Braden's. Use about 3 waysides covering all 76 blocks, with blocks 9 and 75 in the same wayside. Leave switches NORMAL. Drop crossings 11 and 47 when the crossing block or either neighbour is occupied. Take the safety rules, speed caps included, from Braden's design on `origin/wp2/TrackCtrl-HW-design` (see the next row). |
| K4b | Braden's WP2 design | The `wp2/` branch has "many updates" | `origin/wp2/TrackCtrl-HW-design` is one commit, `f590f41` (Braden, 2026-10-20), on history this branch already has: the Track Controller HW software design (`documents/sdd/track_ctrl_hw.md`), `documents/sdd/system_concepts.md`, UML under `documents/uml/track_ctrl_hw/` (architecture, boundary/core/host classes, deployment, sequences sd01–sd07 including the tick and the scan cycle) and design-review slides. It is documents only; its `TrackCtrlHw` code is the old version, older than PR #43. Merge it into this branch as well (a merge commit, never a rebase; leave the branch itself alone). **Follow this design for the Pi split**: core on the Pi (`HwTrackController`, `Wayside`, PLC engine, `PiLinkServer`); host process with the window plus `HarnessEndpoint`, `RemoteTrackController` and `PiSerialLink`; newline JSON over USB serial (D027). Where it and this plan differ, say so and follow Braden's design unless it contradicts a ruling; then ask. It also describes a dual-channel PLC (channels A and B must agree), speed entering the program as five bits `SPD_n_0..4`, and a planned generated read-only vital PLC block, which it marks as a design assumption until Harry Tye confirms it. Check which of these PR #43's code already has. Put the speed caps in PLC code, consistent with K3b and Braden's design (in the generated vital block if PR #43 has one, otherwise in the test programs), and report which. |
| K5 | Pis and USB identity | "Pi 5 set up by module owners. assign the both usb ident strigns" | Raspberry Pi 5, USB device mode on its USB-C port. Assign one identity per module (manufacturer, product, serial number, VID:PID), find each Pi by it, document it, and file a proposal. Suggested: manufacturer `Track Overflow`; product `Track Overflow Track Controller HW` / `Track Overflow Train Controller HW`; serial `TO-TRACK-CTRL-HW-01` / `TO-TRAIN-CTRL-HW-01`; VID:PID `1d6b:0104`, the Linux composite-gadget default. Owners set up the Pis; you write and document the gadget and agent setup without running it on hardware. |
| K6 | Pi-link additions | "accept" | `HELLO` (protocol, module, agent version/hash, session), `ACTION`/`ACK` (window actions applied before the next `STEP`) and `VIEW` (a display snapshot, at most every 100–200 ms), on the host-to-Pi link only. File a proposal as an additive extension of D027. |
| K7 | Unplug or reboot recovery | "approved" | Hold the reply (the harness pauses and names the module after 1 s). Reconnect by USB identity, redo `HELLO`, replay the recorded loads, re-send the pending `STEP`, and log every step. The Pi answers a repeated `STEP` from its cache by (id, tick) and never steps twice. File a proposal. |
| K8 | Pi missing at launch | "the whole clock should wait this will never happen" | No fallback. The clock waits for every module, as now. A simulated Pi exists only for tests and development, chosen explicitly, never automatic. Do not add a production `--hw-sim` path that hides a missing Pi. |
| K9 | A Pi that can't hold 10x | "agreed test when implemented" | Measure once hardware works (step 10, not now). Now, record per-tick bytes and core step time from the simulated runs, to size the risk. |
| K10 | Windows builder; separate installs | "kick this down the road" | Out of scope. Record as deferred. |
| K11 | Gains after a Pi reboot | "they should never loose connection mid run but add logic to check if connections are lost while the clock as running and if they are lost while the clock is running then the gains should be resent" | Detect a lost Pi connection. If it was lost while the clock was running, re-send the engineer's gains when it reconnects. If it was lost while paused, do not auto-apply gains (D024). Log both cases. File a proposal. |
| K12 | Python behind the windows | "any ui changes require permission" | See "How you work". Prefer remote adapters passed in through constructor parameters that already exist (`TrackControllerState(controller=…)`, `ConsoleBackend(fleet=…)`), so no window file changes. |

#### The work, in order (steps 1–9, then 13)

**Architecture (Option A, decided by K6).**
- **Host process.** Each HW module (`--module track-controller-hw`,
  `--module train-controller-hw`) runs a host process. It is an ordinary harness module: it
  shows the window on the host (D021) and relays the harness's messages to its Pi.
- **Pi agent.** The agent on the Pi runs the module's Qt-free core, using the Python
  standard library plus `utils/harness_protocol.py`. It opens `/dev/ttyGS0` raw, echo off,
  and steps once per `STEP`. It never keeps time; the harness owns the clock (D017).
- **Unchanged:** the harness core, the protocol to modules and the other modules.

1. **Merge PR #43, then Braden's WP2 design, into this branch (K3, K4b).** Two merge
   commits, never a rebase; leave both branches and PR #43 untouched.
   - Read `documents/sdd/track_ctrl_hw.md` and the UML before designing steps 4–8.
   - Re-run the Track Controller HW suite.
   - Acceptance: it passes, apart from the known sample-wayside test; reports carry `line`,
     `ready` and `reason`; there is no vital layer.
2. **Fix the known failing test (R78).** Add `next_blocks` to the Green sample waysides, as
   exact cuts of `green_line.json`.
   - Acceptance: the Track Controller HW suite passes in full.
3. **Red data.**
   - Apply K2 to `red_line.json`, and update anything that read the old yard placement.
   - Add Red wayside databases covering all 76 blocks exactly once, with `next_blocks` (R34,
     R78), in about 3 waysides, with blocks 9 and 75 in the same wayside (K4).
   - Add matching Red PLC programs that carry every safety rule (K3b, K4b):
     - switches stay NORMAL;
     - crossings 11 and 47 drop when the crossing block or either neighbour is occupied;
     - separation as the SW starter does it;
     - signals;
     - speed caps.
   - These are integration test copies (K4). Mark them in each file and in the README as
     not Braden's, for him to replace or approve.
   - Acceptance: each file matches `red_line.json` block for block; each loads into the HW
     core; each program compiles with no errors; all three readers agree on every Red
     switch's NORMAL and REVERSE legs.
4. **Harness mappings for the HW Track Controller.** Write pure functions in the harness for
   CTC→HW, Track Model→HW (sections from `BlockNames`), HW→Track Model and HW→CTC. The HW
   module's `time_s` comes from the step's simulation time. Choose the mapping by variant in
   `edges.py`.
   - Acceptance:
     - contract tests feed each mapping into the HW module's own decoder, and from its own
       encoder;
     - `merge_ctc_inputs` joins the Green and Red reports;
     - Red's `WAYSIDES_READY` comes from the HW outputs.
5. **Register the Train Controller HW** (`train-controller-hw` in the module process and in
   `track_overflow.py`). Wire both HW modules behind an option until step 9.
   - Acceptance: Red trains reach only the HW controller, and both controllers' commands are
     merged into the Train Model's inputs.
6. **A Red run in one process, without serial**, following the
   `test_harness_train_loop.py` pattern.
   - Acceptance:
     - the Red waysides become ready;
     - `--dispatch R1:Red:16` releases R1 at 9, and each module takes it a tick apart;
     - R1 runs 9 to 16 with no emergency brake and no pickup-failure latch, and dwells 45 s;
     - G1 on Green alongside is unaffected.
   - Follow-up: Red return to yard and retirement at 9, and whether a train can turn back on
     Red. Report what happens.
   - Record per-tick output bytes and the core step time (K9 groundwork).
7. **The Pi-link protocol and the Pi agent (K6, K7).** Pure functions plus a loop over any
   byte stream.
   - Acceptance: unit tests with chunked and split streams, non-JSON lines (modem `AT`
     probes are skipped and logged), a version mismatch, a repeated `STEP` answered from the
     cache, and `QUIT` resetting the session.
8. **Host relay processes and a simulated Pi.**
   - **Transport:** an abstraction over `QSerialPort`, found by the K5 identity (PySide6
     6.11 ships QtSerialPort, so no pyserial on the host); `QProcess` stdio to a local
     agent; and a Linux pty for the raw-mode path.
   - **Simulated agent:** `--delay-ms`, `--jitter-ms`, `--drop-after N` and
     `--reboot-at-tick N` for fault injection.
   - **`ModuleLink`:** add a deferred-reply mode.
   - **Windows:** remote adapters for both windows, with no UI change (K12).
   - **Recovery:** implement K7, and K11's gain re-send while running.
   - **Tests:** an explicit test-only option selects the simulated Pi (K8).
   - Acceptance:
     - the real-process system test passes with all seven modules real and simulated Pis,
       running G1 and R1;
     - an injected unplug or reboot gives `REPLY_LATE`, then `LATE_REPLY_RECEIVED` after the
       replay, with no double step;
     - gains are re-sent only after a loss while running;
     - window actions behave as they do locally;
     - stderr is empty.
9. **Make both HW variants real modules by default**, finding each Pi by its K5 identity,
   with no fallback (K8).
   - Acceptance: argument tests for every mode; `--stubs-only` unchanged; the default
     harness and module suites green on the simulated Pi in tests.
13. **Documents.**
    - Design §5.6 "Phase 5 as built (steps 1–9)", with K1–K12 as new rulings.
    - A Phase 5 handover in the same form as the Phase 4 one.
    - The harness README.
    - An integration guide for `TrackCtrlHw`.
    - Pi setup instructions for the module owners (USB gadget, systemd unit, the K5
      identity), marked untested on hardware.
    - Truth proposals for K2, K5, K6, K7 and K11, plus K3b if Kevin confirms its scope.
    - Mark steps 10–12 as not started, waiting for working Pis (K9, K10).

#### Questions still open (ask Kevin, don't decide)

- Does "the vital layer has been removed" cover the SW variant too?
- The exact NORMAL leg of the block-9 switch, and the stray `75` in its text: confirm with
  the Track Model owner and Braden.
- Where Braden's WP2 design (K4b) and PR #43's code differ (for example the generated vital
  PLC block, or the dual channels), which one the integration follows. Report what you
  found; Harry Tye confirms the vital block.

Owner questions that are still open are listed in `documents/integration-summary.md`.

#### Before you finish

Run every suite the work touches:
- harness;
- utils;
- CTC Office;
- Track Controller SW;
- Track Controller HW;
- Track Model;
- Train Controller, plus its `main.py --check`;
- Train Model;
- the opt-in Green round trip (`TRACK_OVERFLOW_ROUND_TRIP=1`).

Report the numbers. Leave the tree clean and pushed. Give Kevin a summary of every change,
by area: commits, tests, proposals filed, open questions.

<a id="phase-5-fixes-prompt"></a>

Source: archive/handover/phase-5-fixes-prompt.md

### Prompt: Phase 5 fixes

---

You are continuing the Track Overflow system integration on branch
`claude/quirky-fermi-sickg4`, starting at `1b64bc4`. Never change branches, and open no pull
request unless Kevin Schillinger (the user) asks for one. Phase 5 steps 1–9 and 13 were built
from `documents/integration-handover.md#phase-5-prompt` and are reported in
`documents/integration-handover.md#phase-5-handover`. An independent check on 2026-10-22 found the
problems below. Kevin answered each one; this session fixes them.

#### How you work

- **You are the orchestrator.** Delegate every piece of legwork to subagents running
  **sol 6.1 at medium effort**. You plan, review and validate their work (read each commit's
  `git show --stat`, re-run the key tests yourself), and report to Kevin. Say what you verified
  yourself and what you only have from an agent's report.
- **Agents share one working tree.** `AGENTS.md` forbids worktrees for agents. Give each agent a
  separate set of files, and tell every agent:
  - stage explicit paths only, never `git add -A`, and check `git diff --cached --stat`
    before committing;
  - never touch another agent's uncommitted changes;
  - if `.git/index.lock` exists, wait and retry.
- **Commits and pushes.** End commit messages with the attribution lines your environment
  requires. Put no model identifier in any repository file. Push with
  `git push -u origin claude/quirky-fermi-sickg4`, retrying only on network errors.
- **Any UI change needs Kevin's permission first.** That covers QML and the Python behind a
  window. Ask and show the exact change rather than make it.
- **`AGENTS.md` is binding.** Run its session-start steps (fetch `truth`, read `INDEX.md`, check
  the toolchain, report date/time/machine/OS, present this branch's inbox: 27 proposals).
  Truth is read with `git show` only. Proposals come only from Kevin's decisions or documents,
  and promotion is human-only. **Editing an existing proposal is allowed only where Kevin
  asked**; item 4 below is such a request.
- **Python:** project virtual environment, Python ≥ 3.10, `PySide6>=6.11`, pytest, mypy,
  flake8. Run Qt tests with `QT_QPA_PLATFORM=offscreen`.
- **Write documentation as you go**, matching each file's style.

#### Read first

- `AGENTS.md`.
- `documents/integration-handover.md#phase-5-prompt` (decisions K1–K12).
- `documents/integration-handover.md#phase-5-handover` and design §5.6.
- `common/hw_link/` (`protocol.py`, `agent.py`, `relay.py`, `host.py`, `transport.py`).
- `common/harness/{core.py,measure.py,supervisor.py,edges.py}`.
- `TrackCtrlHw/` README and INTEGRATION, and `TrackCtrlHw/ui/` (read only).
- Braden's design on `origin/wp2/TrackCtrl-HW-design`, already merged here as `2335197`:
  `documents/sdd/track_ctrl_hw.md` (§4 architecture, §5.3 host classes) and
  `documents/uml/track_ctrl_hw/class_host.puml` / `class_core.puml`.

#### Kevin's answers of 2026-10-22, and the work

| # | Problem found | Kevin's answer | Do this |
|---|---|---|---|
| 1 | The harness core and protocol gained a `CLOCK_STATE` message (D031). The no-vital-layer proposal for both variants claimed his approval without quoting him. | "yes" to both: he approves `CLOCK_STATE`, and confirms the no-vital-layer rule covers the SW variant. | Amend those two proposals (`20261021-…` D031 and `track-controller-plc-only-both-variants`) so their provenance quotes Kevin's "yes" of 2026-10-22. Do **not** remove the SW variant's vital layer in this session: ask Kevin whether he wants that done now, and record it as an open item. |
| 2 | `python -m common.harness.measure --system` waits forever: it never passes `--test-pi`, so it waits for Pis that don't exist. The README budget recipe is broken. | "create a fix" | Give `measure.py` an explicit `--test-pi process\|pty` option. Use it for both HW modules, passing it through the way `app.py` does. Fix the README recipe. Add a test that `measure --system --test-pi process` starts and measures. Never fall back silently (K8). |
| 3 | With simulated Pis, a 10x run reaches only about 5x, with 18 slipped ticks and a mean round trip of 17–23 ms. Phase 4 measured about 5 ms. | "investigate" | Profile one tick end to end: harness → host relay → simulated agent → back. Places to look: the deferred reply, the per-transaction fsync of the journal, the `VIEW` snapshots, JSON encoding of the ~12 KB Track Controller HW output, pipe/pty buffering, and the stdio `QProcess` path. Report where the time goes, with numbers. Fix what is clearly overhead, and keep the K7 durability guarantees unless Kevin agrees to relax them. Re-measure 1x, 10x headless and 10x window with simulated Pis, and compare to Phase 4. If 10x cannot be reached without weakening a guarantee, stop and give Kevin the options. |
| 4 | The no-vital-layer proposal for both variants targets `truth/decisions/D019-wayside-runs-only-its-program.md`, the same path as Braden's own D019 proposal in `truth/_inbox/feature/TrackCtrl-Showcase-Feedback/`. | "add that it has a conflict" | Edit that proposal only (Kevin asked): add a `## Conflict` section per `AGENTS.md`, naming both entries, each one's provenance, and an owner to resolve it (Harry Tye, contract owner, with Braden). Also fix its entry key so it matches its filename. Leave Braden's proposal untouched. |
| 5 | mypy reports 5 errors in `common/hw_link`: `transport.py:71,194,199`, `relay.py:28`, `host.py:104`. The `host.py` one is a real type mismatch (`deferred_handler` dict vs Mapping). | "fix" | Fix them properly, with no blanket ignores. Run mypy (`--explicit-package-bases --disallow-untyped-defs --follow-imports=silent --ignore-missing-imports`) on `common/hw_link` and the changed harness and utils files; correct the handover's mypy claim. Clean flake8 on production code; also clear the 55 E501/E402/N802 warnings in the new test files where that matches existing practice. |
| 6 | Owners' code changed: Red-9 special cases in four layout readers (`TrackCtrlSW/track_ctrl/layout.py:440`, `TrackModel/track_model/layout.py:422`, `TrackCtrlHw/track_ctrl_hw/territory.py:187`, `common/harness/track_devices.py:128`). Braden's HW core gained cross-wayside neighbour `OCC_n` inputs, where an occupied block missing from the inputs counts as clear. | "write this to the change log for the respective modules" | Add an entry to each affected module's change log (`TrackCtrlSW`, `TrackModel`, `TrackCtrlHw`, and the harness README's change notes; create a `CHANGELOG.md` where a module has none, in `Train-Ctrl_HW/CHANGELOG.md`'s style). Give what changed, why (the commit and the decision), and the risk: "an occupied block missing from the inputs counts as clear" is a safety note for Braden and Harry. No code change for this item. |
| 7 | The track data itself. | "the track is a given data point and can not be modified" | **This supersedes part of K2.** Phase 5 commit `f27ba4e` edited `TrackModel/red_line.json` (moved `"yard"` from block 75's `next_blocks` to block 9's). Restore `red_line.json` to its course-given content, exactly as before `f27ba4e`. Keep the yard at block 9 (K2: "block 9 physically connects to the yard via a switch … block 9 is in section c") by interpreting the given file in the readers, which already carry Red-9 handling. Make all four readers agree on the unmodified file, and keep the test that enforces it. Re-check the block-9 switch legs: the readers currently take 9 as the point, 10 as NORMAL and the yard as REVERSE, with the light on 8, yet R1 is released toward 10. Make them consistent with a train leaving the yard onto 9, and record the reading as an assumption for the Track Model owner and Braden. Check every user of the yard placement still works: CTC tracking, `YARD_EXIT_BLOCKS`, the Red run. Update the K2 proposal (D028) only if it states that the file is edited: Kevin asked for this change, so record his words of 2026-10-22. |
| 8 | Red return doesn't work: R1, sent back to the yard, stops for good at 66, behind switch 52 (NORMAL), and never retires. | "fix", and "wait for real" for Red switching in the PLC programs | **These pull against each other. Do not make the test PLC programs route Red switches;** Braden's real programs will. Find out why the CTC Office routes R1 from 16 back to 9 by way of 66 rather than another way, and fix the return without switch routing in the test programs, if a correct fix exists elsewhere. Note truth `arbitration/no-automatic-reversal` and the CTC's two-way zones. If the only fix needs switch routing or a reversal the rules forbid, stop and give Kevin the options; don't pick one. |
| 9 | A missing Pi shows only "5 ready" in the log. | "yes" (the harness should name it) | While a HW host is searching for its Pi, log an event naming the module and the K5 identity it is looking for. Log it at start and then at a sensible interval. Log the matching ports found, including the case where more than one matches, which today waits silently. No UI change: events only; the operator window already lists events. Test it. |
| 10 | The Track Controller HW window's state is swapped after construction (`common/hw_link/host.py:58-68,144-148`). | "no Plug in at the core instead: give the window's existing state a RemoteTrackController in place of the local core, if his state class already accepts one, so the window stays untouched. check the wp2 code on bradens branch for refrencee" | Remove the post-construction swap. Plug a `RemoteTrackController` in at the core: build the window's existing state with it in place of the local `HwTrackController`, through a parameter the state class already has (check `TrackCtrlHw/ui/state.py` and the PR #43 code). Follow Braden's design on `origin/wp2/TrackCtrl-HW-design`: `RemoteTrackController`, `PiSerialLink` and `HarnessEndpoint` in `class_host.puml` and SDD §4/§5.3. If the state class has no such parameter, or the window builds its own state, **stop and ask Kevin**: that would be a UI change. Show him the smallest change that would allow it. |

#### Before you finish

Run every suite:
- harness + utils;
- `common/hw_link`;
- Track Controller HW;
- CTC Office;
- Track Controller SW;
- Track Model;
- Train Controller, plus `main.py --check`;
- Train Model;
- the opt-in Green round trip.

Then:
- run a full-system `--test-pi process` run dispatching G1 and R1;
- run the fixed `measure --system --test-pi process` at 1x and 10x, headless and with the window;
- update the Phase 5 handover and design §5.6 (numbers, the item 7 reversal, open items);
- leave the tree clean and pushed;
- give Kevin a summary of every change, by area: commits, tests, proposals touched, and
  what is still open.

**Still open:**
- removing the SW vital layer in code (item 1);
- the Red return if it needs switches (item 8);
- the block-9 legs assumption (item 7);
- Braden's real Red programs.

## Phase 6

Source: archive/handover/integration-handover-phase-6.md, archive/handover/phase-6-prompt.md

<a id="phase-6-handover"></a>

Source: archive/handover/integration-handover-phase-6.md

### Integration handover — Phase 6

2026-10-22. Work on `claude/quirky-fermi-sickg4`, for Iteration 3 full
system integration on 2026-11-12. This records implementation and measured
evidence, not normative truth. Phase 5 remains the baseline; its handover
records the simulated-Pi limits and the pending owner decisions.

**Status:** the review path is built and passes its manual/scheduled
station scenarios, including simulated Pis. Full acceptance is incomplete:
CTC multi-train questions remain and physical Pis have not been verified.

#### 1. Scope and decisions

Kevin authorized reuse of Braden's real Green PLC routing pattern in the
Red integration test copies for every switch: CTC override, occupancy and
closure AUTO/WANT selection otherwise, reported-position lock while points
are occupied, and signals following the selected route. These remain test
copies for Braden's review. No automatic reversal is authorized. The
wayside split and immutable course data stay unchanged.

At least two trains per line must be exercised, without a hardcoded count
limit. Shared Pi plumbing is used for all modules with transport-specific
adapters. Real-Pi measurements precede the speed decision; Windows
packaging remains deferred. Hardware execution waits for module owners to
report a working Pi 5. The Linux build and external-directory simulated-Pi
smoke pass; physical USB and Windows delivery remain unverified.

#### 2. Yard validation and owner review

The Track Model's exception to entry-only yard validation now applies only
to Red block 9. A malformed Green-63 yard exit is rejected; Green-57 still
requires its yard-return annotation. The unchanged course files load.

D028 retains Kevin's physical connection at section-C block 9 and the
instruction to preserve the given course data. Its `Unconfirmed
interpretation` distinguishes current reader geometry from Kevin's words;
the source-file edit was an earlier implementation choice. CTC's new
module changelog records `5d51051` and the hardcoded Red `to_yard` at 9 in
`ctc/track_layout.py:120–121`, for Landis's review.

The Red-9 geometry remains an assumption: point 9, NORMAL to 8, REVERSE to
yard, fixed side 10 and light on 10. No track JSON changed.

All seven Red switches now use the Green-style pattern. Kevin approved
"Approve shared read-only neighbor closure inputs" on 2026-10-22. The
existing neighbor occupancy mechanism now shares closures through the
same adjacency helper; line scoping and output ownership are unchanged.
Switch 27 can read `CLOSED_76` and protect/select its reverse route. Speed
caps, crossings and authority rules are preserved. The existing `RedLoop` helper verifies 9 … 16 outbound to
a station stop, then an explicit return request following 17 … 66 → 52 … 9
and one retirement event. The loop checks emergency brake and signal
pickup on every tick. This adds no second launcher and no train reversal.

#### 3. Final validation and acceptance limits

All Python commands use `/home/kevin/ECE/Trains/.venv/bin/python` and Qt
checks use `QT_QPA_PLATFORM=offscreen` unless explicitly marked visible.

| Check | Evidence | Who ran it |
| --- | --- | --- |
| Shared neighbor input boundary | `python -m pytest TrackCtrlHw/tests/test_neighbor_inputs.py -q`: 4 passed, 0.02 s | Yard/routing agent |
| Red selection/controller/follower after closure extension | `python -m pytest TrackCtrlHw/tests/test_red_integration.py TrackCtrlHw/tests/test_controller.py common/harness/tests/test_green_follower.py -q`: 51 passed, 2494 subtests, 2.26 s | Yard/routing agent |
| Review, manual and scheduled process scenarios | 3 passed, 24.13 s | Orchestrator |
| Full shared Pi/recovery suite, final | 44 passed, 8.15 s | Orchestrator |
| Track Controller HW full suite, final | 89 passed, 50538 subtests, 33.35 s | Orchestrator |
| Shared fault selector wrapper | 9 passed, 20.88 s | Orchestrator |
| Red outbound and return | `python -m pytest TrackCtrlHw/tests/test_red_routing_loop.py -q`: 1 passed, 26.69 s | Yard/routing agent |
| Track Model focused layout/direction checks | `python -m pytest TrackModel/tests/test_green_direction.py TrackModel/tests/test_layout.py -q`: 59 passed | Yard/routing agent |
| Track Model full suite | 312 passed, 2.41 s, local IPC enabled | Orchestrator |
| Track Controller SW full suite | 213 passed | Orchestrator |
| CTC Office full suite | 261 passed | Orchestrator |
| Train Controller SW / HW suites | 24 / 23 passed | Orchestrator |
| Train Model full suite | 879 passed, 13 skipped; known timing-sensitive test passed | Orchestrator |
| Train Controller `main.py --check` | Zero QML warnings and behavior problems | Orchestrator |
| Complete harness, including round-trip and multi-train opt-ins | 185 passed, 3 failed, 497 subtests, 296.77 s; failures are the three bounded owner questions below | Orchestrator |
| Green round trip / Green two-train schedule | Five round-trip tests and Green two-train acceptance passed within the complete harness run | Orchestrator |
| Final frozen external-directory smoke | 20 s, exit 0; G1/R1 added, both lines ready, HELLO bundle hashes matched, seven module exits 0 and HARNESS_STOPPED; no fault events | Orchestrator |
| Shared utils | 86 passed, 43 subtests | Orchestrator |
| Final scoped flake8 | All 18 changed Python files pass with `-j1 --extend-ignore=N815`; exception covers Qt signal naming | Orchestrator |
| Final Pi source typing | Seven changed Pi source files pass the scoped mypy check | Orchestrator |

The final harness command enables both slow scenario groups:

```
QT_QPA_PLATFORM=offscreen TRACK_OVERFLOW_ROUND_TRIP=1 TRACK_OVERFLOW_MULTI_TRAIN=1 /home/kevin/ECE/Trains/.venv/bin/python -m pytest -q common/harness/tests
```

Its only failures were the mixed two-train, mixed three-train and
Green-only three-train scheduled acceptance probes. The successful review
station scenarios and Green two-train scenario do not erase those failures.
[Scenario evidence](review-scenario-evidence-2026-10-22.md) records the bounds
and observations. In mixed runs, maximum simultaneous Red count remained
one; the real CTC scheduler reserves the shared Red 9 … 66 route zone.

Green-only three-train validation reached three active trains, but at the
2,400 simulated-second bound G1 had retired while G2 remained at 65 and
G3 at 64. Static inspection found that `_release` reserves both upcoming
zones 77 … 100 and 1 … 28 before the departure from 65. This is an observed
stall and CTC owner question, not proof of permanent deadlock. No preceding
separation, exclusive-authority, emergency-brake or pickup-failure assertion
failed in those bounded probes. Owner arbitration and scheduler rules were
left unchanged.

The frozen smoke establishes startup, hash agreement, release events and
clean exits from outside the checkout. It does not independently establish
frozen station stops or multi-train acceptance. Physical Pi testing remains
pending.

#### 4. Measurement conditions

The present host is `kevin-framework`, Linux, with an Intel Core Ultra 5
325 and eight online cores (one thread per core), maximum reported clock
4.5 GHz. The user-supplied Phase 5 fix-check figures in the Phase 6
prompt describe a four-core cloud run reaching about 3.6–4.3x when 10x was
requested, with about 2 s startup, versus the earlier framework result of
9.69x with about 0.5 s startup. The final framework samples reached
9.16x headless and 8.36x with Wayland windows, with 0.50–0.61 s startup. These are not paired benchmarks:
host/CPU, process startup, scheduling, workload, profiling and display
circumstances differ, so their separate contributions cannot be quantified.
They establish no Pi performance inference. The Phase 0 four-core 2.8 GHz
Xeon/stub table is a separate historical measurement; it does not identify
the cloud fix-check machine.

The final runs on 2026-10-22 at 12:24:45–12:26 EDT used committed
`5223f1f`, including routing/closure commit `16a64b8`. CPU pressure before
them was `some avg10=0.00`, `avg60=0.00`, `avg300=0.00`; the local audit
had finished and no deliberately concurrent heavy job was run. These
conditions do not establish a fully isolated benchmark. Desktop variables
were `DISPLAY=:2` and `WAYLAND_DISPLAY=wayland-0`. The Wayland runs
launched the harness and module windows on that desktop. No screenshot or
visual inspection verified their appearance or responsiveness.

The orchestrator ran four sequential 15 s samples. Commands (each speed
is a separate invocation):

```
QT_QPA_PLATFORM=offscreen /home/kevin/ECE/Trains/.venv/bin/python -m common.harness.measure --system --test-pi process --seconds 15 --speed 1
QT_QPA_PLATFORM=offscreen /home/kevin/ECE/Trains/.venv/bin/python -m common.harness.measure --system --test-pi process --seconds 15 --speed 10
QT_QPA_PLATFORM=wayland /home/kevin/ECE/Trains/.venv/bin/python -m common.harness.measure --system --test-pi process --window --seconds 15 --speed 1
QT_QPA_PLATFORM=wayland /home/kevin/ECE/Trains/.venv/bin/python -m common.harness.measure --system --test-pi process --window --seconds 15 --speed 10
```

Xcb could not start because its cursor dependency was unavailable; visible
runs therefore used the existing Wayland desktop. They dispatch the measurement's
standard one-train workload, not the multi-train acceptance scenario.
No performance optimization was made for these samples.

| Front end | Requested | Completed / due | Achieved | Mean / median / p95 / p99 / max (ms) | Startup | Harness CPU | Dropped backlog / late replies |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Headless, offscreen modules | 1x | 151 / 150 | 1.01x | 20.38 / 18.13 / 30.72 / 35.69 / 37.98 | 0.58 s | 6% | 0 / 0 |
| Headless, offscreen modules | 10x | 1376 / 1502 | 9.16x | 10.56 / 9.06 / 23.10 / 31.19 / 90.15 | 0.50 s | 27% | 100 / 0 |
| Wayland window launch | 1x | 151 / 150 | 1.01x | 22.34 / 21.89 / 33.32 / 35.49 / 37.74 | 0.60 s | 8% | 0 / 0 |
| Wayland window launch | 10x | 1260 / 1507 | 8.36x | 11.53 / 10.32 / 24.41 / 30.01 / 65.98 | 0.61 s | 29% | 200 / 0 |

Both 1x runs pass the measurement's 99% completion criterion; both final
10x runs fail it. Headless 10x ends 126 ticks below due, with 100 explicit
dropped-backlog ticks; Wayland 10x ends 247 below due, with 200 explicit
drops. The remaining deficits of 26 and 47 are unfinished due ticks, not
additional reported drops; they do not identify an exact in-flight state.
No run reported a late reply. Reliable simulated 10x remains open. No
performance optimization or profiling was authorized or performed in
Phase 6, and the speed decision still waits for real-Pi measurements.

The initial 11:10 EDT checkpoint reached rounded 10.00x in headless and
Wayland runs, but preceded the final all-seven-switch/neighbor-closure
implementation. A local audit was also running then. Those initial samples
are historical and do not establish final-revision performance. The final
rerun does not causally isolate source changes, CPU state, scheduling or
general variability. Phase 4's 5.1–5.8 ms means, Phase 5's final
10.00–10.27 ms means, and the current 10x means of 10.56/11.53 ms are
separate workloads/samples; none establishes real-Pi performance.

The old Phase 5 table had zero explicit dropped-backlog events, but its
10x runs ended 47 and 88 ticks below due. Those unfinished ticks were not
reported as dropped-backlog events. Current results must distinguish
completed/due ticks, dropped backlog and late replies.

The Green follower snapshot reproduces the open owner issue: with a head
on 77 bound for 101 and switch 76 already reverse, a follower at 75 has
one block of authority and a zero-authority preload at 76. At 76 it has
zero authority. Once the head clears to 101, occupancy on listed block 76
holds the switch reverse for all five observed ticks. This is a seeded
boundary observation, not a physical multi-train-loop claim. The regression
reuses `_Line` from the SW starter tests; CTC/SW owner rules are unchanged.

#### 5. Open questions and remaining work

**Current follow-up (2026-10-24):** [Module owner review](module-owner-review.md) is the
single current writeup for all CTC and other module-owner findings, requested decisions
and Kevin's answers. [Phase 7 prompt](#phase-7-prompt) defines the approved next build
scope. The table below preserves the Phase 6 evidence and owner questions as recorded;
its historical approval/status wording does not establish Braden's acceptance. Kevin
confirmed his own prior approval of neighbor closures; Braden remains a required reviewer.

| Question or requirement | Owner / next evidence |
| --- | --- |
| Shared neighbor closure inputs | Approved by Kevin; implemented and verified by final HW suite and frozen bundle refresh |
| Red test programs and exact Red-9 leg geometry | Braden, Track Model owner: review copies and reader assumptions |
| SW vital-layer implementation of confirmed PLC-only policy | Harry Tye, SW owner: separate follow-up remains open |
| Occupied block missing from PLC input set counts as clear | Braden, Harry: input-completeness and cross-wayside contract review |
| Green 75/76 follower while a train stands at 77 for 101 | Harry, Landis: record scenario and review owner behavior; do not change their rules |
| Green three-train completion | Landis/CTC: observed stall at 65/64 through 2400 simulated seconds; reservation/progress review, without a permanent-deadlock claim |
| CTC Red concurrency / scheduling | Kevin: "Note this as an open question for ctc"; current Red route zone constrains simultaneous dispatch; do not change scheduler rules |
| Ticket sales rate, light-ahead B1, heaters, Green starter decisions | Existing module owners; unresolved questions carry forward |
| Real 10x performance, USB buffering and journal persistence | Real Pi 5 provisioning and measurements; speed decision waits for them |
| Windows packaging | Deferred by Kevin |
| Truth promotion | 34 branch proposals plus 4 from PR #43 await human review; agents do not promote |

Only humans promote or delete inbox proposals. D033 proposes the authorized
Red test routing policy; D034 proposes the Phase 6 readiness scope; D035
proposes the approved shared neighbor closure policy. These
are proposals, not accepted truth. No PR has been opened.

#### 6. Shared tooling and duplication avoided

The review process scenarios reuse the existing system specification and
acceptance runner. The Red round trip reuses `RedLoop`; the Green follower
snapshot reuses the SW `_Line` helper. Red PLCs reuse Braden's Green
AUTO/WANT/LOCK pattern. Neighbor occupancy and closure names/images share
one adjacency helper rather than separate neighborhood logic.

[Pi owner setup](pi-owner-setup.md) and
[bring-up checks](pi-bringup-checks.md) cover the shared production
`common.hw_link` agent, transport, provisioner, bundle manifest, echo/replay
probe and fault selector. The selector runs the existing acceptance tests;
it does not implement a second fault harness. Agent hashes are verified
at HELLO. Offline bundles include the shared protocol/core source and
checksums; hardware USB identity and service installation remain owner
steps. The same `common.harness.measure` entry point measures simulated
and hardware runs.

The Pi agent reported twelve software-only echo combinations: both modules,
process/pty, 1/10/20 KiB, each 100 payload-checked transactions at requested
100 Hz. Four recorded-workload replays each contained 658 Red STEP requests,
plus existing loads/gains ACTIONs. All identities matched and none was
rejected. Their diagnostic timings and recording provenance are tabulated
in the bring-up checks; these samples were not isolated benchmarks and do
not establish real USB performance. No physical Pi was verified.

The Linux build uses [`utils/build_linux.sh`](../utils/build_linux.sh), the
shared launcher and the source manifest. The final post-closure build ran
from an external `/tmp` directory for 20 seconds with simulated Pi
processes and exited 0. Its event log records both lines ready, G1/R1 added,
matching HELLO bundle hashes, all seven module exits at code 0 and
`HARNESS_STOPPED`, without fault events. That smoke has the narrower scope
stated in section 3; source station tests provide the station-stop evidence.

#### 7. Commits

| Commit | Scope |
| --- | --- |
| `7af402a` | Red yard validation guard, Green rejection regressions, owner changelogs and D028/D033/D034 proposals |
| `ede5c89` | Shared Pi transport, provisioning, bundle hashes and bring-up tools |
| `16a64b8` | All Red switch routing, shared neighbor closures, D035, follower observation and Red return tests |
| `5223f1f` | Approved CLI passthrough, review scenarios, Linux build recipe and scenario evidence |
| `25cc37a` | Phase 6 evidence, performance limits and CTC review questions |
| `d8b175a` | Merge the finalized remote Phase 6 prompt and four pending proposals, preserving both histories |

The orchestrator inspected `git show --stat` for every commit above and
independently ran the final checks attributed to it in section 3. The
Pi-only echo/replay timings are explicitly the Pi agent's report. No agent
changed branches or opened a pull request.

#### 8. Remote reconciliation

Kevin authorized inspection and reconciliation of the remote branch.
Normal merge `d8b175a` preserves its two commits, `caf72da` (final Phase 6
prompt) and `8300977` (four proposals), alongside the five local commits
listed above. There were no conflicts or source, UI or test changes.
Validated runtime behavior therefore remains unchanged: the complete
harness result is 185 passed and three owner-question failures; final
requested-10x measurements remain 9.16x headless / 8.36x with Wayland
window launches. No additional runtime checks were required for this
prompt/proposal-only reconciliation. The orchestrator verified the runtime
and test diff from `25cc37a` is empty and the expected bundle hash still
matches the final frozen manifest:
`31fee16e8225461b3cab92baaf77bb059ad766cd7290ac88de97b077441893c0`.

The inbox now contains 34 proposals on this branch plus four from PR #43.
Short decision IDs overlap and require human review before promotion:

| Short ID | Remote canonical key | Local canonical key | Review needed |
| --- | --- | --- | --- |
| D033 | `D033-red-test-plc-switch-routing` | `D033-red-integration-plc-routing` | Overlapping Red routing policies; reconcile their scope and content |
| D034 | `D034-authoritative-green-plc-programs` | `D034-phase6-integration-scope` | Different entries reuse the same short ID |
| D035 | `D035-pi-paths-share-one-implementation` | `D035-shared-neighbor-closures` | Different entries reuse the same short ID |

All canonical filenames are distinct. No proposal was edited, renamed,
deleted or promoted during reconciliation. Human review must resolve the
short-ID ambiguity before promotion; no prefix is treated as an already
accepted decision.

<a id="phase-6-prompt"></a>

Source: archive/handover/phase-6-prompt.md

### Prompt: Phase 6

Written 2026-10-22, after the Phase 5 fixes were verified (`36911aa..b81e213`). Kevin's scope
answers of 2026-10-22 are built in. Paste everything below the line into a new Codex session.

---

You are continuing the Track Overflow system integration on branch
`claude/quirky-fermi-sickg4`. Never change branches, and open no pull request unless Kevin
Schillinger (the user) asks for one.

Phases 0–5 and the Phase 5 fixes are done. See:
- `documents/integration-handover.md#phase-5-fixes-prompt`;
- the updated `documents/integration-handover.md#phase-5-handover`;
- design §5.6.

The whole system runs as seven processes:
- Green runs on the Track Controller SW and the Train Controller SW.
- Red runs on the Track Controller HW and the Train Controller HW, against simulated Raspberry
  Pis (`--test-pi process|pty`), because no real Pi works yet.

**Phase 6 goal (Kevin, 2026-10-22):** "be prepared for iteration 3 full system integration".
The Iteration 3 System Group Review is on **2026-11-12**. Its rubric gives 35 points to "Do the
Sub-systems Communicate" and 35 to "Does the Train Move from Yard to Destination Block".

The Pis are not done yet. Kevin: "include them as much as possible so that it is turnkey for
when they are done. do not repeat code for this reuse as much as possible so that changes can be
applied in one place."

#### Kevin's answers of 2026-10-22

| Topic | Kevin's answer | What it means here |
| --- | --- | --- |
| Goal | "be prepared for iteration 3 full system integration" | Part A. |
| Pis | "include them as much as possible so that it is turnkey" | Part B: everything ready except the hardware itself. |
| Reuse | "do not repeat code … so that changes can be applied in one place" | Applies to all work. See below. |
| Trains | "2+ trains must be able to run on each line" | Nothing hard-codes a train count. Test 2 and 3 trains per line. |
| 10x speed | "wait for pi measurements" | No speed work this phase. Measure and record only. |
| Red return | Reuse Braden's switch logic | The Red test programs route switches in the pattern of Braden's Green programs. This supersedes the earlier "wait for real" for Red switching. |
| Braden's real programs | "Our branch's (PR #43)" | `TrackCtrlHw/data/plc/green_wayside_1..3.plc` on this branch are the real ones; the older copies on `development` are not. `TrackCtrlHw/data/plc/examples/` only demonstrates warnings and errors. |
| Fix-check findings | "yes" | Part A item 7. |
| Windows packaging | "deffered" | Out of scope (K10). |

#### How you work

- **You are the orchestrator.** Delegate all legwork to subagents running **sol 6.1 at medium
  effort**. Plan, review and validate their work: read each commit's `git show --stat`, and
  re-run the key tests yourself. Report to Kevin what you verified yourself, and what you only
  have from an agent's report.
- **Agents share one working tree.** `AGENTS.md` forbids worktrees for agents. Give each agent
  a separate set of files, and tell every agent:
  - stage explicit paths only, never `git add -A`, and check `git diff --cached --stat`;
  - never touch another agent's uncommitted changes;
  - if `.git/index.lock` exists, wait and retry.
- **Commits and pushes:**
  - End commit messages with the attribution lines your environment requires.
  - Put no model identifier in any repository file.
  - Push with `git push -u origin claude/quirky-fermi-sickg4`, retrying only on network errors.
- **Reuse, one place for each change (Kevin).** Before writing anything new, look for what
  already exists and extend it. In particular:
  - The real-Pi and simulated-Pi paths share one implementation. Only the transport differs:
    one agent, one relay, one host and one protocol, in `common/hw_link`.
  - The Track Controller HW and Train Controller HW share every piece of Pi plumbing.
  - Bring-up and measurement tools reuse `common/hw_link` and `common/harness/measure.py`;
    they don't copy them.
  - Scenario scripts reuse the harness's existing options (`--dispatch`, `--schedule`,
    `--load-starters`, `--test-pi`, `--speedup`).
  - If you find existing duplication on the Pi path, fold it into one place.
  - Report every place you removed or avoided duplication.
- **Any UI change needs Kevin's permission first.** That covers QML and the Python behind a
  window. Ask and show the exact change.
- **The track data is given and can't be modified** (Kevin, 2026-10-22). Interpret it in the
  readers; never edit `TrackModel/*_line.json`.
- **`AGENTS.md` is binding:**
  - follow its session-start steps;
  - read truth with `git show` only;
  - write proposals only from Kevin's decisions or documents;
  - promotion is human-only;
  - edit existing proposals only where Kevin asks (item 7 below is such a request).
- **Python:**
  - Use the project virtual environment, and set `QT_QPA_PLATFORM=offscreen` for Qt tests.
  - Leave untracked files from earlier work untouched.
  - One Train Model UI test is known to be flaky:
    `test_ui_sync.py::test_input_list_scrolls_in_place_and_outputs_are_trimmed`. It fails
    sometimes on both the old and new code and passes alone. Report it if it fails; never
    skip it.
- **Write documentation as you go**, matching each file's style.

#### Read first

- `AGENTS.md`.
- `documents/integration-summary.md` and its post-summary decisions.
- `documents/integration-handover.md#phase-4` and `integration-handover.md#phase-5-handover`.
- `documents/system-integration-design.md`:
  - §1.4 rulings and §1.5 open questions;
  - §5.5–5.6;
  - the §6 gaps (G-CLK-6, G-HW-*, G-RUN-*, G-LIFE-*).
- `common/harness/README.md`.
- `documents/integration-handover.md#phase-5-prompt` and `integration-handover.md#phase-5-fixes-prompt`, for decisions K1–K12 and the
  answers of 2026-10-22.
- `common/hw_link/`, and the `TrackCtrlHw/` and `Train-Ctrl_HW/` READMEs.
- Braden's design: `documents/sdd/track_ctrl_hw.md` and `documents/uml/track_ctrl_hw/`.

#### Part A: Iteration 3 full-system readiness

1. **The review scenario, scripted and repeatable.** One command runs the graded run:
   - the Green waysides become ready (starters loaded) and their gains are set (test options);
   - G1 is dispatched from the yard to a Green station;
   - R1 is dispatched from block 9 to a Red station, on the HW variants with simulated Pis.

   Both trains must stop at their stations with doors open. There must be no fault events,
   and the run must end with seven clean exits. Both manual and scheduled dispatch must work
   (R84). Build the scenario from the existing options; don't write a second launcher. Add an
   end-to-end test, and a checklist for a person to run it with windows on a display.
2. **Red return and Red switching.** Kevin chose to reuse Braden's switch logic.

   Today R1, sent back to the yard, stops for good at 66. The reason:
   - The test programs only hold switch 52 where it is.
   - The way back 16→17…66→52…9 needs 52 REVERSE.
   - The direct way back (16→15) would be an automatic reversal, which
     `arbitration/no-automatic-reversal` forbids.

   Give the three Red test programs
   (`TrackCtrlHw/data/plc/red_wayside_{1,2,3}_integration_test.plc`) switch routing in the
   same pattern as Braden's Green programs (`green_wayside_1..3.plc` on this branch):
   - obey the CTC Office while it commands a switch (`CTCSW_n`, `CTCREV_n`);
   - otherwise route automatically from the wayside's own inputs (occupancy, closures), as his
     programs do (`AUTO_12`, `WANT_28`). Route so that a train the CTC Office sends back
     through 52 toward the yard gets the route;
   - lock a switch where it reports while a train is on its points;
   - keep the signals following the route.

   Do this for every Red switch, not only 52. Constraints:
   - Keep his structure and naming. Don't invent a second style.
   - The programs stay test copies for Braden to replace or approve.
   - Keep the wayside split (Red-1: 1–24 and 73–76; Red-2: 25–45 and 67–72; Red-3: 46–66).
   - Keep the no-automatic-reversal rule and the block-9 reading (point 9, NORMAL 8, REVERSE
     yard, light on 10).
   - If routing a switch needs an input the HW core does not give a program today, stop and
     ask Kevin.

   Then:
   - R1 returns to the yard and retires;
   - the Red outbound runs still work;
   - add tests for both;
   - record the change in `TrackCtrlHw/CHANGELOG.md` with Braden as reviewer.
3. **Two or more trains per line.** Nothing may hard-code a train count. Run 2 and 3 trains
   per line on Green and Red under the CTC Office's schedule in automatic mode, and show that
   exclusive authority, separation and dwell all hold:
   - no emergency brake, no pickup latch, no protocol fault;
   - also exercise the Green follower case: Landis's open question at 75/76, while a train
     stands at 77 bound for 101. Report what happens. Don't change the CTC's or Track
     Controller's rules without the owners;
   - add the scenarios as tests (opt-in if they are slow).
4. **Speed: measure only (Kevin: "wait for pi measurements").** Run `measure --system
   --test-pi process` at 1x and 10x, headless and with every window visible on a real display.
   Use the review machine if Kevin names one. Record the numbers against the Phase 4 and
   Phase 5 tables in the handover. Don't optimize for 10x this phase.

   The Phase 5 fix check measured:
   - about 3.6–4.3x at 10x on a 4-core cloud machine, against the handover's 9.69x on
     kevin-framework;
   - startup of about 2 s, against the handover's 0.5 s.

   Explain the difference. Correct the handover table, which reports 1,455 of 1,502 ticks done
   yet "zero slipped".

   Also:
   - Make `measure --system` without `--test-pi` say what it is waiting for, instead of
     waiting silently. Show the existing `PI_SEARCH` events or a one-line hint, from one place
     in the code.
5. **The full system as one Linux build.** Extend the PyInstaller recipe to every module:
   - `TrackCtrlHw` and its data;
   - `common/hw_link`;
   - the Pi agent bundle, with its hash checked at `HELLO`.

   Smoke-test the build from outside the checkout with simulated Pis: both lines dispatched,
   and seven clean exits. Windows packaging stays deferred (Kevin: "deffered").
6. **Event log and operator readiness.** Confirm a person can follow the run from the harness
   window and the CSV log alone:
   - readiness per line;
   - each train added and retired;
   - missing Pis named;
   - faults.

   Fill any gap with log events only. Make no UI change without permission.
7. **Findings from the Phase 5 fix check (Kevin: "yes").**
   - **CTC Office change log.** Commit `5d51051` hard-codes Red `to_yard` to block 9 in
     `CTC-Office/ctc/track_layout.py:120-121`. Add an entry to the CTC Office change log
     (create `CTC-Office/CHANGELOG.md` in `Train-Ctrl_HW/CHANGELOG.md`'s style if none
     exists), and list the change for the CTC Office owner's review.
   - **D028.** Revert the proposal's wording beyond recording Kevin's words of 2026-10-22.
     Kevin asked for this. That means:
     - restore its "Unconfirmed interpretation" section;
     - stop calling K2 a "source-file edit instruction";
     - keep reader-interpretation wording out of the normative text, and put it in a
       labelled assumption section;
     - keep a heading rename (D028 or D031) only where it makes the entry key match the
       target filename (`AGENTS.md`: "the filename is the entry key"); otherwise restore the
       heading.
   - **Track Model guard.** Limit the `_check_directions` change
     (`TrackModel/track_model/layout.py:331`, which dropped the `from_yard` guard) to the
     Red block-9 reading. Keep the guard for every other switch and line, and add a test that
     it still rejects a bad layout on Green. Record the change in `TrackModel/CHANGELOG.md`.
   - **flake8 wording.** Correct the handover's "Production flake8 passes": it holds only
     with the repo's existing N815 convention for Qt signals ignored. Say so.
8. **Review documents.** Write:
   - a one-page run book for the review: setup, the command, what to show, and how to recover
     if something stalls;
   - an update of the design document.

#### Part B: Pis turnkey, without hardware

No Pi works yet. Make the day a Pi works a matter of plugging in and running scripted checks,
with no new code. Everything here reuses `common/hw_link` and `measure.py`. Test everything
that can be tested without hardware against the simulated Pis (`--test-pi pty` exercises the
serial path).

1. **Provisioning, scripted and documented.** One setup recipe for the Pi 5, shared by both
   HW modules and parameterized by module. It covers:
   - USB device mode on the USB-C port;
   - the K5 identity:
     - manufacturer `Track Overflow`;
     - product;
     - serial `TO-TRACK-CTRL-HW-01` or `TO-TRAIN-CTRL-HW-01`;
     - VID:PID `1d6b:0104`;
   - installing the agent bundle;
   - starting the agent at boot so it answers `HELLO` within the 20 s startup timeout.

   Add a host-side check command that reports, from one place, whether each identity shows up:
   `ttyACM*` on Linux, a COM port on Windows (built-in usbser).
2. **USB round-trip checks, ready to run (G-CLK-6, K9 "agreed test when implemented").**
   Provide these as commands, run now against simulated Pis:
   - an echo test at 1, 10 and 20 KB payloads at 100 per second;
   - the agent's step time with recorded Red inputs;
   - `measure --system` against real Pis.

   They must produce a table like §5.5's. The 10x decision waits for these real numbers. Then
   give Kevin the options: accept a slower time, use a faster Pi, or shrink the per-tick data
   on the Pi link.
3. **Fault checks, ready to run (K7, K11).** Write a checklist and a script for each check,
   tested now with simulated Pis where possible (kill and restart the simulated agent; drop
   the pty). The checks: unplug and replug while the clock runs, and reboot a Pi. Expected:
   - `REPLY_LATE`, then recovery and `LATE_REPLY_RECEIVED`;
   - no double step;
   - gains re-sent only if the connection was lost while the clock was running;
   - the missing-Pi event naming the module.
4. **A bring-up run book** for the module owners (K5: "Pi 5 set up by module owners"). It
   gives the order of the checks above, the expected output of each, and what to send back.
   It ends with the full system on real Pis on Linux. Windows comes later, with packaging.

#### Questions to put to Kevin and owners as they come up (don't decide)

- Removing the SW vital layer in code, now that K3b covers both variants (Harry Tye; Kevin
  kept this open).
- Braden's review of the Red test programs' switch routing (item 2), and his real Red programs
  and wayside split if he writes them.
- The Red block-9 reading (point 9, NORMAL 8, REVERSE yard, light on 10), for the Track Model
  owner and Braden.
- The cross-wayside occupancy rule, where "an occupied block missing from the inputs counts as
  clear" (Braden, Harry).
- The CTC Office's Red `to_yard` change (item 7), for the CTC Office owner.
- Earlier open owner questions:
  - the ticket rate (Q-P4-7);
  - the Track Model light-ahead issue B1;
  - heaters (D026);
  - the Green starter and follower decisions (Harry, Landis).
- The pending truth proposals, on this branch and the 4 from PR #43, for Kevin to review and
  promote.

#### Before you finish

Run every suite:
- harness and utils;
- `common/hw_link`;
- Track Controller HW and SW;
- CTC Office;
- Track Model;
- Train Controller, with `main.py --check`;
- Train Model;
- the opt-in Green round trip;
- the new review-scenario, Red-return, multi-train and Pi-readiness tests.

Phase 5 fix-check baseline at `b81e213`:

| Suite | Passed |
| --- | --- |
| Harness + utils | 260 |
| `common/hw_link` | 33 |
| Track Controller HW | 80 |
| CTC Office | 261 |
| Track Controller SW | 213 |
| Track Model | 310 |
| Train Controller HW | 23 |
| Train Controller SW | 24 |
| Train Model | 878, plus the flaky one |
| Green round trip | 5 |

Then:
- write a Phase 6 handover and update the design (§5.7);
- leave the tree clean and pushed;
- give Kevin a summary of every change, by area: commits, tests, measurements, duplication
  removed, proposals, and open questions.

## Phase 7

Source: archive/handover/integration-handover-phase-7.md, archive/handover/phase-7-prompt.md

<a id="phase-7-handover"></a>

Source: archive/handover/integration-handover-phase-7.md

### Phase 7 integration handover

Prepared 2026-10-24. This phase makes functional review explicitly 1x and
consolidates shared Pi HELLO matching. The single
[module owner review queue](module-owner-review.md) retains the CTC and other owner
questions; this handover does not resolve them or establish new policy.

#### Revision and environment

Work began at `022608a` on `claude/quirky-fermi-sickg4`, a descendant of `f6ed1a1`.
The review host is `kevin-framework`, running Ubuntu 26.04.1, Python 3.14.4,
PySide6 6.11.2 and PyInstaller 6.22.2. The functional-review host is provisional,
as Kevin requested. Source commit `92e500b` contains the five Python changes
described below, on the same baseline. All times in this record are EDT (UTC−04:00).

Historical [Phase 6](#phase-6-handover) and
[scenario evidence](review-scenario-evidence-2026-10-22.md) results retain their
original revisions, hosts and bounds. They are not Phase 7 measurements.

#### Implementation and approved scope

`common/hw_link/protocol.py` now owns `matches_hello`, used by both the relay and
bringup probe to compare HELLO operation, hardware module, protocol version,
session, agent version and bundle hash. Existing decoding still checks framing
and field types. The helper receives expected values explicitly and adds no
manifest, transport or provisioning dependency.

Relay admission still requires a truthy boot identifier; its boot comparison,
reboot recovery and gain policy remain in the relay. Bringup still accepts an
otherwise valid HELLO without a boot identifier. Both callers retain their exact
existing mismatch diagnostics. New tests cover matching replies, every identity
mismatch and missing identity field, relay boot rejection, and bringup's actual
receive/decode path with optional boot.

The process-review tests use the existing seven-module harness and two explicit
simulated Pi processes. Functional review is fixed at 1x with a 240-second wall
bound per manual/scheduled case. It retains `TIME_SLIPPED` among the fault
assertions, stopped trains with Green right-only and Red both-side platform doors,
continuous 45-second dwells, commanded/active emergency-brake checks and seven
clean module exits. Ten-times speed is measured separately.
The [runbook](review-runbook.md) and [HW changelog](../TrackCtrlHw/CHANGELOG.md)
carry the approved documentation follow-ups.

Kevin approved neighbor `CLOSED_n` inputs before implementation. He explicitly
stated that the approval was his, not Braden's acceptance. Braden remains the
required reviewer. No owner has been contacted by this work.

This phase does not authorize UI changes, including Python behind windows;
scheduler, vital-layer, starter, PLC or interpretation policy changes; new
transport/provisioning paths; or 10x optimization before real-Pi measurements.
`TrackModel/*_line.json`, preserved user files and existing inbox proposals remain
outside the edit scope. Truth facts were read from fetched `origin/truth`; no
proposal is treated as truth. The functional-review-speed proposal remains pending
human promotion, alongside the existing proposals.

#### Recovery and evidence provenance

A power cut interrupted the first complete-harness run and removed the pre-cut
`/tmp/phase7-*` logs. The exact cut minute is unknown; work resumed and the
repository was rechecked at **10:55 EDT on 2026-10-24**. The interrupted run has
no complete result. Pre-cut shared-link and utils counts were observed by the
orchestrator, but the fresh post-cut results below are the primary evidence.

Qwen drafted runbook/changelog text and recovery labels; the sol agent corrected
wording and the orchestrator reviewed the actual diff rather than relying on a
worker success status.

#### Fresh verification

Post-cut checks used `/home/kevin/ECE/Trains/.venv/bin/python`,
`QT_QPA_PLATFORM=offscreen`, and the Phase 7 source now committed as `92e500b`.
The module-validation agent ran suites sequentially in isolated processes, with
local IPC enabled, from **10:57:07 to 10:59:46 EDT**. The retrievable log is
`/tmp/phase7-postcut-module-validation.txt`; its recorded wall durations include
process startup. These are agent-run results reviewed by the orchestrator.

| Command (from repo root unless noted) | Result | Wall time |
| --- | --- | --- |
| `python -m pytest -q CTC-Office/tests` | 261 passed, 284 subtests | 20.88 s |
| `python -m pytest -q TrackCtrlHw/tests` | 89 passed, 50,538 subtests | 27.65 s |
| `python -m pytest -q TrackCtrlSW/tests` | 213 passed, 16 subtests | 9.63 s |
| `cd TrackModel` then `python -m pytest -q tests` | 312 passed | 2.43 s |
| `python -m pytest -q TrainController/tests` | 24 passed | 0.17 s |
| `python -m pytest -q Train-Ctrl_HW/tests` | 23 passed, 18 subtests | 0.29 s |
| `cd Train-Ctrl_HW` then `python main.py --check` | Exit 0; zero QML warnings and behaviour problems | 29.42 s |
| `cd TrainModel` then `python -m pytest -q tests` | 879 passed, 13 existing skips | 39.20 s |
| `python -m pytest -q common/hw_link/tests` | 71 passed | 8.08 s |
| `python -m pytest -q utils/tests` | 86 passed, 43 subtests | 20.99 s |

The pytest suites total **1,958 passed, 13 existing skips and 50,899 passed
subtests**. The timing-sensitive Train Model UI test
`test_ui_sync.py::test_input_list_scrolls_in_place_and_outputs_are_trimmed` ran
and passed in the complete suite, without a retry or additional skip.

The orchestrator then independently reran the complete shared-link suite on `92e500b`: **71 passed in 7.92 s**, recorded in `/tmp/phase7-parent-hw-link.log`.
The orchestrator also reran the scoped Flake8 command with pep8-naming/N815 exception and the three-file mypy command below; both passed after the separate measurements completed.

The independent post-cut source audit also passed:

- The 27 new HELLO cases passed in 0.06 s, including each identity mismatch,
  missing identity fields, relay boot admission and bringup's receive/decode path.
- Scoped Flake8 used `-j 1 --max-line-length=79 --extend-ignore=N815` on the
  three HELLO production files, new HELLO test and review-scenario test.
  `pep8-naming==0.15.1` was reinstalled only in `/tmp/phase7-lint-deps`, enabled
  through `PYTHONPATH`. Without the exception, only existing relay signals
  `viewChanged` and `diagnosticEvent` produce N815 warnings in these files.
  Broader `common/hw_link` lint retains twelve existing N802 fake-Qt method
  warnings in `test_bringup.py` and `test_transports_recovery.py`.
- Mypy passed for `protocol.py`, `relay.py` and `bringup.py` using
  `--explicit-package-bases --disallow-untyped-defs --follow-imports=silent
  --ignore-missing-imports`.
- `review_schedule` and both mixed/Green opt-in multi-train test functions are
  AST-identical to baseline `022608a`. Relay reboot/recovery/gain policy and
  exact caller mismatch diagnostics are preserved.
- All four runbook shell blocks pass `sh -n`. Interpreter selection checks cover
  the project venv, sibling venv, supplied interpreter and missing-venv failure.
  Dwell-observer boundary checks accept closure exactly 450 ticks after opening,
  reject closure at 449 ticks, and credit only 44.9 s at the last open sample.

##### Process reviews and separate performance measurements

The orchestrator started the complete harness run on `92e500b` at 11:00 EDT:

```sh
QT_QPA_PLATFORM=offscreen TRACK_OVERFLOW_ROUND_TRIP=1 \
  TRACK_OVERFLOW_MULTI_TRAIN=1 "$PYTHON" -m pytest -q --durations=12 \
  --basetemp=/tmp/phase7-final-harness common/harness/tests
```

The direct orchestrator run completed with **185 passed, 3 failed and 497 passed
subtests in 456.45 s** (`/tmp/phase7-harness.log`). The three failures are the
unchanged owner probes below; the suite does not have a clean acceptance result.
Both manual and scheduled seven-process reviews passed at 1x in 111.39 s and
111.34 s respectively, each within its 240-s wall bound. Their assertions verified
continuous station dwells, correct platform doors, no fault events including
`TIME_SLIPPED`, no commanded/active emergency braking and seven clean module exits.
Direct event-CSV inspection confirmed manual/scheduled endpoints at ticks
1108/1107: each had two `TRAIN_ADDED` records, seven `MODULE_EXITED` records with
`exit code 0`, only `CLOCK_RESUMED 1x` for clock changes, no `SPEED_CHANGED`, and
no event from the unchanged `FAULTS` set. Green-only two-train and existing
round-trip tests also passed.

| Unchanged opt-in owner probe | Fresh endpoint / failed requirement |
| --- | --- |
| Mixed two trains per line | All four completed dwells; maximum simultaneous Green/Red count was 2/1, failing the required 2/2. The loop can finish before its 900-s simulation bound. |
| Mixed three trains per line | At the 900-s simulation bound, G1/G2/R1/R2 completed; maximum counts were 3/1. Endpoint: G1=111, G2=65, G3=64, R2=48. |
| Green-only three trains | At the 2,400-s simulation bound, G1/G2 completed with three simultaneously active. G1 retired; endpoint G2=65, G3=64. |

No earlier separation, exclusive-authority, emergency-brake or pickup assertion
failed in those probes. Their final fault-event assertion follows the failed
endpoint assertion and was not reached. They run real cores in one process and do
not verify process/Pi protocol correctness. The owner requests remain [CTC-1 and
CTC-2](module-owner-review.md#ctc-1-red-concurrency); no scheduler policy was changed.

Separate direct headless measurements use the same one-train system wiring,
two simulated Pi processes and zero filler bytes:

```sh
"$PYTHON" -m common.harness.measure --system --test-pi process --seconds 15 --speed 1
"$PYTHON" -m common.harness.measure --system --test-pi process --seconds 15 --speed 10
```

| Quantity | 1x | 10x |
| --- | --- | --- |
| Startup / measured wall time | 0.46 / 15.01 s | 0.52 / 15.02 s |
| Completed / due ticks | 150 / 150 | 1,500 / 1,502 |
| Achieved simulation speed | 1.00x | 9.99x |
| Dropped backlog (`ticks slipped`) | 0 | 0 |
| Late replies | 0 | 0 |
| RTT mean / median / p95 / p99 / max | 7.87 / 7.17 / 13.03 / 17.23 / 18.50 ms | 6.12 / 5.30 / 13.50 / 19.51 / 38.47 ms |
| Harness CPU, one core | 2% | 19% |

Both commands exited 0; logs are `/tmp/phase7-measure-1x.log` and
`/tmp/phase7-measure-10x.log`. Both samples meet the existing 99%-completion,
zero-drop, zero-late criterion. At 10x, two due ticks remained unfinished when the
sample ended; that is separate from the reported zero abandoned backlog, and the
report does not identify their exact in-flight state. No other test workload was
deliberately run during these samples; ordinary app/background activity was not
isolated. These are short samples of this host and workload, not a reliable-10x
guarantee or physical-Pi performance evidence. The speed decision remains open
until real-Pi measurements.

#### Limits and remaining work

Simulated Pi processes and raw ptys do not verify physical USB power, cold boot,
port identity, unplug/reboot durability or real-board performance. Physical Pi
checks wait for working boards and owners' measurements. Windows packaging remains
deferred; this phase does not claim Windows acceptance or a fresh frozen build.

In-process opt-in probes cannot establish process-protocol correctness. A bounded
multi-train stall does not prove permanent deadlock. Owner-question failures remain
visible and must not be weakened into passing acceptance tests. The known Train
Model UI flake passed in this run; that observation does not establish that its
timing sensitivity is resolved.

The twelve requests and Kevin's answers remain in
[module-owner-review.md](module-owner-review.md). Human action is still required
for proposal collisions: consolidate D033; withdraw D034's Phase 6 scope plan while
retaining authoritative Green; preserve both distinct D035 policies and renumber
one. The branch inbox retains 35 pending proposals, with four separately
attributed to PR #43. Agents did not modify, delete, rename, renumber or promote
existing proposals. All twelve owner requests and these human proposal actions
remain open.

#### Independent Phase 7 verification receipt

The follow-up check at `d606e05` on `kevin-framework` on 2026-10-24 reproduced
**1,958 passed, 13 existing skips and 50,899 passed subtests** across module,
utils and shared-link suites. The orchestrator directly ran the 71 shared-link
tests and spot-checked both completed process-review event CSVs; the check-only
verification subagent ran the remaining suites. The known timing-sensitive Train
Model UI test ran and passed; its timing sensitivity is not thereby resolved.

The full harness with both opt-in families produced **185 passed, 3 failed and
497 passed subtests in 461.59 s**. Manual and scheduled 1x process reviews passed
in **111.45 s** and **111.32 s**, within their 240-second bounds. The three
preserved failures remain the mixed-count 2/3 concurrency/completion probes and
Green-count 3 completion probe described in the shared owner-review queue.
HW `main.py --check` exited 0 with zero QML warnings and behaviour problems.
Scoped Flake8 passed with the existing N815 exception; three-file mypy passed.

The commit/rule audit found no implementation-scope violations: no UI, protected
course JSON, owner policy, preserved user file or inbox proposal changed. Two
minor stale links were found in `module-owner-review.md` (then lines 90/137):
test anchors 183/295 rather than 234/346. The documentation follow-up corrected
those anchors on 2026-10-25; no code changed.

Recovery on 2026-10-25 found the same branch/HEAD, remote alignment and five
preserved untracked files, with no tracked changes. Toolchain minima still pass.
The prior `/tmp/phase7verify-*` logs and event CSVs are no longer available; the
recovery check did not rerun tests. These counts describe the completed October 24
verification, not a new October 25 run. No Qwen diagnostic output was recovered.
See [module owner review](module-owner-review.md) for the current owner requests.

<a id="phase-7-prompt"></a>

Source: archive/handover/phase-7-prompt.md

### Prompt: Phase 7

Written 2026-10-24 from Kevin's post-Phase-6 answers. Paste everything below the line
into Codex. Preparing this prompt did not implement or test the build work.

---

Continue Track Overflow integration on `claude/quirky-fermi-sickg4`. Never change branches,
create worktrees, discard work or open a PR unless Kevin asks. Read `AGENTS.md`, complete
its session-start checks, including the truth fetch and INDEX read. Also run
`git fetch origin claude/quirky-fermi-sickg4` and verify HEAD is `f6ed1a1` or a descendant
without switching branches. Report unexpected state; do not merge, reset or rebase
concurrent changes without authorization.

Read `documents/integration-handover.md#session-handover-2026-10-22`, then `documents/module-owner-review.md`
(the single current owner-review queue), `documents/integration-handover.md#phase-6-handover`,
`documents/review-runbook.md` and `documents/review-scenario-evidence-2026-10-22.md`.
Historical results belong to their recorded revisions and hosts, not this phase.

#### How you work

You are the orchestrator. Delegate legwork to **sol 6.1 medium effort** subagents; plan,
review and validate. Assign disjoint files in the shared working tree. Stage explicit
paths only, inspect `git diff --cached --stat`, never touch another agent's uncommitted
work, and wait/retry on `.git/index.lock`. Inspect each commit's `git show --stat` and
rerun key checks yourself; distinguish direct verification from agent reports.

Use the project venv and offscreen Qt for tests. Preserve all user work, including:
`TrainModel/docs/architecture-drawio-prompt.md`, `class-diagram-supplemen-prompt.md` and
`uml-sequence-prompt.md` in that directory; `common/harness/tests/adversarial_probe.py`;
and `documents/central-harness-adversarial-2026-10-20.md`.
Never edit `TrackModel/*_line.json`. Any UI change (including Python behind a window)
needs Kevin's prior approval for that exact change. Reuse existing harness options and
shared `common/hw_link`; real and simulated Pis differ only in transport. No 10x
optimization before real-Pi measurements. Windows packaging remains deferred.
Read facts from fetched `origin/truth` only; proposals are not facts. Only humans promote
or delete inbox proposals. Do not edit/rename/renumber/withdraw existing proposals.
New normative decisions require full-entry proposals with checked aliases and provenance,
committed and pushed that session. Keep plans, status and results out of truth.

#### Kevin's decisions, 2026-10-24

- Prior neighbor `CLOSED_n` approval: **"yes"**. Braden acceptance: **"he didnt i did.
  ensure it is documented"**. Attribute approval to Kevin; Braden remains required reviewer.
- Functional review 1x, `TIME_SLIPPED` retained as fault, 10x measured separately:
  **"yes option a is better"**. Review host: **"for now the review will happen on this
  machine"**, identified that session as `kevin-framework`.
- Human collision recommendation: **"ues"** — consolidate D033; withdraw D034's Phase6
  scope plan, retain authoritative Green; retain both D035 policies and renumber one.
  Record this recommendation; agents do not perform deletion, renumbering or promotion.
- CTC findings: **"give a wriet up of the exact issues found"**; carryovers: **"write them
  up for module owner review"**; **"put the ctc and other module owner review things in
  the same place"**. Keep the shared review file current; do not message owners.
- Shared HELLO helper, explicit Braden required reviewer and portable runbook path:
  **"approved"**.

#### Build scope

1. Run manual and scheduled process review tests at **1x**, with sufficient bounded
   wall time. Retain every safety/protocol fault assertion including `TIME_SLIPPED`,
   station stops, platform-side doors, continuous 45-s dwell and seven clean exits.
   Reuse the process runner. Do not weaken unresolved multi-train probes.
2. Make the runbook's functional recipe explicitly 1x. Replace fixed `/home/kevin/...`
   Python with portable project-venv selection or caller-supplied interpreter. Identify
   provisional host `kevin-framework`; document optional 10x measurement separately.
3. Consolidate HELLO identity/protocol/session/version/hash validation in one helper.
   Preserve relay boot/reboot checks and caller-specific diagnostics. Test valid replies
   and each rejected identity field, including relay's boot requirement. Reuse protocol
   facilities; do not add another transport, host, agent or provisioning path.
4. Name Braden explicitly as required reviewer in `TrackCtrlHw/CHANGELOG.md`; document
   Kevin's approval before neighbor-input implementation without claiming Braden accepted.
   Keep CTC and other owner findings in `module-owner-review.md`, linked elsewhere.
   CTC/Track Controller owner issues are diagnostics and decision requests only: do not
   change scheduler, vital-layer, starter, PLC or interpretation policies to pass probes.

#### Validate and deliver

Run focused 1x process review and shared-Pi HELLO tests, then relevant complete suites:
harness/utils, common.hw_link, Track Controller HW/SW, CTC, Track Model, Train Controller
HW/SW (including `main.py --check`), Train Model and existing opt-in scenarios. Preserve
and report owner-question failures. Report the known Train Model UI flake; do not skip it.
Run scoped lint/type checks and state existing exceptions accurately, including N815.
Record revision, host, commands and bounds with fresh results. Bounded stalls do not prove
permanent deadlock; in-process probes do not verify process protocol faults; simulated
Pis do not establish physical USB readiness. Separate 10x measurements into completed/due
ticks, dropped backlog and late replies. Physical-Pi checks wait for working boards.
Write a Phase7 handover and link the shared owner review. Commit explicit paths with
required attribution and push this feature branch normally. Stop/report non-fast-forward
rejection rather than overwrite history. Preserved user files may leave the tree unclean.
Report changes, commits, direct/agent verification, limitations and remaining decisions.

## Phase 8

Source: archive/handover/phase-8-prompt.md

<a id="phase-8-prompt"></a>

### Prompt: Phase 8 — owner diagnostics

Prepared 2026-10-25. Kevin's direction: "No updates—continue owner diagnostics".
Paste everything below the line into Codex. Reviewed diagnostic observations live
in the shared owner-review queue; this prompt does not authorize policy changes.

---

Continue on `claude/quirky-fermi-sickg4`. Read `AGENTS.md` and complete its
session-start checks, fetching `truth` and this feature branch once. Read fetched
truth INDEX first, then relevant shards only via `git show`. Verify HEAD is
`d606e05` or its expected descendant and report unexpected state without repair.
Never change branches, create worktrees, discard work or open a PR unless asked.

Read `documents/integration-handover.md#session-handover-2026-10-22`,
`documents/integration-handover.md#phase-7-handover`, `documents/module-owner-review.md`,
`documents/review-runbook.md` and this prompt. The shared owner-review file is the
single current queue; link it instead of creating parallel issue writeups.

#### How you work

You are the orchestrator. Delegate bounded legwork to **sol 6.1 medium effort**
subagents with disjoint file ownership; review their actual diffs and evidence.
Kevin runs build phases in Codex. His 2026-10-25 answer is
**"No updates—continue owner diagnostics"**: there are no new owner decisions or
working-Pi reports. Preserve existing ownership and approval boundaries.
Kevin's temporary pause expires on 2026-10-25 at **02:20:45 EDT (06:20:45 UTC)**:
make no Qwen delegate calls before that time. Expiry does not require using Qwen.

Preserve these five untracked user files:
`TrainModel/docs/architecture-drawio-prompt.md`,
`TrainModel/docs/class-diagram-supplemen-prompt.md`,
`TrainModel/docs/uml-sequence-prompt.md`,
`common/harness/tests/adversarial_probe.py`, and
`documents/central-harness-adversarial-2026-10-20.md`.
Do not modify `TrackModel/*_line.json`. Any UI change, including Python
behind windows, requires Kevin's prior approval for that exact change.
No scheduler, zone/reservation, vital-layer, PLC/starter, routing or interpretation
policy changes to make owner probes pass. No 10x optimization before real-Pi
measurements, new transport/provisioning paths or claims of physical-Pi readiness.
Truth is read from fetched `origin/truth`; code observations are not decisions.
Do not edit, delete, rename, renumber or promote existing inbox proposals.

#### Known diagnostic baseline

- Green's earlier zone hold cleared; at the endpoint CTC grants 35 blocks but the
  SW starter `AUTH_65` gate yields zero, without a reported vital-layer override.
- The Red review plan forms one zone 9…66 through yard index 101; seeded
  snapshots release followers only after the preceding run is DONE.
- Normal occupancy maps are complete; member omission becomes clear membership,
  while missing fields/namespace and retained rejected ticks are distinct cases.

#### Diagnostics scope

1. Turn the reviewed Green trace into bounded reusable diagnostic coverage using
   existing real-core harness wiring. Capture the first transition into the 65/64
   hold and the grant boundary, not merely another identical endpoint. Preserve
   schedule/tick semantics and distinguish starter separation from CTC admission.
   Record front position, beacon, station eligibility and door-command state at
   the first hold; preserve existing assertions without assuming an arrival-policy fix.
2. Make the reviewed Red schedule/zone/hold snapshots reproducible with meaningful
   assertions on current behavior. Preserve the distinction between seeded Worlds
   and physics acceptance; do not choose a new zone, route or reservation policy.
3. Make the reviewed input-completeness boundary cases reusable: individual member
   omission versus explicit false, unavailable namespace, missing whole fields and
   repeated snapshots. Fill the static-only rejected-tick retention gap with a
   bounded harness injection that observes retained outputs and rejection events;
   preserve the clock barrier and separate rejected, late and disconnected cases.
4. Reuse existing harness/test facilities and meaningful observations. Preserve the
   three known acceptance failures and all safety/protocol assertions. Avoid
   duplicate runners, permanent debug output and implementation-mirroring tests.
   Do not rerun just-completed traces or full suites merely to reproduce their counts.
5. Update the matching entries in `module-owner-review.md` with reviewed evidence,
   exact revision/host/commands/bounds and concise Landis/Harry/Braden decision
   packets: observation, remaining gap, owner question and required validation.
   Keep historical results scoped to their revisions; a bounded stall is not proof
   of permanent deadlock. No separate issue writeups or policy fixes.

#### Validate and deliver

Use the project venv and offscreen Qt. Keep scratch traces and caches outside the
repo where feasible. Run new/changed diagnostic checks and appropriate affected
suites; do not repeat the completed Phase 7 verification without a source change
or a new failure requiring it. Label direct checks versus agent reports.
Report ticks/bounds and expected owner failures explicitly. In-process diagnostics
cannot verify process/Pi protocol correctness; simulated Pis cannot verify USB.
Review explicit staged paths and each commit's stat, preserve all user work, commit
with required attribution and push this feature branch normally. Stop and report
non-fast-forward rejection. Summarize findings and unresolved owner/Pi decisions.
Do not implement a policy fix or advance another phase without Kevin's answers.

## Session handover 2026-10-22

Source: archive/handover/session-handover-2026-10-22.md

### Session handover, 2026-10-22 (after Phase 6)

For a fresh session that continues the orchestration of the Track Overflow integration on
`claude/quirky-fermi-sickg4`. It holds only what the repository doesn't already say. For
everything else, read:
- `documents/integration-handover.md#phase-6-handover`, `review-runbook.md` and
  `review-scenario-evidence-2026-10-22.md`;
- `documents/integration-handover.md#phase-6-prompt`, for the standing rules under "How you work".

#### How this work runs

- **Kevin (the user) runs the build phases in Codex.** This session's role is orchestrator
  only (Kevin: "moving forward you are only the orchestrator all legwork is to be done by
  subagents and you review and validate"):
  - Write the next phase's prompt as `documents/phase-N-prompt.md`, with everything below a
    `---` line pasted into Codex.
  - When Kevin says a phase is done, verify it with one check-only subagent (no edits), then
    spot-check the key claims yourself.
  - Report to Kevin: a verdict per item, rule violations, suite numbers and his open
    questions.
  - Then draft the next prompt from his answers.
- **Prompts for Codex** name the subagent model as **"sol 6.1 medium effort"**, never this
  session's model.
- **Kevin answers questions tersely.** Ask with numbered options and mark the recommended one.
  Put his exact words in prompts and proposals as provenance.
- **Before writing a decision into a prompt, check it against the code.** Example: on
  2026-10-22, "wait for Braden's programs" turned out to mean his three Green programs in
  `TrackCtrlHw/data/plc/`, which led to a follow-up question.
- **Kevin's other wishes:**
  - When he asks for a prompt, print it in a code block for copy and paste, as well as
    committing it.
  - Wrap it in "how to find and start" instructions when he asks.
  - Make sure everything is committed and pushed before stopping.
- **The verification environment is per-container and is lost between sessions.** Recreate a
  venv (`python -m venv`, then `pip install "PySide6>=6.11" pytest mypy flake8 pyinstaller`),
  and run Qt with `QT_QPA_PLATFORM=offscreen`. Cloud hosts are 4-core: 10x runs reach about
  4x there, against about 9x on Kevin's machine (kevin-framework).

#### Kevin's answers this session that the repo doesn't record

- **`TrackCtrlHw/ui/app.py` `state_factory` parameter (Phase 5 fixes):** "I approved the
  app.py change".
- **10x speed:** "wait for pi measurements". No optimization until real Pi numbers exist.
- **Red return:** reuse Braden's switch logic. This superseded his earlier "wait for real".
  Phase 6 did this.

#### Phase 6 verification (2026-10-22, at `a23bc22`)

It was checked on a 4-core cloud host; I spot-checked the proposal collisions and the
`wayside.py` change myself.

**Rules held:**
- no UI file changed;
- `TrackModel/*_line.json` untouched;
- nothing promoted or pushed to `truth`;
- the D028 edit matches what Kevin asked for.

| Item | Verdict | Evidence or gap |
| --- | --- | --- |
| 1. Review scenario | Partly | One command from existing options, with tests and a run book. **Both review tests fail on a 4-core host**: they run at 10x and count `TIME_SLIPPED` as a fault. They pass at 1x. No CSV event records a station stop. |
| 2. Red switching | Met, with one exception | All seven Red switches (9, 15, 27, 32, 38, 43, 52) follow Braden's pattern; R1 returns and retires; the split is kept. **Exception:** `TrackCtrlHw/track_ctrl_hw/wayside.py` (Braden's core) gained neighbour `CLOSED_n` program inputs in the same commit, `16a64b8`. The prompt said to stop and ask first. The handover quotes Kevin approving "Approve shared read-only neighbor closure inputs", but nothing shows he was asked before the code was written. |
| 3. Two or more trains | Not met, reported honestly | Green with 2 trains passes. Green with 3 stalls with G2 at 65 and G3 at 64. Red stays at one train because of the CTC zone rule (9…66). The tests run in process, so protocol faults aren't exercised. The follower case is a seeded snapshot: at 76 the follower gets 0 authority, and occupancy of 76 holds switch 76 REVERSE. |
| 4. Speed, measured only | Partly | Recorded: 9.16x headless and 8.36x Wayland on kevin-framework; 4.26x on the cloud host. The "zero slipped" claim is corrected, and `measure` now prints a hint when `--test-pi` is missing. The difference between machines is described but not explained. |
| 5. Linux build | Met | Built and smoke-tested from outside the checkout. When frozen, the host and the simulated agent read the same `pi-bundle.json`, so the hash check can't fail in that smoke test. |
| 6. Event log | Met | No new events were needed. |
| 7. Fix-check findings | Met | CTC Office change log, D028, the Track Model guard limited to Red block 9 (a Green test fails on the old code), and the flake8 wording. |
| 8. Run book and design §5.7 | Met | `review-runbook.md` hard-codes `/home/kevin/...` as the Python path. |
| 9. Pis turnkey | Mostly | One provisioning recipe; identity and port matching only in `transport.py`; echo and fault checks run against simulated Pis. **HELLO validation is written twice**: `common/hw_link/relay.py:135-140` and `bringup.py:220-227`. The real-board fault checks are a checklist without scripts. |
| 10. Proposals | Partly | See the proposal problems below. |

**Proposal problems.** The inbox now holds 34 on this branch, plus 4 from PR #43.
- **Decision-number collisions between Codex's and this session's proposals:**
  - D033: `red-integration-plc-routing` and `red-test-plc-switch-routing`, which say the same
    thing;
  - D034: `phase6-integration-scope` and `authoritative-green-plc-programs`;
  - D035: `shared-neighbor-closures` and `pi-paths-share-one-implementation`.
- **`20261022-1135-phase6-integration-scope`** records a plan, which `AGENTS.md` forbids in
  truth. It also overlaps D032 and D035.
- **`shared-neighbor-closures`** gives only the option text "Approve…" as provenance.
- Proposals may be edited only where Kevin asks; leave renumbering and withdrawal to him.

**Suites on the cloud host.** Baseline at `b81e213` in brackets.

| Suite | Result |
| --- | --- |
| Harness + utils | 261 passed, 4 failed (260) |
| `common/hw_link` | 44 (33) |
| Track Controller HW | 89 (80) |
| CTC Office | 261 |
| Track Controller SW | 213 |
| Track Model | 312 (310) |
| Train Controller HW | 23, with `main.py --check` clean |
| Train Controller SW | 24 |
| Train Model | 878, plus the known flaky UI test |
| Opt-in | 44 passed, 5 failed |

What failed:
- **Harness + utils (4):**
  - the two review scenarios, on `TIME_SLIPPED`;
  - `test_run_is_clean`, which failed in 4 of 11 runs at HEAD against 0 of 10 at `b81e213`.
    This hints at a small 10x slowdown on weak hosts, not proven;
  - a `test_clock_driver` rapid-speed-change test, which passes alone.
- **Opt-in (5):** the 3 expected multi-train failures and the 2 review scenarios.
- **flake8:** passes only with N815 ignored, as before. `common/hw_link/tests/test_bringup.py:124-139`
  adds new N802 warnings.
- **mypy:** `common/hw_link` is clean.

#### Follow-up recorded 2026-10-24

Kevin's answers and all CTC and other module-owner findings now live together in
[Module owner review](module-owner-review.md). Use that file for the current owner review
queue and [Phase 7 prompt](#phase-7-prompt) for the next build phase. The questions below
are the historical October 22 handover, not a request to repeat answered questions.

Kevin confirmed he approved neighbor `CLOSED_n` before implementation; Braden has not
accepted it. Functional review is 1x with `TIME_SLIPPED` retained as a fault; 10x is a
separate measurement. The provisional review host is `kevin-framework` (Kevin: "for now
the review will happen on this machine"). Kevin approved the HELLO/helper, reviewer and
portable-path cleanup for Phase 7, and the human collision-resolution recommendation.
No implementation or fresh suite results are claimed by this documentation update.

#### Current follow-up, 2026-10-25

Kevin answered **"No updates—continue owner diagnostics"**. Phase 7 verification
is complete; the [independent receipt](archive/handover/integration-handover-phase-7.md#independent-phase-7-verification-receipt)
records the follow-up results and the recovery-time loss of temporary logs.
The [shared owner-review queue](module-owner-review.md) remains the current source
for issues and requested decisions. The [Phase 8 prompt](#phase-8-prompt) scopes
bounded owner diagnostics and reusable diagnostic coverage; it authorizes no
owner-policy changes. No new owner answers or working-Pi reports were supplied.
The questions below remain historical context; use the shared queue for current action.

#### Historical open questions for Kevin (2026-10-22)

1. Did you approve the neighbour `CLOSED_n` core input before it was written? Does Braden
   accept the change to his `wayside.py`?
2. Should the review run at 1x? Or should `TIME_SLIPPED` stop counting as a fault in the review
   tests? Which machine will the review use?
3. How should the proposal collisions be settled: D033 (keep one), D034 (withdraw the scope
   proposal as a plan?), D035 (renumber)?
4. The CTC Office questions for its owner:
   - Red allows only one train because of its zone rule;
   - Green with 3 trains stalls at 65/64;
   - the follower at 76.

   The "2+ trains" requirement (D032) depends on these.
5. Should the duplicate HELLO validation be folded into one helper? Should
   `TrackCtrlHw/CHANGELOG.md` name Braden explicitly as reviewer? Should the run book drop
   the hard-coded `/home/kevin` path?
6. Still open from earlier:
   - removing the SW vital layer (Harry);
   - Braden's real Red programs;
   - the Red block-9 reading;
   - the cross-wayside "missing counts as clear" rule;
   - the 38 pending proposals awaiting human promotion.

## Next session prompt

Source: archive/handover/integration-next-session-prompt.md

### Prompt for the next integration session

Paste everything below the line into a new session on branch `claude/quirky-fermi-sickg4`.

---

You are continuing the Track Overflow system integration on branch
`claude/quirky-fermi-sickg4` (never change branches; no PR unless I ask). Phases 0 to 4 are
built. The Iteration 3 scenario (dispatch a train from the yard to a Green station) runs end
to end, and as of 2026-10-21 a Green train also completes the full round trip and is retired
at 57.

#### How you work

- You are the **orchestrator only**. Every piece of legwork (reading code, editing, testing,
  measuring, writing documents) goes to subagents: model `opus`, effort `medium`. You plan,
  write their prompts, review and validate what they report (check their commits'
  `git show --stat`, re-run the key tests yourself), and report to me.
- Several agents may run at once in the one working tree. AGENTS.md forbids git worktrees for
  agents, so give each agent a disjoint set of files, and tell every agent: stage explicit
  paths only (never `git add -A`), check `git diff --cached --stat` before committing, never
  touch another agent's uncommitted changes, wait and retry if `.git/index.lock` exists.
- Every commit message ends with the two attribution lines this session's system reminder
  gives. No model identifiers in repository files. Push with
  `git push -u origin claude/quirky-fermi-sickg4`, retrying only on network errors.
- **No UI changes** unless I ask for one by name (my rule of 2026-10-21).
- Follow AGENTS.md exactly: session-start steps (fetch `truth`, read `truth/INDEX.md`,
  toolchain check, report date/time/machine/OS, check this branch's inbox), truth is read with
  `git show` only, proposals only from my decisions or documents, promotion is human-only.
- Python with the toolchain: create a venv in the scratchpad if none exists
  (`pip install "PySide6>=6.11" "pyinstaller>=6.22.2" pytest mypy flake8 pep8-naming`), and run
  Qt tests with `QT_QPA_PLATFORM=offscreen`.

#### Read first

1. `AGENTS.md`.
2. `documents/integration-handover.md#phase-4` and `documents/integration-handover.md#phase-3`
   (as built, open questions, commit tables).
3. `documents/system-integration-design.md` v0.12: §1.4 rulings (R83 to R90 are mine of
   2026-10-21), §1.5 open questions, §5.4 and §5.5, §6 gaps.
4. `common/harness/README.md`.

#### First task: a summary of all changes

Before any new work, have a subagent produce a **summary of every change on this branch
since `c311800`** (the last commit before Phase 3), and give it to me. Group it by area:
harness, CTC Office, Track Controller SW, Track Model, Train Model, Train Controller,
utils, documents, truth proposals. For each item give what changed, why (the ruling or
decision), the commit hashes, and the tests that cover it. Then list every module change made
for an owner to review (Track Controller starter rules and PLC inputs `SUG_n`/`REV_s`, the
switch dialog rename, CTC next-block suggestion, train events, return to yard, harness clock,
Train Controller engine-failure rule) and every open question with its owner. Validate the
summary against `git log --stat c311800..HEAD` before you pass it on. Put it in
`documents/integration-summary.md`, commit, push, and show it to me.

#### Then, in this order

1. **Small loose ends from 2026-10-21:**
   - The `ReturnToYardTest` docstring in `common/harness/tests/test_harness_train_loop.py`
     still says it fails at block 93. It passes since `460579b` (5/5, about 2 min, only with
     `TRACK_OVERFLOW_ROUND_TRIP=1`). Fix the docstring.
   - Record in the design document and the Phase 4 handover:
     - the round trip is unblocked;
     - Q-P4-8 is resolved by `460579b`;
     - the engine-failure rule as built: never within 0.05 m/s of target; a steady fall of
       more than 0.05 m/s over 6 s, with power commanded and no brake commanded or
       reported.
   - Record its two known limits:
     - a train at a stand with a dead engine is not flagged;
     - a heavily loaded train that cannot hold speed on Green 7's 5 % grade is flagged.
2. **Ask me** (do not decide):
   - The engine detector adds a "steady fall" test on top of my three rules. A straight-line
     check stops the grade sag at Green 7 (about 0.51 m/s, recovered in about 3 s) from
     latching. Do I accept it? See `Train-Ctrl_HW/OPEN_ISSUES.md` #26 and the proposal
     `truth/_inbox/claude/quirky-fermi-sickg4/20261021-1536-engine-failure-detection.md`.
   - Should a `--stubs-only` window run keep pressing Run by itself (the stub CTC has no
     window), or need `--auto-run` too?
   - Present the 18 proposals in `truth/_inbox/claude/quirky-fermi-sickg4/` for review.
     Promotion is mine.
3. **Owner questions to put to me for relay**, still open:
   - **Harry Tye:**
     - keep the new starter switch rule, `SUG_n`/`REV_s`, and switch 28 standing reverse
       at rest?
     - should the vital switch lock cover the points block, or move to it?
     - a cross-wayside occupancy input?
   - **Landis:** does the two-way zone keep a follower off 75/76 while a train stands on 77
     bound for 101?
   - **Track Model owner:**
     - the ticket sales rate (Q-P4-7);
     - switch naming by point versus truth's listed-on block (Phase 3 Q3);
     - bug B1 (light ahead);
     - D026 heaters, with no rule stated (Q6).
   - Phase 3 Q5 (Red `75-yard` normal leg), Q8, Q9, Q10, Q11 and Q12, as listed in the
     Phase 3 handover.
4. **Phase 5**, once I say go. Its scope:
   - the Red Line on the Track Controller HW and the Train Controller HW, on Raspberry Pis
     over USB serial (CDC-ACM, D027), one Pi per hardware module, their UIs on the host
     (D021);
   - the Red wayside data (R34) with `next_blocks` (R78);
   - measuring the USB round trip (G-CLK-6);
   - packaging as one executable, and the build on Windows.

   Known Red issues:
   - every Red block is two-way, so the starter switches stay normal there;
   - the `75-yard` normal leg disagrees between modules (Q5);
   - `merge_ctc_inputs` is already written for a second Track Controller.

   Plan Phase 5 with me before building it.

When agents report, review before relaying: say what you verified yourself and what you only
have from their report.
