# Integration change summary

**Scope:** `c311800` exclusive through `cf4edf582cea499eae8e5f9e8f7fcae53d5474a1` inclusive, on `claude/quirky-fermi-sickg4`: 23 commits and 83 net changed paths. Prepared 2026-10-21. This is a review of implementation and recorded decisions, not a truth entry.

Phases 3 and 4 replace the scripted wayside and then the scripted CTC Office with the real Green Track Controller SW and CTC Office. The system runs five real module processes and two hardware stubs. The Green dispatch-to-GLENBURY scenario works, and the later engine-detector repair in `460579b` unblocks the complete Green round trip and retirement at block 57. At the baseline endpoint the rule's additional steady-fall criterion still needed Kevin's acceptance. He subsequently accepted it as built on 2026-10-21; the post-summary decisions below record that later decision separately from the audited range.

The baseline itself already enforced the 45 s dwell (`c311800`); that implementation and Phases 0–2 are context, not new changes in this range. Existing UI changes are documented below for review. This summary changes no UI, truth entry, module code, handover, design document, or test docstring.

## Evidence and verification

The audit read the complete `git log --stat c311800..cf4edf5`, per-area diffs, both phase handovers, design v0.12 §§1.4–1.5, 5.4–5.5 and relevant gaps, and the harness README. The commit and path accounting at the end preserves intermediate additions/deletions that a net diff hides. The authoritative `origin/truth` was freshly fetched for this session; relevant decisions were read with `git show`, never copied into the checkout. D005 requires direct producer-to-consumer mapping, one harness driver and process ownership, and exactly-once output forwarding; D017 supplies fixed-step unwrapped shared time and reply synchronization; D022 supplies release/retirement ownership and events; D021 assigns Green to SW and Red to HW. R references below mean rulings recorded in the design/handovers; proposals remain proposals until human promotion.

**Current session environment:** kevin-framework, Ubuntu 26.04.1 LTS, checked 2026-10-21 11:46 EDT (America/New_York). `/home/kevin/ECE/Trains/.venv` passes the truth toolchain minima: Python 3.14.4, PySide6 6.11.2, PyInstaller 6.22.2.

**Fresh checks independently rerun by the orchestrator**, with `QT_QPA_PLATFORM=offscreen`:

| Targeted checks | Result | Scope of evidence |
| --- | --- | --- |
| CTC Office: `tests/test_ctc_next_block.py`, `test_ctc_train_events.py`, `test_ctc_scheduler.py`, `test_module_process.py` | 67 passed, 40 subtests, 2.64 s | Next-block suggestions, release/retirement/return, shared-time scheduling and process boundary |
| Track Controller SW: `tests/test_starter_switches.py`, `test_boundary.py`, `test_module_process.py`, `test_layout.py` | 89 passed, 4 subtests, 1.51 s | Starter inputs/routing, separation, process and layout |
| Train Controller: `Train-Ctrl_HW/tests/test_engine_detection.py`, `test_harness_driven.py` | 23 passed, 18 subtests, 0.18 s | Engine detection, harness drive and lower-limit braking; three sandbox stream-fd warnings were emitted without test failure |
| `common/harness/tests/test_harness_edges.py`, `test_harness_faults.py`, `test_harness_system.py` | 74 passed, 4 subtests, 13.26 s | Direct mappings/decoders, protocol recovery and real-process scenario |
| Opt-in `common/harness/tests/test_harness_train_loop.py::ReturnToYardTest` (`TRACK_OVERFLOW_ROUND_TRIP=1`) | 5 passed, 38.95 s | Complete Green round trip and retirement; faster than historical ~140 s in the prior environment |

Total fresh targeted verification is **258 passed, 66 subtests**. This is not a whole-suite rerun.

The CTC/Track audit agent also attempted their full unittest suites: CTC ran 259 tests with 22 failures during socket setup, and Track Controller SW ran 213 with 30 failures during socket setup, because the sandbox denied QLocalServer listen. Those attempts are not full-suite green results and do not establish product regressions. Historical suite/build/budget results below are attributed to the committed handovers or commit messages, not presented as this session's measurements. Concurrent uncommitted `TrainModel/README.md`, `TrainModel/train_model/app.py`, `ui/aspect_lock.py`, `common/harness/tests/adversarial_probe.py` and `documents/central-harness-adversarial-2026-10-20.md` belong to parallel work and are outside this summary's committed scope.

## Harness

| Change and effect | Why / decision or implementation rationale | Commits | Covering tests and evidence |
| --- | --- | --- | --- |
| Register and launch the real Green Track Controller SW; route its inputs/outputs and readiness. Add opt-in `--load-starters` to launch/measurement. Delete scripted `wayside_script.py`. Introduce temporary `ctc_script.py` to release trains and provide current/next-block suggestions, readiness gating and dwell until the real CTC Office joins. | D005/D017 process boundaries and prior-tick inputs; R44 person loads PLCs, R48 wayside has no train ID, R49 next-block preload, R70–R71 wayside readiness, R77 Green SW; D022 release and D024 engineer gains. Wayside loading gates dispatch, not the system clock. | `1a9ce27` | `test_harness_edges.py::{TrackDevicesTest,WaysideEdgesTest,EdgeContractTest,SystemEdgesTest}`; `test_harness_train_loop.py::{StationStopTest,ReadinessTest,SwitchAndLightTest,FailureTest,EmergencyBrakeTest}`; `test_harness_system.py::{SystemTest,NotReadyTest}`; CLI/window test. Historical Phase 3 validation in handover. |
| Add `track_devices.py` and four direct JSON mappings in `wayside_edges.py`: CTC suggestions→wayside; occupancy/device readback→wayside; per-block commands and devices→Track Model; wayside occupancy/device/readiness reports→CTC. Drop train IDs before wayside, independently take the lower speed and authority for duplicate block suggestions, report failed blocks occupied, and send no heater command. Map listed-on switch ID to Track Model point, and each light through its switch, from layout files. | D005 direct mappings, R48/R49, R33/R69 failed occupancy and D026 heater ownership. Naming/light discrepancies are mapped for integration, not declared resolved. Green listed-ID/point/light mappings: 12/13/14, 28/28/27, 58/57/56, 62/63/64, 76/77/78, 85/85/84. | `1a9ce27` | `TrackDevicesTest` compares both real layout readers for Green and Red; `EdgeContractTest` feeds mappings into receiving modules' own decoders. Loop switch/light and failure scenarios. |
| Replace temporary `ScriptedCtc` with the real CTC process and events; add CTC to `WIRED_MODULES`; pass `--dispatch`; measure a dispatch to Green 73. Read readiness directly from fresh wayside outputs. Add `merge_ctc_inputs` to concatenate Track Controller report lists for eventual Red HW. Remove `ctc_script.py` and its tests. | Phase 4/D005/D022/D025. Same previous-tick snapshot semantics, now using CTC's own boundary. Red merger is preparation, not HW integration. | `163fdd0` | `test_harness_edges.py::{CtcEdgesTest,SystemEdgesTest,EdgeContractTest}`; full five-module JSON loop and real-process `SystemTest`/`NotReadyTest`; window dispatch option. |
| Add Track Model→CTC ticket edge and `TicketSales` acknowledgment buffer: whole-number station counts only; omit zero sellers; retain sales until CTC returns accepted outputs for the tick sent; resend after refused/missed ticks; repeated Track Model outputs never count twice. | R52 station-count deltas exactly once; D005 forwarding and D023 no Blue stations. This is transport accounting, not a decision on ticket generation rate. | `163fdd0` | `SystemEdgesTest::test_each_ticket_sale_reaches_the_ctc_office_once`; `EdgeContractTest::test_the_ctc_office_takes_the_track_models_sales`; `CtcEdgesTest`; station-loop ticket totals. |
| Harden request/reply handling: log `INPUTS_FAILED` for unsendable edge inputs while other modules still step; reject replies whose tick mismatches even if request ID matches; preserve links and later good frames after an oversized frame. | Reproduced protocol defects; repairs support D005/D017/R19. No new normative decision inferred. | `d6066e2` | `test_harness_faults.py::{OverflowingNumberTest,UnencodableInputsTest,InvalidUnicodeTest,FramingTest,WrongTickTest}`; wrong-tick case accepts a later good reply. Utils tests below cover the shared framing/encoding implementation. |
| Use atomic `EventLog.create` and print its actual filename. | Prevent same-second/concurrent launches overwriting a log; implementation repair. | `122b279` | `utils/tests/test_event_log_names.py::SameSecondTest`, including six concurrent processes. |
| Historical operator-window fixes retain module-row identity so Show window keeps keyboard focus during status changes; clear selected event and close inspector when that event rolls out of the bounded list. | Repair existing focus/selection bugs; no new user ruling recorded. | `bab5599` | `test_harness_window_state.py::HarnessWindowStateTest::test_focus_and_selection_probe` launches `window_state_probe.py`. |
| Make startup-timeout fault test deterministic: 2 s timeout, deliberately delayed Train Model 4 s, assert only it is named. Extend real-system CLI/window run from 2 s to 8 s, retain 1 s stubs run, allow run duration +30 s timeout. | Remove test races: ordinary child startup could exceed the old 0.3 s threshold or consume the whole 2 s run. Implementation/test rationale only. | `428852b`, `ed3fd91` | `test_harness_console.py::ConsoleFaultRunTest::test_startup_timeout_names_the_loading_module`; `test_harness_window.py::HarnessWindowTest::test_cli_modes_keep_options_and_exit_cleanly`. Commit `428852b` records four parallel and five sequential passes (historical). |
| Add opt-in complete Green round-trip tests: scheduled stop, whole route, switch setting/holding, retirement at 57, no emergency/pickup failure. Initially exposed engine-detector failure at Green 93; later passes after detector repair. | R86/Phase 3 Q7 starter routing repair plus D022 end-to-end lifecycle coverage. | `234c353`; unblocked by `460579b` | `test_harness_train_loop.py::ReturnToYardTest` (five tests), enabled by `TRACK_OVERFLOW_ROUND_TRIP=1`; see verification and Train Controller section. |
| Ordinary window runs wait for dispatcher Run; add `--auto-run`. Headless, stubs-only, and explicit auto-run pass `--run-on-ready`; measure remains automatic. Suppress shutdown-only `TIME_SLIPPED` events while preserving actual dropped-backlog accounting. | R83 Kevin's answer to Q-P4-1; shutdown backlog is not a runtime timing fault. The exception was still undecided at the baseline endpoint; Kevin subsequently explicitly kept it on 2026-10-21 (post-summary R92). | `68fcfa7` | `test_harness_window.py::AutoRunTest` (five cases: normal window, auto-run, headless, stubs, passthrough); `test_harness_faults.py::StopWithTicksOwedTest::test_stopping_logs_no_time_slipped`. Historical harness result 156 passed, five opt-in skips. |

