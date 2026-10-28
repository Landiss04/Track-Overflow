# Integration handover: Phase 3 to Phase 4

Written 2026-10-20 at the end of the session that built Phase 3, on branch
`claude/quirky-fermi-sickg4`. It is for whoever picks the work up next, person or agent.
It says what Phase 3 built, how it was validated, the open questions, and how to begin
Phase 4. The plan and the history are in `documents/system-integration-design.md`
(v0.10; Phase 3 is section 5.4); how a module joins the harness is in
`common/harness/README.md`.

The first session stopped partway through validation, at Kevin Schillinger's request.
A second session on the same day finished it: the measurement runs, the frozen build
and the document updates (section 2).

## 1. Phase 3 as built

Phase 3 in the plan: "Track Controller SW on Green: commanded speed and authority per
block, switches, signals, readiness, failures."

### What runs

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

### Changed, by file

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

### Behaviours worth knowing

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

## 2. Validation: done, and left to finish

### Done in the first session

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

### Finished in the second session

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

## 3. Open questions

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

## 4. Phase 4: beginning

Phase 4 in the plan: "CTC Office: dispatch from the yard, suggestions, occupancy, ticket
sales and clock control. The Iteration 3 scenario on Green: dispatch a train from the
yard to a station (2026-11-12)."

### What is ready for it

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

### What it lacks (from the code, 2026-10-20)

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

### Plan

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

### Risks

- The CTC Office's window is the heaviest UI; at 10x its redraw may hold up replies. The
  Track Model needed a deferred, throttled redraw (`WINDOW_REFRESH_MS`). Expect to do
  the same.
- Clock ownership moves from the CTC Office window to the harness. Its clock bridge and
  clock link must stand down under the harness without breaking standalone use.
- Release and retire timing against occupancy latency: test the too-early failure
  inference with real tick timing.
