# Integration handover: Phase 4, the CTC Office

Written 2026-10-20 at the end of the session that built Phase 4, on branch
`claude/quirky-fermi-sickg4`. It is for whoever picks the work up next, person or agent,
and for the merge of these notes into `documents/system-integration-design.md` (a §5.5
"Phase 4 as built") and `common/harness/README.md`. It follows
`documents/integration-handover-phase-3.md`.

Phase 4 in the plan: "CTC Office: dispatch from the yard, suggestions, occupancy, ticket
sales and clock control. The Iteration 3 scenario on Green: dispatch a train from the yard
to a station (graded 2026-11-12)."

The CTC Office's own changes for Q13 (the next-block suggestion) and Q14 (`new_trains`,
`retired_trains`) were made by the CTC Office's side in `9c440d6`. This file covers the
integration built on them.

## 1. As built

### What runs

`python track_overflow.py` starts the harness and seven module processes. Five run as
themselves: the CTC Office (new), the Track Controller SW, the Track Model, the Train
Model and the Train Controller SW. The two HW variants are stubs.

1. The clock starts paused (D017). The CTC Office presses Run once it is ready
   (`--run-on-ready`, as its stub did before; see Q-P4-1), and the harness reads Run,
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

### Changed, by file

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
| `common/harness/app.py` | No stand-in; `--dispatch` passed to the CTC Office. (Minimal change; the bug-fix agent's uncommitted `EventLog.create` change in the same file was left uncommitted.) |
| `common/harness/measure.py` | `--system` runs the real CTC Office: Run (and 10x) and `--dispatch G1:Green:73`, so the train runs for the whole measurement. |
| `common/harness/tests/` | `test_harness_edges.py` (53): readiness events, the CTC Office's inputs, the Track Controller's `ctc` from the CTC Office, ticket sales once across accepted and refused ticks, `merge_ctc_inputs`, and the real Track Model's stations accepted by the CTC Office's own validator. `test_harness_train_loop.py` (23): the five modules' own code in one process, CTC Office included. `test_harness_system.py` (11): the Iteration 3 scenario end to end. `test_harness_window.py`: system mode passes `--dispatch`. |

### The CTC Office's tracking under harness timing

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

## 2. Validation

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

Not done: the frozen build (see section 4).

## 3. Departures and design choices

- **Dispatch in the scenario.** A test option on the CTC Office process plays the
  dispatcher (`--dispatch`), given once the line is ready, as `--load-starters` plays
  the person loading programs. Manual dispatch to GLENBURY is the Iteration 3 scenario
  as stated; `--schedule` is there for automatic mode. See Q-P4-2.
- **Run on ready in a normal run.** `app.py` still passes `--run-on-ready`, as it did to
  the stub, so a run starts by itself. D017 says the clock starts paused and the CTC
  Office runs it; the window now has a working Run. See Q-P4-1.
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

## 4. Open questions

| # | Question | Who | Recommendation |
|---|---|---|---|
| Q-P4-1 | Should a normal run wait for the dispatcher's Run (D017), now that the CTC window has one? `app.py` presses Run automatically, as Phases 0 to 3 did. | Kevin, Landis | Keep `--run-on-ready` for headless and test runs; in window mode let the dispatcher press Run. A one-line change in `app.py`. |
| Q-P4-2 | For the graded Iteration 3 run, manual dispatch (the dispatcher in the CTC window, or `--dispatch`) or the course schedule in automatic mode? | Landis, Kevin | Manual dispatch to GLENBURY: it is the scenario as stated and needs no schedule. Both are tested to work. |
| Q-P4-3 | The "return to yard" action for manual trains (R66, D022) does not exist, and a scheduled run cannot reach the yard entry block in the full system: the starter program never throws switch 58 (Phase 3 Q7). So no train is ever retired in a real run. | Landis (CTC), Harry Tye (Track Controller) | Settle Q7 first, then add the action to the CTC Office. Not needed for Iteration 3, which ends at a station. |
| Q-P4-4 | Speed at a lower limit ahead: G1 enters block 67 (40 km/h, 11 m/s) at 18 m/s. The CTC Office suggests for 66 a little under 66's own limit (70 km/h), and nothing slows the train before 67. The Train Controller only follows the block it is in. | Landis (CTC), Train Controller owners | Have the CTC Office cap a block's suggestion so a train can brake to the next block's limit at the service rate, as it already does for the end of authority. |
| Q-P4-5 | The CTC Office keeps its own elapsed time (`StubCtcOffice._elapsed_s`) and does not read the step's simulation time. A refused tick puts its schedule one tick behind the harness's time, for good. | Landis | Take the time of day from the step's `sim_time_s` (D017). A model change; the process already has the time. |
| Q-P4-6 | The test UI and `ctc_host._suggestions` key suggestions by train. The test UI now names the next block's rows `next_...`; the CTC window shows the train's own block. | Landis | Accept, or key both by train and block. |
| Q-P4-7 | Ticket sales: the Track Model sells with probability 0.02 per station per tick, so a station sells about 12 tickets a simulated minute. Is that the intended rate? | Track Model owner | Unrelated to the harness; flag only. |

No truth proposal was filed: nothing in this phase came from a new decision or a direct
statement. The behaviours above follow D005, D017, D022, D025, R46, R49, R51 and R52.
`truth/_inbox/claude/quirky-fermi-sickg4/` still holds the 16 proposals from earlier in
the session, awaiting promotion by a person.

## 5. What is left

1. **Documents** (owned by the validation work): `documents/system-integration-design.md`
   §5.5 "Phase 4 as built" from section 1 and 2 above, Appendix A's CTC Office edges;
   `common/harness/README.md`: the module table (`ctc_script.py` is deleted, and the
   README still lists it), `--dispatch`, the CTC Office's test options, the readiness and
   train events, and the tests' new contents.
2. **Frozen build** (G-RUN-2). Add `--paths "$PWD/CTC-Office"` and
   `--add-data "$PWD/CTC-Office/ctc_ui/ui:CTC-Office/ctc_ui/ui"` to the recipe. The
   process finds its layouts and window under `_MEIPASS`, but `ctc.track_layout`'s
   default `LAYOUT_DIR` and `TrackMapModel()` without a layout use `__file__` and would
   not; the process always passes the layout, so check only that nothing else calls them
   in a build. Then run `--headless --speedup --load-starters --dispatch G1:Green:65
   --run-seconds 12` from outside the checkout and expect `TRAIN_ADDED` and seven exits
   of 0.
3. **The CTC Office window at 10x by eye**: the measurement ran offscreen. Watch the map
   and tables with a real display; raise `WINDOW_REFRESH_MS` if replies lag.
4. **Phase 5**: the Track Controller HW's reports join the CTC Office's input through
   `merge_ctc_inputs` once its process returns `ctc_reports` in the SW variant's form.