Historical Phase 3 validation recorded edges 55, loop 21, system 11 and Track Controller SW 194 tests. Phase 4 at `b65fd26` recorded harness 150 passed with 495 subtests, utils 82 with 37 subtests, CTC 244 and Track Controller SW 194. Later handover records CTC 259, Track Controller SW 213, and Train Controller harness suite 12. These counts refer to different historical revisions, not one current aggregate.

Historical offscreen Phase 4 budget (`python -m common.harness.measure --system --seconds 15`): five real modules and two stubs reached 9.99–10.00x, mean round trip 5.14–5.82 ms, p95 about 16–17 ms, ready in 1.02–1.41 s, with no late reply or slipped tick. Linux one-folder frozen smoke runs found CTC QML/layouts, dispatched and shut down all seven children cleanly. In frozen CLI smoke without engineer gains the train stayed at the exit, as D024 requires. These do not verify Windows, visible display load, USB timing or multiple-train budget.

## CTC Office

| Change and effect | Why / ruling | Commits | Covering tests |
| --- | --- | --- | --- |
| Emit at most two suggestions per train: current block and, while authority ≥1, next route block with authority one less and speed recomputed for its own limit/stopping distance. Keep head suggestion last for existing displays keyed by train. Update boundary/wire documentation and fixtures across authority, boundary, collisions, safety, scheduler, tracking, host and socket tests. | Kevin's direct Oct 20 instruction “fix Q13 and Q14 in the CTC”; R49/current truth suggested-speed and track-signal. Prevent new-block zero signal/pickup latch through harness latency. No lower-limit-ahead cap added (R87). | `9c440d6` | `tests/test_ctc_next_block.py::NextBlockTest`: two suggestions, own-block speed, authority-one→next-zero, no next at zero authority, limits/exclusive authority, two trains never name one block; `BlockChangeLoopTest::test_authority_never_falls_from_two_blocks_to_none`. |
| Add `new_trains` (ID+line) and `retired_trains` (ID) step events and JSON tuple→list conversion. Track explicit releases, one per line, most late first, only with ready/clear/unreserved exit and scheduler permission. Hold exit claim until observed; tracker recognizes released trains only. Retire at Green 57/Red 9 once stopped at zero destination authority, then observe clear before completing schedule. Behavior is implemented in `ctc/model.py`; `scheduler.py` and `tracking.py` changes in this commit are docstrings only. Snapshots may repeat for display; harness consumes each tick once. | Same Q14 direction; R35/R46/R47 and D022 CTC creates at release, yard lifecycle, exact-once events. | `9c440d6` | `tests/test_ctc_train_events.py::{ReleaseTest,RetireTest,WireTest}` (10/3/3 tests; wire shape, omitted-events default, roster application); updated scheduler/tracking/collision regressions. |
| Add harness module process and `HarnessClockBridge`; host can disable test server, expose module, start history at supplied time, step and refresh separately. Decode own JSON strictly; malformed keys/values/dt reject without mutation. Run/Pause/speed send `STATE` immediately, defer before READY, scripted speed change after reply; repaint after reply no faster than 200 ms. Add run-on-ready, speedup-at-tick, dispatch and schedule test/demo options; resolve source/bundle layouts. Correct existing host mypy bool conversion. | D005 sole harness driver, D017 shared clock, D025 test UI removed from integrated path. Refresh timing is an implementation choice to protect replies. | `97a2fd1` | `tests/test_module_process.py::{ProcessTest,TestOptionsTest}` (8+5): shape/no test link, rejection atomicity, sales once, header and paused 1x, STATE ordering, redraw ordering and test-option readiness. Real-process harness system and historical frozen smoke. |
| Historical test-UI outputs label next-block rows `next_block`, `next_suggested_speed`, `next_authority`; host suggestion key retains current block. README explains two suggestions and harness operation. | Disambiguate duplicate output rows; R89 later directs no further UI changes. | `97a2fd1` | Existing host/test-process coverage and historical QML launch; no dedicated visual/button assertion identified. |
| Add manual `return_to_yard` action and requested Return to yard button. Route through dispatch to Green 57/Red 9 with existing safety/readiness checks; reject non-track or scheduled trains; subsequent order/cancel withdraws it; existing retirement path emits once. | R66/D022 and Kevin's Oct 21 “yes add a button” (R85). Historical explicitly authorized UI addition. | `4cc873b` | `tests/test_ctc_train_events.py::ReturnToYardTest` (eight: contract, retirement once, Red 9, non-track, safety atomicity, readiness, scheduled refusal, later-order withdrawal); `tests/test_ctc_host.py` return-to-yard host action. |
| Accept optional absolute `sim_time_s` in `CtcOffice.step`; validate finite increasing time and derive elapsed from 18000. Harness host passes STEP time. Standalone still accumulates dt when no absolute time supplied. | R88 “use the harness clock”/D017: a refused or missed tick must not permanently move schedules behind shared time. | `4cc873b` | `tests/test_ctc_scheduler.py::HarnessTimeTest` (four); `tests/test_module_process.py::HarnessTimeTest` (two: refused/missed time and schedule on harness time). |

Owner review: **Landis** should review next-block suggestions, explicit release/retirement events and tracker/scheduler changes, integrated process and immediate STATE push (G-CLK-3), return-to-yard action and shared-time schedule adoption. Implementation/testing does not constitute his ratification.

## Track Controller SW

| Change and effect | Why / ruling | Commits | Covering tests |
| --- | --- | --- | --- |
| Add Green-only six-wayside harness process using own wire types and `ModuleLink`; use STEP simulation time; reject explicit input time override or malformed inputs atomically. No test server; hide windows on close; load starter PLC only by opt-in. State can select lines (standalone still loads both), layout path supports frozen bundle. Register launcher. Header infers pause after steps stop; cannot display 10x. | D005/D017, R44 manual program loading, R77 Green SW; readiness gates dispatch, not clock. | `1a9ce27` | `tests/test_module_process.py::ProcessTest` six cases: Green alone, not-ready until loaded, pass suggestions after startup, STEP time, atomic bad-input refusal, header running while steps arrive. Real-process harness system/window; historical frozen smoke. |
| Starter authority separation now blocks only when the block and an adjacent block are both occupied. Empty preloaded next block retains its suggestion rather than losing it to own train's occupancy. Two adjacent occupied trains still hold each other. | R49/Phase 3 Q1: old rule prevents block transitions and contradicts next-block preload. Explicit owner review remains. | `1a9ce27` | `tests/test_boundary.py::StarterSeparation::{test_a_preloaded_next_block_passes_its_suggestion,test_a_train_beside_another_is_held}`; updated `test_world.py`; harness route loop/system. |
| Historical switch dialog signal rename `applied`/`released`→`switchApplied`/`switchReleased`, with ProgramView/StatusView handlers. | Remove Qt Dialog `applied()` name collision/warning; existing behavior had still worked. Phase 3 Q2 owner acceptance remains. | `1a9ce27` | Historical QML/process/frozen launch smoke covers load; no dedicated automatic button-behavior test identified. |
| Generate starter switch routes using new `SUG_n` (suggestion present even if zero) and `REV_s` (last driven position, not delayed readback) inputs and complete immutable layout direction chart. Detect facing approach before point occupancy, route trailing one-way legs, preload where vital lock requires it, hold occupied/conflicting points, normal maintenance unless held. Green 28 rests reverse for arrival from unseen 150; 12/76/85 route dynamically, 58/62 remain normal because retirement at 57 needs no physical yard entry. Existing PLC programs and vital-layer code unchanged. | Kevin's “fix” (R86, Phase 3 Q7) makes complete Green route possible. Individual starter/vital/follower choices remain owner decisions, not new accepted contract facts. | `234c353` | `tests/test_starter_switches.py` 18 tests: AtRest (2), Switch76 (6), Switch28 (2), Switch12 (3), Switch85 (1), YardSwitches (1), Maintenance (1), InputImage (2); `test_layout.py::RealLayoutTests::test_the_direction_of_travel_is_read_and_shared_by_the_line` plus bad-`next_blocks` cases within existing `RefusalTests::test_block_errors`; five opt-in harness round-trip cases. |

Owner review: **Harry Tye** and Track Controller SW owners must review separation, switch rule, new `SUG_n`/`REV_s`, Green 28 at rest, switch-dialog rename and SW/HW interface/PLC vocabulary. **Harry and Landis** retain the vital-lock points-block question, cross-wayside occupancy input and follower/two-way-zone safety review. No Track Controller HW executable or Red data changed in this range.

## Track Model

No executable or test file changed in this range. `91a5afd` updates [README](../TrackModel/README.md) and [INTEGRATION](../TrackModel/INTEGRATION.md): real Green SW wayside commands/readback replace the scripted wayside; harness maps listed switch IDs to points and lights; no heater commands are sent. This reconciles Phase 3 docs under D005/R49/D026. Existing mappings are covered by harness `TrackDevicesTest`, `EdgeContractTest`, switch/light and failure loops; the historical handover reports Track Model 309 OK, not a fresh run here.

The INTEGRATION text still refers to temporary `ctc_script.py`, removed in Phase 4. This is stale documentation, not the current running topology. Switch naming, light-ahead bug B1, Red normal-leg disagreement, heater rule and ticket generation rate remain owner questions below; none is claimed fixed by these documentation changes.

## Train Model

No runtime or test file changed in this range. `91a5afd` updates only [docs/open-issues.md](../TrainModel/docs/open-issues.md): Phase 3 takes real Green speed/authority from Track Controller SW and retains legacy catalog adapters off the running path. Its scripted-CTC wording predates Phase 4. This is D005/R49 wiring-status documentation; real Train Model participation is covered by the station/route harness loops and system tests. Phase 3 handover's historical Train Model result is 855 passed, 13 skipped; no fresh Train Model full-suite result is claimed.

Earlier Train Model brake/beacon/time/arrival work described in design reconciliation is outside this exclusive range. Parallel uncommitted Train Model UI/readme work is also outside it and has not been edited or included.

## Train Controller

The active logical Green `train-controller-sw` process imports **`Train-Ctrl_HW/train_ctrl/module_process.py`** via `track_overflow.py`; no `Train-Ctrl_SW` directory exists. Thus the detector repair in the HW-named package changes the active Green SW process. Logical Red/HW remains a stub until Phase 5.

| Change and effect | Why / ruling | Commits | Covering tests |
| --- | --- | --- | --- |
| Add two tests of existing behavior on entering a slower block: power zero and service brake on the first tick, held until under the new limit, without emergency brake. No controller logic change in this commit. | Kevin's Oct 21 R87/Q-P4-4: CTC does not cap ahead; controller slows after entering block. Historical example enters Green 67 at 17.9 m/s and falls below 11.1 m/s after 4.8 s/about 70 m. | `0305d05` | `tests/test_harness_driven.py::LowerLimitAheadTest::{test_brakes_on_the_first_tick_in_the_slower_block,test_holds_the_service_brake_until_under_the_limit}`. |
| Replace failure inference from “speed not rising for 2 s” with falling-speed detection. Never latch within 0.05 m/s target band. Require commanded power and no service/emergency brake commanded or reported anywhere in the 6 s window, and fall >0.05 m/s. Reset window on no power/braking and clear_failure. Use half-second means and require each mean within 10% of total fall of the straight first-to-last line. | Kevin's three rules: never flag holding target; flag falling speed with power and no brake throughout; use longer than 2 s. Exact 6 s/0.05 thresholds are implementation choices. **At the baseline endpoint, the extra straight-line/steady-fall check was an unaccepted implementation choice** (subsequently accepted by Kevin on 2026-10-21, R91), avoiding a healthy Green 7 grade-entry sag (~0.51 m/s recovering in ~3 s). | `460579b` | `tests/test_engine_detection.py::EngineDetectionTest` 11 cases: longer window, steady uphill target, entering grade, failed engine flat/uphill/accelerating, any brake in window, brake then pulling, driver release, noise, steady below-target. `ReturnToYardTest` five route cases now pass (historical source and fresh status in verification). |
| Toy plant `ControllerCore._plant()` in `control.py` applies rolling resistance when engine or brake failure is injected; `constants.py` supplies its resistance constant. Update self-check cruise to expect eventual engine detection under resistance; revise CHANGELOG, HARNESS_INTEGRATION, OPEN_ISSUES and REQUIREMENTS. This does not change Train Model physics. | Dead engine must visibly slow in the toy plant, consistent with Train Model's documented rolling resistance. Implementation/test realism, not a new physics decision. | `460579b` | Engine detector tests use their own custom Plant, not `ControllerCore._plant()`. The historical self-check covers the actual toy plant; entrypoint is `main.py --check` from `Train-Ctrl_HW` (running `check.py` directly does not execute it). No fresh self-check result claimed here. |

**Q-P4-8/G-NEW-6 is resolved by `460579b`:** healthy steady speed at Green 93 no longer latches, and the full Green round trip retires at 57. At the baseline endpoint, design v0.12, the Phase 4 handover, harness README and `ReturnToYardTest` docstring still said it failed. The subsequent authorized cleanup is now complete in `55dac4f` and `b6c6eb2`, outside this summary's audited range.

Two known limits remain: a dead-engine train at a stand is not flagged because speed does not fall; a heavily loaded train physically unable to hold speed on Green 7's 5% grade is flagged. These are recorded limits in OPEN_ISSUES #26 and the handoff, not separately proven by dedicated assertions in `EngineDetectionTest`. **Train Controller owners (unassigned)** review the detector; **Kevin accepted the additional steady-fall criterion as built on 2026-10-21 (post-summary R91)**. The earlier proposal deliberately leaves the exact window/threshold/band/shape unspecified; a new full-entry proposal records his later acceptance without editing that earlier file.

## Utils

| Change and effect | Why / implementation rationale | Commits | Covering tests |
| --- | --- | --- | --- |
| Decode rejects nonfinite/overflowing numbers (including syntactically valid `1e999`), integers beyond double range, invalid raw UTF-8 and lone surrogate text in keys/values. Encode rejects nonfinite floats/lone-surrogate text and emits UTF-8; it does not impose the decoder’s integer-range bound. | Reproduced malformed-message defects could silently strand a tick; repairs support existing D005 synchronization, not a new decision. | `d6066e2` | `utils/tests/test_protocol_faults.py::{NumberRangeTest,UnicodeTest}` (4+5); harness overflow/Unicode cases. |
| `LineBuffer` reports per-line errors, discards one oversized frame through its newline exactly once, and preserves surrounding/following valid frames across partial chunks. Module link logs/skips bad frames without disconnecting; unsendable outputs become `REJECTED`; malformed rejection text is escaped. EventLog uses `errors=backslashreplace` so logging bad text cannot strand a tick. | Frame recovery and every-request reply guarantee; implementation defect repair. | `d6066e2` | `test_protocol_faults.py::{FramingTest,ModuleRepliesTest,EventLogTextTest}` (2+3+1), two updated `LineBuffer` cases in `test_harness_protocol.py`, companion harness framing/wrong-tick/inputs cases. |
| `EventLog.create(folder, started)` atomically reserves with exclusive `x`: original `events-YYYYMMDD-HHMMSS.csv` for first run, `-2`, `-3`, etc. on clash. | Prevent same-second concurrent runs truncating each other's CSV. Existing one-log-per-run policy, implementation repair. | `122b279` | `utils/tests/test_event_log_names.py::SameSecondTest::{test_first_name_is_unchanged,test_second_run_gets_its_own_file,test_simultaneous_launches_never_share_a_file}` (six concurrent children). |

## Documents

| Logical change | Why / commits | Validation and limitations |
| --- | --- | --- |
| Create Phase 3 handover with per-file integration, validation, departures and owner questions; complete validation and promote design's Phase 3 as-built section/gaps/edge map; note CTC Q13/Q14 commit. Update harness README, Track Controller SW README/discrepancies, Track Model integration/readme and Train Model open issues. | Phase 3 handoff/status evidence; `1a9ce27`, `91a5afd`, `af6abf6`. No new truth inferred from implementation. | Source/diff audit and underlying tests above; historical Phase 3 budget/frozen smoke only. |
| Create Phase 4 handover and expand design/README with CTC process/edges, scenario, validation, faults, frozen recipe, questions and historical metrics. Mark Phase 3 CTC blockers resolved and startup race fixed. | Preserve integration review evidence; `b65fd26`, `a55b8b9`; CTC README also `97a2fd1`. | Linux offscreen frozen smoke reported in committed handover; Windows and visible UI performance remain unverified. No code test uniquely validates prose. |
| Record Kevin's Oct 21 R83–R90 rulings, return-to-yard/shared clock/starter implementation, lower-limit test and remaining questions; mark auto-run decision implemented and shutdown slip fixed. | Keep design v0.12 and handovers aligned with then-current work; `f32d81e`, `9f9b644`. | Cross-check cited commits/tests, not a new execution result. Later `460579b` makes round-trip failure status stale. |
| Update Train Controller change/requirements/open-issue/integration documents with new detector, toy plant and acceptance/limits. | Explain changed owner behavior; `460579b`. | Audit against constants/control/tests; rule acceptance was open at the baseline, then resolved by Kevin on 2026-10-21 (R91). |
| Add next-session prompt: summary first, then stale-status/docstring cleanup, ask Kevin about steady-fall and stubs auto-run, owner relay questions, and plan Phase 5 before implementation. | User-directed continuation instructions; `cf4edf5`. | Audited as source of task order. This summary does not perform later cleanup or authorize Phase 5. |

## Truth proposals

The **baseline inventory contains 18 proposals**, still awaiting human review. Sixteen were already present at baseline; only `66aa348` and `91e8c0a` add proposals in this range. Nothing was promoted, deleted, edited or pushed to `truth`. The target paths below describe proposed destinations, not authoritative facts. Each link is relative to this summary; provenance is summarized from its wrapper/entry.

| Proposal / heading | Target | Provenance | Present before exclusive baseline? / in-range commit |
| --- | --- | --- | --- |
| [track-controller-ready](../truth/_inbox/claude/quirky-fermi-sickg4/20261020-0234-track-controller-ready-roster.md) (`20261020-0234-track-controller-ready-roster.md`) | `truth/signals/track-controller-ready.md` | Kevin relayed Track Controller Oct 20 answers: ready iff DB+PLC loaded; whole roster reported from startup; supersedes prior loaded-by-hand proposal. | Yes; unchanged in this range |
| [harness-output-inspector](../truth/_inbox/claude/quirky-fermi-sickg4/20261020-0927-harness-output-inspector.md) (`20261020-0927-harness-output-inspector.md`) | `truth/decisions/harness-output-inspector.md` | Kevin Oct 20 harness-window implementation answers. | Yes; unchanged in this range |
| [harness-show-window](../truth/_inbox/claude/quirky-fermi-sickg4/20261020-0927-harness-show-window.md) (`20261020-0927-harness-show-window.md`) | `truth/decisions/harness-show-window.md` | Kevin Oct 20 harness-window implementation answers. | Yes; unchanged in this range |
| [harness-window-close](../truth/_inbox/claude/quirky-fermi-sickg4/20261020-0927-harness-window-close.md) (`20261020-0927-harness-window-close.md`) | `truth/decisions/harness-window-close.md` | Kevin Oct 20 harness-window implementation answers. | Yes; unchanged in this range |
| [harness-window-title](../truth/_inbox/claude/quirky-fermi-sickg4/20261020-0927-harness-window-title.md) (`20261020-0927-harness-window-title.md`) | `truth/decisions/harness-window-title.md` | Kevin Oct 20 harness-window implementation answers. | Yes; unchanged in this range |
| [D006-fixed-time-step](../truth/_inbox/claude/quirky-fermi-sickg4/20261020-1341-D006-fixed-time-step-sdd-review.md) (`20261020-1341-D006-fixed-time-step-sdd-review.md`) | `truth/decisions/D006-fixed-time-step.md` | Kevin Oct 20 SDD review; Train Model SDD v0.2 §4.9; direct documentation request. | Yes; unchanged in this range |
| [beacon](../truth/_inbox/claude/quirky-fermi-sickg4/20261020-1341-beacon-sdd-review.md) (`20261020-1341-beacon-sdd-review.md`) | `truth/signals/beacon.md` | Same SDD review; compact-array encoding selected in response, not attributed to old backend PDF. | Yes; unchanged in this range |
| [brake-state](../truth/_inbox/claude/quirky-fermi-sickg4/20261020-1341-brake-state-sdd-review.md) (`20261020-1341-brake-state-sdd-review.md`) | `truth/signals/brake-state.md` | Kevin Oct 20 SDD review; Train Model SDD v0.2 §4.9. | Yes; unchanged in this range |
| [brakes-apply-together](../truth/_inbox/claude/quirky-fermi-sickg4/20261020-1341-brakes-apply-together-sdd-review.md) (`20261020-1341-brakes-apply-together-sdd-review.md`) | `truth/arbitration/brakes-apply-together.md` | Kevin Oct 17 simultaneous application and Oct 20 SDD review; force summation selected in response. | Yes; unchanged in this range |
| [passengers-boarded](../truth/_inbox/claude/quirky-fermi-sickg4/20261020-1341-passengers-boarded-sdd-review.md) (`20261020-1341-passengers-boarded-sdd-review.md`) | `truth/signals/passengers-boarded.md` | Kevin Oct 20 SDD review; Train Model SDD v0.2 §4.9. | Yes; unchanged in this range |
| [D010-train-model-test-ui-boundary](../truth/_inbox/claude/quirky-fermi-sickg4/20261020-1342-D010-train-model-test-ui-boundary-sdd-review.md) (`20261020-1342-D010-train-model-test-ui-boundary-sdd-review.md`) | `truth/decisions/D010-train-model-test-ui-boundary.md` | Kevin Oct 1–6 boundary/test-UI assertions, plus Oct 20 SDD review. | Yes; unchanged in this range |
| [D017-shared-simulation-clock](../truth/_inbox/claude/quirky-fermi-sickg4/20261020-1342-D017-shared-simulation-clock-sdd-review.md) (`20261020-1342-D017-shared-simulation-clock-sdd-review.md`) | `truth/decisions/D017-shared-simulation-clock.md` | Landis Oct 1; Kevin Oct 2/16/20 shared-clock decisions and SDD review. | Yes; unchanged in this range |
| [track-signal](../truth/_inbox/claude/quirky-fermi-sickg4/20261020-1342-track-signal-sdd-review.md) (`20261020-1342-track-signal-sdd-review.md`) | `truth/signals/track-signal.md` | Backend Design §5.3; D013; Kevin Oct 16/20, CTC answers and SDD review. | Yes; unchanged in this range |
| [train-model](../truth/_inbox/claude/quirky-fermi-sickg4/20261020-1342-train-model-sdd-review.md) (`20261020-1342-train-model-sdd-review.md`) | `truth/modules/train-model.md` | Backend Design, instructor clarifications, Kevin Sept 30–Oct 20 boundary/physics/UI assertions and SDD review. | Yes; unchanged in this range |
| [train-position](../truth/_inbox/claude/quirky-fermi-sickg4/20261020-1342-train-position-sdd-review.md) (`20261020-1342-train-position-sdd-review.md`) | `truth/signals/train-position.md` | Backend Design §5.3/Interfaces supplied Sept 30; Kevin Oct 20 SDD review. | Yes; unchanged in this range |
| [D007-station-dwell](../truth/_inbox/claude/quirky-fermi-sickg4/20261020-1858-D007-dwell-scheduled-by-ctc-enforced-by-train-controller.md) (`20261020-1858-D007-dwell-scheduled-by-ctc-enforced-by-train-controller.md`) | `truth/decisions/D007-station-dwell.md` | Current D007 plus Kevin direct Oct 20: CTC schedules, Train Controller enforces, 45 s. | Yes; unchanged in this range |
| [lower-limit-ahead](../truth/_inbox/claude/quirky-fermi-sickg4/20261021-1445-lower-limit-ahead-train-controller-slows.md) (`20261021-1445-lower-limit-ahead-train-controller-slows.md`) | `truth/arbitration/lower-limit-ahead.md` | Kevin direct Oct 21/Q-P4-4: controller slows after entering lower-limit block; CTC does not cap ahead. | No; `66aa348` |
| [engine-failure-detection](../truth/_inbox/claude/quirky-fermi-sickg4/20261021-1536-engine-failure-detection.md) (`20261021-1536-engine-failure-detection.md`) | `truth/arbitration/engine-failure-detection.md` | Kevin direct Oct 21 three detector rules after Green 93 false latch; exact constants and shape deliberately unspecified. | No; `91e8c0a` |

Proposal validation in this session is inventory/metadata/provenance comparison only; no promotion or claim that all proposed choices are approved. Lower-limit proposal records R87 and earlier engine proposal records Kevin's three rules, not his later acceptance of the extra shape test. The post-summary section records two later proposals, bringing the current inbox to 20 while preserving this 18-entry baseline table. Promotion remains Kevin's/human-only work.

## Owner review and questions to relay

These are review requests, not messages sent to owners and not decisions made by this audit. Names come from the handovers, next-session prompt or truth ownership; an unassigned owner is kept unassigned.

| Owner | Change requiring review | Commit / question |
| --- | --- | --- |
| Harry Tye / Track Controller SW owners | Starter separation rule; new switch routing, `SUG_n`/`REV_s`, switch 28 reverse at rest; existing programs/vital behavior and cross-wayside implications | `1a9ce27`, `234c353`; Phase 3 Q1/Q7; discrepancies E7 |
| Track Controller SW owners | Dialog `switchApplied`/`switchReleased` rename and handlers | `1a9ce27`; Phase 3 Q2 |
| Landis / CTC Office | Current+next-block suggestion, explicit new/retired events, release/tracker/scheduler semantics | `9c440d6`; Phase 3 Q13/Q14 now implemented |
| Landis / CTC Office | Process/clock bridge, immediate STATE push; return-to-yard and harness-time schedule | `97a2fd1`, `4cc873b`; G-CLK-3, R85/R88 |
| Train Controller owners (unassigned), Kevin | Falling-speed detector, target band/window/brake guards, additional straight-line criterion and limits; package also serves logical Green SW | `460579b`, OPEN_ISSUES #26; Q-P4-8 implementation resolved; Kevin subsequently accepted the check as built (R91); known limits remain |

### Kevin's decisions and remaining actions

1. **Steady-fall check accepted as built:** Kevin directly said "Accept the steady-fall check as built" on 2026-10-21 (post-summary R91), including half-second speed means within 10% of the total fall of a straight line across the 6 s window. The two known limits remain.
2. **Stubs-only automatic Run retained:** Kevin directly said "Keep automatic Run for --stubs-only" on 2026-10-21 (post-summary R92). A stubs-only window run requires no `--auto-run`; a real window run still waits for the dispatcher unless `--auto-run` is given.
3. **Review the proposals:** 18 appear in the baseline table above and two later proposals appear below, for 20 currently. Promotion is human-only; the earlier inbox files remain unchanged.
4. **Plan Phase 5 together before giving go.** No hardware build starts from this summary alone.

### Remaining open questions and owners

| Source | Question / unresolved review | Owner |
| --- | --- | --- |
| Phase 3 Q1 | Keep new starter separation rule? (Implementation exists.) | Harry Tye |
| Phase 3 Q2 | Keep switch-dialog signal rename? (Implementation exists.) | Track Controller SW owners |
| Phase 3 Q3 | Track Model point-based switch naming versus truth listed-on block: retain harness mapping or change module? | Track Model owner and Kevin |
| Phase 3 Q4 / Track Model B1 | Accept light mapping through switch; fix light-ahead/placement, including light facing away from G1 near yard | Track Controller and Track Model owners |
| Phase 3 Q5 | Red `75-yard`: normal leg is 9 for Track Controller, 76 for Track Model; settle data before Phase 5 | Kevin, with module owners |
| Phase 3 Q6 / D026 | What automatic heater rule should Track Model apply? None specified; currently no heater commands, so none run | Track Model owner |
| Phase 3 Q7 / discrepancies E7 | Accept starter routing/inputs and reverse-at-rest 28; should vital switch lock include or move to points block; add cross-wayside occupancy input? | Harry Tye (relay via Kevin) |
| Phase 3 Q7 / E7 follower case | Does CTC two-way zone keep follower off 75/76 while train stands on 77 bound for 101? | Landis (relay via Kevin), Harry for controller side |
| Phase 3 Q8 | Add clock speed to STEP so Track Controller header can show 10x? Requires protocol/decision proposal if approved | Kevin |
| Phase 3 Q9 | Lowercase Track Controller enums versus agreed uppercase boundary convention; edges currently accept/map both | Track Controller owners |
| Phase 3 Q10 | Optional per-line readiness in operator window | Kevin; no UI change authorized by this summary |
| Phase 3 Q11 | Two preexisting HarnessWindow/QGuiApplication mypy errors in harness app/measure | Kevin (harness) |
| Phase 3 Q12 | Adjacent occupied trains hold each other under starter; ownership/direction behavior remains | Harry Tye |
| Q-P4-7 / R90 | Intended ticket probability/rate: Track Model 0.02 per station per tick, about 12 tickets per simulated minute? | Track Model owner |
| G-CLK-3 | Confirm CTC process's immediate STATE push on Run/Pause/speed | Landis / CTC Office |
| OPEN_ISSUES #26 | Known-limit disposition; shape acceptance is resolved by Kevin's later R91 decision | Train Controller owners (unassigned); Kevin |
| G-CLK-6 | Visible windows, multiple trains, USB hardware, lab-machine load within budget | Module owners; hardware/integration owner not assigned in handovers |
| G-LIFE-2 / G-RUN-7 | Remaining HW module startup/readiness, files and windows against 20 s; lifecycle/show/quit integration | HW module owners; integration owner unassigned in design |
| G-RUN-2 / Phase 5 | Windows executable/build and course per-subsystem installable expectation | Integration/packaging owner unassigned in design; Kevin to plan |
| Truth backlog / contract ownership | Human review/promotion and still-placeholder contracts/variant/interface reconciliation | Kevin for promotion; named module owners for their contracts; Train Controller contract owner unassigned |

Resolved questions are not silently left open: Phase 3 Q13/Q14 are implemented by `9c440d6`, Q15 by `428852b`; Q7 routing repair by `234c353` retains the owner choices above. Phase 4 Q-P4-1 normal Run by `68fcfa7`; Q-P4-2 both dispatch methods supported; Q-P4-3 return/retirement path works with later detector fix; Q-P4-4 decided R87; Q-P4-5 `4cc873b` shared time; Q-P4-6 no further UI changes R89. Q-P4-8 is resolved by `460579b`, with detector acceptance subsequently resolved by Kevin on 2026-10-21 (R91).

## Next work, after summary delivery

The subsequent authorized loose ends were completed in `55dac4f` (test docstring) and `b6c6eb2` (design/Phase 4 handover/README status, detector and limits), outside the baseline range. Kevin has now answered the detector and stubs-only Run questions below; the other owner questions remain open. Preserve the prohibition on further UI changes unless named by the user.

The successful one-train round trip does not validate the unresolved follower case: if the CTC Office admits a follower onto 75/76 while the leader stands at 77 bound for 101, the controller-side switch/lock may leave it waiting. Whether the CTC two-way zone prevents that entry remains Landis’s question, with Harry reviewing the controller side. No full-system follower entry is claimed verified.

**Phase 5 requires planning with Kevin and an explicit go.** Scope: Red Track Controller HW and Train Controller HW on Raspberry Pis over USB CDC-ACM, one Pi per hardware module with UIs on host (D021/D027); Red wayside data with `next_blocks` (R34/R78); measure USB round trip; one executable and Windows build. Red blocks are all two-way, so current generated starters leave switches normal there; the `75-yard` normal leg must be settled. `merge_ctc_inputs` already prepares the second Track Controller path but proves no hardware behavior.

## Post-summary decisions (2026-10-21; outside the baseline range)

Kevin Schillinger directly accepted the steady-fall check as built and retained
automatic Run for `--stubs-only` (design v0.14 R91/R92). These resolve the two user
decisions that were pending at `cf4edf5`; they require no runtime, UI or test-logic
change. Acceptance concerns the detector under review as built, without imposing
identical numerical constants on every independent variant. The decisions do not
settle the detector's two known limits or other owner questions,
and they do not authorize Phase 5.

Two new full-entry proposals record the direct decisions:

- [20261021-1220-engine-failure-steady-fall-accepted.md](../truth/_inbox/claude/quirky-fermi-sickg4/20261021-1220-engine-failure-steady-fall-accepted.md)
  targets `truth/arbitration/engine-failure-detection.md`, including the accepted
  half-second means / 10% straight-line check across the 6 s window.
- [20261021-1220-harness-stubs-only-auto-run.md](../truth/_inbox/claude/quirky-fermi-sickg4/20261021-1220-harness-stubs-only-auto-run.md)
  targets `truth/decisions/harness-stubs-only-auto-run.md`, preserving automatic Run
  in stubs-only window mode without `--auto-run`.

The current inbox contains **20 proposals**. The 18-entry table, 23-commit ledger and
258-pass / 66-subtest verification above remain the original baseline snapshot, not
an audit of these later proposals or a claim of new tests. Earlier proposal files
remain unchanged; review and promotion are human-only.

## Exhaustive commit ledger

Every commit in the exclusive range is listed below with every path touched in that commit. Intermediate `ctc_script.py` additions/deletions are deliberately retained. The ledger supplements, rather than substitutes for, the logical narratives above. Status letters are Git A/M/D (added/modified/deleted).

### `1a9ce27` — Phase 3: Track Controller SW under the harness (validation in progress)

- `M` `TrackCtrlSW/tests/test_boundary.py`
- `A` `TrackCtrlSW/tests/test_module_process.py`
- `M` `TrackCtrlSW/tests/test_world.py`
- `M` `TrackCtrlSW/track_ctrl/controller.py`
- `M` `TrackCtrlSW/track_ctrl/layout.py`
- `A` `TrackCtrlSW/track_ctrl/module_process.py`
- `M` `TrackCtrlSW/track_ctrl/state.py`
- `M` `TrackCtrlSW/ui/ProgramView.qml`
- `M` `TrackCtrlSW/ui/StatusView.qml`
- `M` `TrackCtrlSW/ui/components/SwitchDialog.qml`
- `M` `common/harness/app.py`
- `A` `common/harness/ctc_script.py`
- `M` `common/harness/edges.py`
- `M` `common/harness/measure.py`
- `M` `common/harness/modules.py`
- `M` `common/harness/tests/test_harness_edges.py`
- `M` `common/harness/tests/test_harness_system.py`
- `M` `common/harness/tests/test_harness_train_loop.py`
- `M` `common/harness/tests/test_harness_window.py`
- `A` `common/harness/track_devices.py`
- `M` `common/harness/track_edges.py`
- `A` `common/harness/wayside_edges.py`
- `D` `common/harness/wayside_script.py`
- `A` `documents/integration-handover-phase-3.md`
- `M` `track_overflow.py`

### `9c440d6` — CTC Office: next-block suggestion and train events (Q13, Q14)

- `M` `CTC-Office/ctc/interface.py`
- `M` `CTC-Office/ctc/model.py`
- `M` `CTC-Office/ctc/scheduler.py`
- `M` `CTC-Office/ctc/tracking.py`
- `M` `CTC-Office/ctc/wire.py`
- `M` `CTC-Office/tests/occupancy.py`
- `M` `CTC-Office/tests/test_ctc_authority.py`
- `M` `CTC-Office/tests/test_ctc_boundary.py`
- `M` `CTC-Office/tests/test_ctc_collisions.py`
- `M` `CTC-Office/tests/test_ctc_host.py`
- `A` `CTC-Office/tests/test_ctc_next_block.py`
- `M` `CTC-Office/tests/test_ctc_safety.py`
- `M` `CTC-Office/tests/test_ctc_scheduler.py`
- `M` `CTC-Office/tests/test_ctc_tracking.py`
- `A` `CTC-Office/tests/test_ctc_train_events.py`
- `M` `CTC-Office/tests/test_socket_link.py`

### `91a5afd` — Phase 3: finish validation and update the documents

- `M` `TrackCtrlSW/INTEGRATION_DISCREPANCIES.md`
- `M` `TrackCtrlSW/README.md`
- `M` `TrackModel/INTEGRATION.md`
- `M` `TrackModel/README.md`
- `M` `TrainModel/docs/open-issues.md`
- `M` `common/harness/README.md`
- `M` `documents/integration-handover-phase-3.md`
- `M` `documents/system-integration-design.md`

### `af6abf6` — Design document: note the CTC Office commit after the Phase 3 validation

- `M` `documents/system-integration-design.md`

### `97a2fd1` — CTC Office: the process the harness starts

- `A` `CTC-Office/ctc/module_process.py`
- `M` `CTC-Office/ctc_ui/README.md`
- `M` `CTC-Office/ctc_ui/ctc_host.py`
- `A` `CTC-Office/ctc_ui/harness_clock.py`
- `M` `CTC-Office/ctc_ui/test_harness.py`
- `A` `CTC-Office/tests/test_module_process.py`
- `M` `track_overflow.py`

### `163fdd0` — Harness Phase 4: the CTC Office wired in

- `M` `common/harness/app.py`
- `D` `common/harness/ctc_script.py`
- `M` `common/harness/edges.py`
- `M` `common/harness/measure.py`
- `M` `common/harness/modules.py`
- `M` `common/harness/tests/test_harness_edges.py`
- `M` `common/harness/tests/test_harness_system.py`
- `M` `common/harness/tests/test_harness_train_loop.py`
- `M` `common/harness/tests/test_harness_window.py`
- `M` `common/harness/track_edges.py`
- `M` `common/harness/wayside_edges.py`

### `d6066e2` — Harness: refuse unsendable replies, recover framing, match the tick

- `M` `common/harness/core.py`
- `M` `common/harness/supervisor.py`
- `A` `common/harness/tests/test_harness_faults.py`
- `M` `utils/event_log.py`
- `M` `utils/harness_protocol.py`
- `M` `utils/module_link.py`
- `M` `utils/tests/test_harness_protocol.py`
- `A` `utils/tests/test_protocol_faults.py`

### `122b279` — Event log: a file of its own for each run

- `M` `common/harness/app.py`
- `M` `utils/event_log.py`
- `A` `utils/tests/test_event_log_names.py`

### `bab5599` — Harness window: keep focus and the selected event across updates

- `A` `common/harness/tests/test_harness_window_state.py`
- `A` `common/harness/tests/window_state_probe.py`
- `M` `common/harness/ui/EventList.qml`
- `M` `common/harness/ui/Main.qml`

### `428852b` — Harness tests: make the startup-timeout console test deterministic

- `M` `common/harness/tests/test_harness_console.py`

### `b65fd26` — Phase 4 handover: as built, validation, open questions

- `A` `documents/integration-handover-phase-4.md`

### `a55b8b9` — Phase 4 documents and frozen build

- `M` `common/harness/README.md`
- `M` `documents/integration-handover-phase-3.md`
- `M` `documents/integration-handover-phase-4.md`
- `M` `documents/system-integration-design.md`

### `0305d05` — Train Controller: test braking on entering a slower block

- `M` `Train-Ctrl_HW/tests/test_harness_driven.py`

### `66aa348` — Propose arbitration/lower-limit-ahead (Q-P4-4)

- `A` `truth/_inbox/claude/quirky-fermi-sickg4/20261021-1445-lower-limit-ahead-train-controller-slows.md`

### `4cc873b` — CTC Office: return to yard, and the harness's clock

- `M` `CTC-Office/ctc/interface.py`
- `M` `CTC-Office/ctc/model.py`
- `M` `CTC-Office/ctc/module_process.py`
- `M` `CTC-Office/ctc_ui/README.md`
- `M` `CTC-Office/ctc_ui/ctc_host.py`
- `M` `CTC-Office/ctc_ui/ui/panels/SelectedTrainPanel.qml`
- `M` `CTC-Office/tests/test_ctc_host.py`
- `M` `CTC-Office/tests/test_ctc_scheduler.py`
- `M` `CTC-Office/tests/test_ctc_train_events.py`
- `M` `CTC-Office/tests/test_module_process.py`

### `234c353` — Track Controller starter: set each switch for the train coming (Q7)

- `M` `TrackCtrlSW/INTEGRATION_DISCREPANCIES.md`
- `M` `TrackCtrlSW/README.md`
- `M` `TrackCtrlSW/tests/test_layout.py`
- `A` `TrackCtrlSW/tests/test_starter_switches.py`
- `M` `TrackCtrlSW/track_ctrl/controller.py`
- `M` `TrackCtrlSW/track_ctrl/layout.py`
- `M` `common/harness/tests/test_harness_train_loop.py`

### `ed3fd91` — Harness window test: give the system run time to start

- `M` `common/harness/tests/test_harness_window.py`

### `f32d81e` — Documents: Kevin Schillinger's answers of 2026-10-21 (design v0.12)

- `M` `common/harness/README.md`
- `M` `documents/integration-handover-phase-3.md`
- `M` `documents/integration-handover-phase-4.md`
- `M` `documents/system-integration-design.md`

### `68fcfa7` — Harness: dispatcher presses Run in a window run (R83); no TIME_SLIPPED at stop

- `M` `common/harness/app.py`
- `M` `common/harness/core.py`
- `M` `common/harness/measure.py`
- `M` `common/harness/tests/test_harness_faults.py`
- `M` `common/harness/tests/test_harness_window.py`

### `9f9b644` — Documents: Q-P4-1 done (68fcfa7): Run in window mode, --auto-run

- `M` `common/harness/README.md`
- `M` `documents/integration-handover-phase-4.md`
- `M` `documents/system-integration-design.md`

### `460579b` — Train Controller (HW): detect an engine failure by a steady fall, not a flat speed

- `M` `Train-Ctrl_HW/CHANGELOG.md`
- `M` `Train-Ctrl_HW/HARNESS_INTEGRATION.md`
- `M` `Train-Ctrl_HW/OPEN_ISSUES.md`
- `M` `Train-Ctrl_HW/REQUIREMENTS.md`
- `M` `Train-Ctrl_HW/check.py`
- `A` `Train-Ctrl_HW/tests/test_engine_detection.py`
- `M` `Train-Ctrl_HW/train_ctrl/constants.py`
- `M` `Train-Ctrl_HW/train_ctrl/control.py`

### `91e8c0a` — Truth proposal: how the Train Controller detects an engine failure

- `A` `truth/_inbox/claude/quirky-fermi-sickg4/20261021-1536-engine-failure-detection.md`

### `cf4edf5` — Prompt for the next integration session

- `A` `documents/integration-next-session-prompt.md`

## Net path accounting

The range has **23 commits**, **83 net changed paths**, and **84 distinct paths touched across the commit ledger**. Net paths are listed below so each implementation/document/test can be checked against its area above. Temporary paths can occur only in the ledger.

```text
M	CTC-Office/ctc/interface.py
M	CTC-Office/ctc/model.py
A	CTC-Office/ctc/module_process.py
M	CTC-Office/ctc/scheduler.py
M	CTC-Office/ctc/tracking.py
M	CTC-Office/ctc/wire.py
M	CTC-Office/ctc_ui/README.md
M	CTC-Office/ctc_ui/ctc_host.py
A	CTC-Office/ctc_ui/harness_clock.py
M	CTC-Office/ctc_ui/test_harness.py
M	CTC-Office/ctc_ui/ui/panels/SelectedTrainPanel.qml
M	CTC-Office/tests/occupancy.py
M	CTC-Office/tests/test_ctc_authority.py
M	CTC-Office/tests/test_ctc_boundary.py
M	CTC-Office/tests/test_ctc_collisions.py
M	CTC-Office/tests/test_ctc_host.py
A	CTC-Office/tests/test_ctc_next_block.py
M	CTC-Office/tests/test_ctc_safety.py
M	CTC-Office/tests/test_ctc_scheduler.py
M	CTC-Office/tests/test_ctc_tracking.py
A	CTC-Office/tests/test_ctc_train_events.py
A	CTC-Office/tests/test_module_process.py
M	CTC-Office/tests/test_socket_link.py
M	TrackCtrlSW/INTEGRATION_DISCREPANCIES.md
M	TrackCtrlSW/README.md
M	TrackCtrlSW/tests/test_boundary.py
M	TrackCtrlSW/tests/test_layout.py
A	TrackCtrlSW/tests/test_module_process.py
A	TrackCtrlSW/tests/test_starter_switches.py
M	TrackCtrlSW/tests/test_world.py
M	TrackCtrlSW/track_ctrl/controller.py
M	TrackCtrlSW/track_ctrl/layout.py
A	TrackCtrlSW/track_ctrl/module_process.py
M	TrackCtrlSW/track_ctrl/state.py
M	TrackCtrlSW/ui/ProgramView.qml
M	TrackCtrlSW/ui/StatusView.qml
M	TrackCtrlSW/ui/components/SwitchDialog.qml
M	TrackModel/INTEGRATION.md
M	TrackModel/README.md
M	Train-Ctrl_HW/CHANGELOG.md
M	Train-Ctrl_HW/HARNESS_INTEGRATION.md
M	Train-Ctrl_HW/OPEN_ISSUES.md
M	Train-Ctrl_HW/REQUIREMENTS.md
M	Train-Ctrl_HW/check.py
A	Train-Ctrl_HW/tests/test_engine_detection.py
M	Train-Ctrl_HW/tests/test_harness_driven.py
M	Train-Ctrl_HW/train_ctrl/constants.py
M	Train-Ctrl_HW/train_ctrl/control.py
M	TrainModel/docs/open-issues.md
M	common/harness/README.md
M	common/harness/app.py
M	common/harness/core.py
M	common/harness/edges.py
M	common/harness/measure.py
M	common/harness/modules.py
M	common/harness/supervisor.py
M	common/harness/tests/test_harness_console.py
M	common/harness/tests/test_harness_edges.py
A	common/harness/tests/test_harness_faults.py
M	common/harness/tests/test_harness_system.py
M	common/harness/tests/test_harness_train_loop.py
M	common/harness/tests/test_harness_window.py
A	common/harness/tests/test_harness_window_state.py
A	common/harness/tests/window_state_probe.py
A	common/harness/track_devices.py
M	common/harness/track_edges.py
M	common/harness/ui/EventList.qml
M	common/harness/ui/Main.qml
A	common/harness/wayside_edges.py
D	common/harness/wayside_script.py
A	documents/integration-handover-phase-3.md
A	documents/integration-handover-phase-4.md
A	documents/integration-next-session-prompt.md
M	documents/system-integration-design.md
M	track_overflow.py
A	truth/_inbox/claude/quirky-fermi-sickg4/20261021-1445-lower-limit-ahead-train-controller-slows.md
A	truth/_inbox/claude/quirky-fermi-sickg4/20261021-1536-engine-failure-detection.md
M	utils/event_log.py
M	utils/harness_protocol.py
M	utils/module_link.py
A	utils/tests/test_event_log_names.py
M	utils/tests/test_harness_protocol.py
A	utils/tests/test_protocol_faults.py
```

## Phase 5 software as built (2026-10-21)

This section is additional to the audited Phase 3/4 range above. The Phase 5
session starts at `aa7776c`. The full ruling record and acceptance limits are
in `system-integration-design.md` §5.6 and `documents/integration-handover.md#phase-5-handover`.

| Area | What changed / why | Commits / covering evidence |
| --- | --- | --- |
| Track Controller HW | Merge PR #43 source and Braden's WP2 design; dual channels/five-bit speed, no generated vital PLC. Add exact-cut Green adjacency and three marked Red integration test waysides/PLCs with all safety in programs (K3/K3b/K4/K4b). | `8407baf`, `2335197`, `f27ba4e`; full HW 80/50,506 subtests, exhaustive Red speed/topology/crossing/separation tests. |
| Track Model / SW topology | Yard adjacency moves from 75 to section-C 9 (K2); four readers agree using row9 while retaining unresolved `75-yard` source. Kevin confirmed the policy covers SW too; existing SW vital code stays unchanged under the original implementation scope, with an owner follow-up. | `f27ba4e`; reader contract and existing layout regressions. |
| Harness / utils | Direct HW edge mappings, Green+Red command/report merging, variant train routing and deferred replies; both HW modules real by default with explicit test-only simulated Pis; approved CLOCK_STATE metadata for exact loss-time gain policy. | `cb8a326`, `d4db358`, `9325523`, `f465c99`; mixed seven-core run, decoder/deferred and clock-state tests. |
| USB / Pi | Standard-library agent and host transport/adapters implement the D027 split against explicit simulated Pis; no missing-Pi fallback. Final real-process and K11 integrated acceptance is recorded in the handover. | `daaa3e7`, `78c470c`, `8d15a69`, `c39a070`, `baed0cd`; protocol/recovery/window tests. |
| Documents / truth proposals | K1–K12 exact decisions R93–R107, integration guide, untested owner setup, Phase5 handover; seven new normative proposals, including the later confirmed both-variant policy and CLOCK_STATE exception. | `17beefc`; K2/K5/K6/K7/K11 proposals await human promotion. |
| CTC Office, Train Model, Train Controller safety | No additional module safety/UI change was needed for the in-process Red outbound route. Existing line-specific behavior is mapped through the harness; remote adapters reuse existing window constructors. | Mixed-line route 9–16, 45 s dwell, Green unaffected; broad suites in handover. |

Owner review must include the test copies, read-only neighbor OCC extension,
Red-9 NORMAL-leg assumption/source text, WP2 vital-block discrepancy and the
NORMAL-only return limitation (held 66 by switch 52; no retirement/turnback).
Hardware USB measurements, provisioning and Windows/installer packaging are
steps 10–12, not started. The starting 20 current-branch proposals plus 7 new
ones make 27; four merged-owner proposals remain under their separate source
branch path. None has been promoted by this work.

Software steps 1–9 and documentation step 13 are complete against explicit
simulated Pis. Both HW modules are real by default, with identity-based USB
waiting and no fallback; `--test-pi process`/`pty` is an explicit development
selection. Approved CLOCK_STATE supplies authoritative loss-time clock state.
Final post-default harness+utils: 252 passed/5 skipped/540 subtests; opt-in
Green round trip: 5 passed. Full Pi suite: 31 passed. The handover lists all
module counts, independent acceptance slices and the known preexisting
harness Qt argument type-check mismatch. No actual Pi/USB/Windows result is
implied by the simulated software acceptance.

## Changes since the summary (2026-10-22 to 2026-10-28)

**Scope:** the 33 non-merge commits dated 2026-10-22 or later, `25cc37a` through `7d9b47e`, on `claude/quirky-fermi-sickg4`, and the consolidation commit `a21bf64`. The audited range above is not repeated. The sources are the commit messages, the commits named below, and the owner answers in `module-owner-review.md`. This section records changes. It changes no code.

### CTC Office

- Dispatcher Cancel order removed from the actions, code, tests, panel, SDD and UML: `fcb0ed5`, `e7dcea2`, `b9befc6`. The CTC still clears an order when its run is back in the yard (`fcb0ed5`).
- Two-way zones reserved by direction, not by train; a train leaving the yard heads out the fixed side of the yard switch, as the Track Model runs it: `31ed67c` (CTC-1 and LAYOUT-1 answers, 2026-10-25).
- One empty block between trains: `7120fee` (`ctc/routing.py`), with `1adef08` in the SDD.
- The gap is kept against every other train, on the route or off it: `57614d2` (`keep_gap()`; Landis, 2026-10-28).
- Owner answers and proposals: `bf43321`; owner review write-up and Phase 8 scope in `e58011a` and `c10a5c6`. CTC-2 and CTC-3 are routed to the Track Controller owners, with no CTC change.
- Diagnostics: Red scheduler snapshots made reproducible (`3319d14`); bounded Green and input diagnostics (`c4b3cce`).

### Track Controller SW

- Harry Tye's development SW is taken, with generated vital PLC code attached to every program: `7120fee` (applied from `f796f49` on `origin/development`). Harry Tye's replies are recorded in `8a860fb`.
- Separation holds only a block with a train in it: `AUTH_n := NOT (OCC_n AND (OCC_n-1 OR OCC_n+1))` (`7120fee`). `test_starter_switches.py` is removed.
- Open, as recorded in `7120fee`: a not-ready wayside transmits nothing, and the crossing test that expects them held down is marked expected-failure. `test_hw_language.py` fails three tests against the Red programs' new `CTCSW_s` and `CTCREV_s` names.

### Track Controller HW

- A generated read-only vital PLC block runs after every program, on both channels. It is in `track_ctrl_hw/vital.py` and `wayside.py`, and the snapshot carries its checksum and overrides: `a5bd465`.
- Braden's three Red programs are merged in place of the integration test copies. The file names are unchanged (`a5bd465`; HW-1 answer, 2026-10-26).
- Signals sit at switch points in the Red integration test (`86f4658`).
- The vital block is PLC code, so it keeps to the no-vital ruling R96 ("everything is done by the plc code"): safety stays in the PLC programs.

### Track Model

- TM-1, time-based ticket sales: `tickets_per_minute`, default 12 per station; each tick's chance is `min(1, rate × dt / 60)` (`ef1dc26`).
- TM-3, heaters: on at or below 0 °C ambient, off above, no hysteresis, last state kept when ambient is missing. Heater commands are accepted but not applied (`ef1dc26`).
- TM-2, B1 closed: signals sit at switch points, and each train is sent the light ahead on every tick, facing its direction of travel (`86f4658`). The physical placement is still to be confirmed by the Track Controller owners (SW discrepancy C6).
- Owner answers in `module-owner-review.md`: `c92f58f`.

### Train Model

- Passenger pull stays latched until the Train Controller's emergency brake goes from true to false. The one-shot `passenger_brake_release` is withdrawn (`bd72876`). The test-only `clear_passenger_brake` override remains in `train_model/link.py`.
- On a signal-pickup failure the Train Model sends null commanded speed and authority (`661f249`).
- No speed limit is sent to the Train Controller: `ControllerOutputs.speed_limit_mps` is removed (`a6c1eb3`). The Train Model still receives the limit in Track Info and shows it in its window; only the test UI's stand-in speed limiter acts on it (`train_model/harness.py`). The Train Model itself does not govern speed (D009).
- Documents follow the changes: `bd72876`, `661f249`, `a6c1eb3`.

### Train Controller

- The PR #50 Train Controller is pulled in: `74159e9`, from `Train_Ctrl_integration` `e0e142d`.
- A null commanded speed or authority is read as a signal-pickup failure. The 0 and 0 rule is removed (`a6c1eb3`).
- `Train-Ctrl_HW/OPEN_ISSUES.md` #24 (speed limit) and #25 (passenger brake release) are closed (`a6c1eb3`).
- Open: `constants.py` still spells `SUPER GREEN`. The engine-failure latch on a grade is recorded as `OPEN_ISSUES.md` #23 in the 2026-10-27 owner answer.

### Harness

- `common/harness/train_edges.py`: a null passes through, `passenger_brake_release` is not carried, and no speed limit is sent (`661f249`, `bd72876`, `a6c1eb3`).
- Simulated Pis are configured per module at startup. A true toggle in `config/pi-testing.json` selects the simulator; a missing key means physical hardware (`8110e88`; `common/harness/pi_config.py`).
- The Pi HELLO identity check is one helper, `matches_hello`, used by the relay and by bring-up (`92e500b`; `common/hw_link/tests/test_hello.py`).
- Phase 7 review scenarios run at 1x (`92e500b`, `d606e05`). Owner diagnostic tests are added in `c4b3cce` and `3319d14`.

### Documents

- Handovers and phase prompts are consolidated in `documents/integration-handover.md`, with the originals in `documents/archive/handover/` (`a21bf64`).
- Phase 6 evidence and limits (`25cc37a`, `a23bc22`); Phase 7 (`022608a`, `d606e05`); Phase 8 (`c10a5c6`); the 2026-10-22 session handover (`5050a30`).
- The shared owner review queue, `documents/module-owner-review.md`, records the answers (`022608a`, `c92f58f`, `8a860fb`, `e58011a`, `c10a5c6`, `d606e05`). Braden's answers are in `documents/module-owner-review-braden.md` (`a5bd465`).
- CTC Office design, use-case and sequence diagrams (`c9cd437`, `f6ed1a1`, `b9befc6`, `e7dcea2`); Train Model UML exports (`e8aad02`, `59d5bf7`).
- `7d9b47e` untracks three Train Model prompt files that `a6c1eb3` committed by mistake.

### Truth proposals

Twenty-one proposals were added under `truth/_inbox/` on this branch since 2026-10-22. Twenty are in `truth/_inbox/claude/quirky-fermi-sickg4/`, and one is in `truth/_inbox/feature/ctc-remove-cancel-order/`. Each is a proposal awaiting human promotion. None is promoted, and agents do not promote them. Targets are as written in each file.

- `20261024-1023-review-functional-speed.md` → `truth/decisions/review-functional-speed.md` (`022608a`)
- `20261025-1509-independent-simulated-pis.md` → `truth/decisions/independent-simulated-pis.md` (`8110e88`)
- `20261025-2128-two-way-zone-direction-reservation.md` → `truth/arbitration/two-way-zone-direction-reservation.md` (`bf43321`)
- `20261025-2129-maintenance-closure-lock-switches.md` → `truth/arbitration/maintenance-closure-lock.md` (`bf43321`)
- `20261025-2130-track-model-layout-is-master.md` → `truth/decisions/track-model-layout-is-master.md` (`bf43321`)
- `20261025-2242-beacon-on-station-block.md` → `truth/signals/beacon.md` (`74159e9`)
- `20261025-2242-passenger-brake-release-conflict.md` → `truth/signals/passenger-brake-release.md` (`74159e9`)
- `20261027-1819-authority-one-empty-block-conflict.md` → `truth/arbitration/authority-stops-before-obstruction.md` (`7120fee`)
- `20261027-1836-missing-occupancy-counts-occupied.md` → `truth/arbitration/missing-occupancy-counts-occupied.md` (`7120fee`)
- `20261027-1836-signals-at-switches.md` → `truth/decisions/signals-at-switches.md` (`7120fee`)
- `20261027-1836-track-controller-hw-variant.md` → `truth/modules/track-controller/track-controller-hw.md` (`7120fee`)
- `20261027-1836-track-controller-vital-plc-block.md` → `truth/decisions/track-controller-vital-plc-block.md` (`7120fee`)
- `20261027-1847-D026-heater-rule.md` → `truth/decisions/D026-track-model-switches-heaters.md` (`ef1dc26`)
- `20261027-1847-signal-aspect-ahead-direction.md` → `truth/signals/signal-aspect-ahead.md` (`ef1dc26`)
- `20261027-1847-ticket-sales-time-based.md` → `truth/signals/ticket-sales.md` (`ef1dc26`)
- `20261028-1118-passenger-brake-release-withdrawn.md` → `truth/signals/passenger-brake-release.md` (`bd72876`)
- `20261028-1119-passenger-emergency-brake-release.md` → `truth/arbitration/passenger-emergency-brake.md` (`bd72876`)
- `20261028-1152-authority-gap-kept.md` → `truth/arbitration/authority-stops-before-obstruction.md` (`57614d2`)
- `20261028-1153-track-signal-null-on-pickup-failure.md` → `truth/signals/track-signal.md` (`661f249`)
- `20261028-1208-track-info-speed-limit-not-sent.md` → `truth/signals/track-info.md` (`a6c1eb3`)
- `feature/ctc-remove-cancel-order/20261025-2000-no-dispatcher-order-cancel.md` → `truth/decisions/D028-no-dispatcher-order-cancel.md` (`fcb0ed5`)

Points for human review before promotion:

- Two proposals target `truth/signals/passenger-brake-release.md`, and two target `truth/arbitration/authority-stops-before-obstruction.md`. In each pair the 2026-10-28 proposal resolves the earlier one's Conflict and supersedes it.
- The cancel-order proposal targets `D028`. The Red yard-connection proposal `20261021-1808-red-yard-connection.md` also targets `truth/decisions/D028-red-yard-connection.md`.
- The cancel-order proposal was committed under `truth/_inbox/feature/ctc-remove-cancel-order/`, not under this branch's directory. `AGENTS.md` names `truth/_inbox/<current-branch>/` as the write location.
