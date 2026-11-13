# Test Plan

**Document Version:** 1.0
**Date:** 2026-11-13
**Prepared By:** SeeingEyeTree (Track Model owner)
**Project Name:** Track Overflow — Track Model

---

## Table of Contents
1. [Introduction](#1-introduction)
   * [1.1 Purpose](#11-purpose)
   * [1.2 Scope](#12-scope)
   * [1.3 Definitions, Acronyms, & Abbreviations](#13-definitions-acronyms--abbreviations)
   * [1.4 References](#14-references)
   * [1.5 Overview](#15-overview)
2. [Features to Be Tested](#2-features-to-be-tested)
3. [Features Not to Be Tested](#3-features-not-to-be-tested)
4. [Item Pass/Fail Criteria](#4-item-passfail-criteria)
5. [Test Deliverables](#5-test-deliverables)
6. [Responsibilities](#6-responsibilities)
7. [Test Items](#7-test-items)
   * [7.1 Layout loader (layout)](#71-layout-loader-layout)
   * [7.2 Green Line data](#72-green-line-data)
   * [7.3 Commands and device state (model)](#73-commands-and-device-state-model)
   * [7.4 Track circuit: speed and authority (model)](#74-track-circuit-speed-and-authority-model)
   * [7.5 Train movement and occupancy (model)](#75-train-movement-and-occupancy-model)
   * [7.6 Signals and beacons (model)](#76-signals-and-beacons-model)
   * [7.7 Heaters, temperature and ambient (model)](#77-heaters-temperature-and-ambient-model)
   * [7.8 Failure modes (model)](#78-failure-modes-model)
   * [7.9 Stations, tickets and boarding (model)](#79-stations-tickets-and-boarding-model)
   * [7.10 Input validation and reset (model)](#710-input-validation-and-reset-model)
   * [7.11 Track Model window (state, QML)](#711-track-model-window-state-qml)
   * [7.12 Harness process and wire format](#712-harness-process-and-wire-format)
   * [7.13 Test UI and test link](#713-test-ui-and-test-link)
   * [7.14 Integration with the central harness](#714-integration-with-the-central-harness)
8. [Approvals](#8-approvals)

---

## 1. Introduction

### 1.1. Purpose
This plan sets out how the Track Model is tested. It identifies:

- the items, meaning the modules of `TrackModel/track_model/` and the scaffolding around them;
- the features and requirements to be tested, and how;
- the test cases with their inputs and expected results;
- who designs, runs and reviews them;
- the risks that limit the plan.

The plan is the evidence that the module meets its SRS requirements (REQ-FUNC-015 to
REQ-FUNC-024 and the interface requirements) before it is integrated with the rest of the
system.

### 1.2. Scope
**System boundary.** The module is `TrackModel/`:

- `track_model/`, the module: `interface`, `layout`, `model`, `state`, `wire`,
  `module_process`;
- `ui/`, the Track Model window;
- `test_ui/` and `test_link/`, the test UI and its link (test scaffolding, removable per
  D010);
- the Track Model's edges in `common/harness/` (`track_edges.py`, `track_model_edges.py`).

Everything the module exchanges crosses `TrackModel.step(dt, inputs)`. All IDs are strings
such as `GREEN D-13`, and all values are in backend units (m, m/s, degrees, °C).

**Test levels.**

| Level | What | How |
|---|---|---|
| Unit | One function or class: layout parser, unit conversion, block filter, codec | Automated, `pytest`, headless |
| Component | The whole module through its boundary: `step`, `snapshot`, `reset`, `set_block_failure`, `load_track` | Automated, `pytest`, with `tests/helpers.py` (`make_model`, `make_inputs`, `report`) |
| Integration (module + scaffolding) | The Track Model window and the test UI over the local-socket link; the module as the process the harness starts | Automated (`test_end_to_end.py`, `test_link.py`, `test_module_process.py`, offscreen Qt), plus manual runs of both windows (`MANUAL_TESTS.md`) |
| Integration (system) | The module under the central harness with the CTC Office, Track Controller and Train Model | Planned: needs the other modules' harness endpoints (7.14) |
| Acceptance | The Track Model rubric items shown in the iteration demonstrations | Manual, scripted in `MANUAL_TESTS.md` (TC-01 to TC-30) |

**Constraints and assumptions.**

- Tests run on Windows 11 with Python 3.14 and PySide6 6.11 (`TrackModel/.venv`).
- `dt` is fixed at 0.1 s (D006) in the tests, except the cases that vary it on purpose
  (7.9).
- Commanded speed and authority last one tick (`signals/track-signal.md`); authority is a
  count of blocks (D013).
- The Track Model switches the heaters itself (D026). The rule it uses (freezing point, no
  hysteresis) is the owner's working rule, not yet recorded in truth, so those cases are
  marked *Provisional* (7.7).
- The automated tests need no display: Qt runs with `QT_QPA_PLATFORM=offscreen`.
- Ticket sales are random; the tests seed the generator (`test_ticket_sales_are_reproducible_with_a_seed`)
  or test rates over many ticks, never a single roll.
- The Blue Line is out of scope (D023). Its layout is loaded in tests only to check that
  the loader is general.

### 1.3. Definitions, Acronyms, & Abbreviations
| Term | Definition |
|------|------------|
| Block | One segment of track, ID `<LINE> <section>-<number>`, e.g. `GREEN D-13`. |
| Section | A lettered group of blocks, ID `<LINE> <section>`, e.g. `GREEN D`. Heaters and track temperature are per section. |
| Point block | The block where a switch is. The switch is named after it. |
| Leg | One of the two blocks a switch can send a train to. NORMAL is the first one listed. |
| Track circuit | What a block's rails carry to a train: commanded speed (m/s) and authority (blocks). |
| Track Info | Terrain data for the occupied block, sent to the Train Model each tick. |
| Feed | Everything one train receives from the track in one tick. |
| Beacon | Station data sent to a train on the blocks next to a station. |
| Offset | Distance the train front has moved since entering its block, as the Train Model reports it. |
| Carry | The overshoot the Track Model keeps when the Train Model restarts its offset at 0 in a new block. |
| Rollback | A negative offset: the train moves back into the block it came from. |
| Stale report | A Train Model report still naming the block a train just left. It is ignored. |
| Murphy | The failure-injection control in the Track Model window. |
| Commanded vs actual | What the Track Controller asked a device to do, vs what the device is doing (they differ in a power failure). |
| Tick | One step of the shared clock (D017), carrying `dt`. |
| SUT | System under test. |

### 1.4. References
- SRS — `documents/srs-filled.md`, REQ-FUNC-015 to 024, REQ-INTF-001.2, 011 to 013,
  018, REQ-NFR-001 to 006.
- SDD contribution — `documents/sdd/track_model.md`, Appendix C (Track Model detailed
  design), D (sequences), E (state machine), G (interface dictionary), H (traceability).
- Decisions on `truth`: D005 (harness), D006 (fixed time step), D008 (stale catalog),
  D009 (Train Model is physics only), D010 (test UI is a separate process), D013
  (authority as a block count), D017 (shared clock), D021 (Green to SW, Red to HW),
  D022 (yard is a black box), D023 (Blue Line out of scope), D026 (Track Model switches
  heaters).
- Signals on `truth`: `track-info`, `track-signal`.
- Module documents — `TrackModel/README.md`, `knowledge/CODE_OVERVIEW.md`,
  `INTEGRATION.md`, `BUGS.md`, `MANUAL_TESTS.md`.
- Sibling plans — `documents/test_plan.md` (system), `documents/test_plan_track_ctrl_sw.md`.
- Test case template — `documents/test-case-template.xlsx`.

### 1.5. Overview
- Section 2 lists the features under test against their requirements, and section 3 the
  features excluded.
- Section 4 gives the pass, fail, suspension and resumption criteria.
- Section 5 lists the deliverables, and section 6 who does what.
- Section 7 is the body of the plan. For each group of behaviour it gives the item, the
  build, the approach, and a table of test cases with inputs and expected results. Each
  automated case names the test that implements it (`file :: test`). Each manual case
  names its script (`MANUAL_TESTS.md` TC-nn).

---

## 2. Features to Be Tested

| # | Feature | Requirements | Test items |
|---|---|---|---|
| F1 | Load track layouts from JSON; convert units on read | REQ-FUNC-015, REQ-INTF-012 | 7.1, 7.2 |
| F2 | Show each segment's grade, elevation, length, speed limit, direction, crossings, heaters, beacons | REQ-FUNC-016.1 to 016.8 | 7.1, 7.2, 7.11 |
| F3 | Track ticket sales per station and send them to the CTC Office | REQ-FUNC-017, 017.1 | 7.9 |
| F4 | Show passengers boarding and disembarking | REQ-FUNC-018.1, 018.2 | 7.9, 7.11 |
| F5 | Show train occupancy | REQ-FUNC-019, REQ-INTF-018 | 7.5, 7.11 |
| F6 | Exchange track circuit signals | REQ-FUNC-020.1, 020.2, REQ-INTF-017 | 7.4 |
| F7 | Set the environmental temperature | REQ-FUNC-021 | 7.7 |
| F8 | Simulate track heaters affecting the track environment | REQ-FUNC-022, D026 | 7.7 |
| F9 | Show switch positions and light states | REQ-FUNC-023.1, 023.2 | 7.3, 7.6, 7.11 |
| F10 | Simulate broken rail, track circuit and power failure | REQ-FUNC-024.1 to 024.3 | 7.8 |
| F11 | Apply Track Controller commands (switch, light, gate); never route | REQ-INTF-018 | 7.3, 7.5 |
| F12 | Move trains across blocks from their offsets; follow the switches as set | REQ-FUNC-019 | 7.5 |
| F13 | Send Track Info, beacon and signal to the Train Model | `signals/track-info`, REQ-FUNC-046 | 7.4, 7.5, 7.6 |
| F14 | Track Model GUI | REQ-INTF-001.2, REQ-INTF-011 | 7.11 |
| F15 | Invalid input rejected without changing state | REQ-NFR-003, REQ-NFR-004 | 7.10, 7.12, 7.13 |
| F16 | Stepped by one shared clock with a fixed dt | REQ-INTF-013, REQ-NFR-002 | 7.10, 7.12 |
| F17 | Runs as a harness process; JSON wire format | D005, REQ-NFR-005, 006 | 7.12 |
| F18 | Separate, removable test UI | D010, Rubric iteration 2 | 7.13 |

---

## 3. Features Not to Be Tested

- **The Blue Line.** Out of scope (D023). `blue_line.json` is loaded only to show the loader
  is general.
- **Routing and interlocking.** The Track Model never routes. The Track Controller decides
  switch and signal commands, and is tested by its owner. Only that the Track Model applies
  the commands it is given is tested.
- **Detecting failures.** The Track Controller detects them (REQ-FUNC-059). The Track Model
  only simulates them and reports them as occupancy.
- **Train physics.** Owned by the Train Model (D009). The Track Model is tested against the
  offsets it is sent, not against a simulated train, except `test_end_to_end.py`, which
  uses the test UI as a stand-in.
- **The CTC Office's use of ticket sales** (throughput metrics, REQ-FUNC-014). Only that sales
  are produced and delivered is tested.
- **Pixel layout and visual style of the QML windows.** These are checked by review against
  `documents/UI_Style_Guide.md`, not by test cases.
- **The Raspberry Pi hardware and the USB link** (D021, D027). They are the Track Controller
  hardware variant's concern.
- **Real-time performance at 10x.** This needs the central harness, and is deferred to system
  integration (7.14).
- **Moving block overlay.** Out of scope (D001).

---

## 4. Item Pass/Fail Criteria

| Criteria | Description |
|----------|--------------|
| Pass | Every automated test of the item passes (`pytest` reports no failures), `mypy --strict` and `flake8` report no errors, and every manual case of the item gives its expected result. |
| Fail | Any automated test fails or errors, or any manual case gives a result other than the expected one. |
| Critical failure | Any failure in a safety case, marked **S** in section 7. The Track Model is not vital, but the Track Controller and the trains rely on it to fail safe: a failed block must read as occupied, a dead circuit must carry 0 and 0, and a power failure must hold the switch, show RED and drop the gates. A critical failure fails the whole module, whatever else passes. |
| Suspension | Testing stops when the module does not start, the suite cannot be imported, or a critical failure is found. Other cases would only hide its cause. |
| Resumption | After the fix, the full automated suite is re-run, not only the failed case. The affected manual cases are then repeated. |
| Not run | A planned case whose dependency is missing, such as another module's harness endpoint (7.14). It is recorded as *Planned*, not as a pass. |
| Provisional | A case that tests a rule the team has not yet recorded in truth. It is run and reported, but a failure is a question for the owner and the team, not a defect. |

Results are recorded in `documents/test-case-template.xlsx`, one row per case: Test Case,
Inputs, Expected Output, Pass/Fail, Failure Description, Tester, Date Tested. Defects are
raised as GitHub Issues under the bug policy in `documents/test_plan.md` §2.3.1 and listed
in `TrackModel/BUGS.md` while open.

---

## 5. Test Deliverables

- This test plan.
- **Automated suites** in `TrackModel/tests/`:
  - `test_layout.py`, `test_load_layout.py`, `test_green_line.py`, `test_green_direction.py`;
  - `test_wiring.py`, `test_circuit_and_ambient.py`, `test_heaters_and_failures.py`,
    `test_sim_time.py`, `test_contract.py`;
  - `test_module_process.py`, `test_harness_edges.py`;
  - `test_codec.py`, `test_link.py`, `test_end_to_end.py`, `test_block_filter.py`;
  - the shared helpers `helpers.py` and `qt_helpers.py`.
- **Test data:**
  - the track layouts `green_line.json`, `red_line.json` and `blue_line.json`;
  - the small and malformed layouts built inside `test_green_direction.py`,
    `test_layout.py` and `test_load_layout.py`.
- **Test tools:**
  - the test UI (`test_ui/`), with its stand-in Track Controller, Train Model and clock;
  - the test link (`test_link/`);
  - `run_tests.py`, which prints each test with its description and PASS or FAIL.
- **The manual script** `MANUAL_TESTS.md` (TC-01 to TC-30), ticked as it is run.
- **The completed test case sheet** (`test-case-template.xlsx`), including the manual cases.
- **The suite's console log** for each recorded run (`pytest`, `mypy`, `flake8`).
- **Defect notes** for every failure, linked from the sheet's Failure Description.

---

## 6. Responsibilities

| Role | Responsibility | Owner |
|------|-----------------|-------|
| Test manager | Owns this plan; keeps sections 2 and 7 in step with the SRS and the SDD | SeeingEyeTree |
| Test designer | Writes the automated cases and the manual script | SeeingEyeTree |
| Test executor | Runs the suite before every push and the manual cases before each demonstration; records results | SeeingEyeTree |
| Interface reviewer (Track Controller) | Confirms the occupancy, read-back and command formats, and the fail-safe failure effects (7.8) | Track Controller owners (Harry Tye, SW; HW owner) |
| Interface reviewer (Train Model) | Confirms Track Info, track circuit, beacon, offset and polarity (7.4 to 7.6) | Kevin Schillinger |
| Interface reviewer (CTC Office) | Confirms ticket sales format and rate (7.9) | CTC Office owner |
| Integration | Runs the module under the central harness (7.14) | SeeingEyeTree, with the harness owner |
| Reviewer | Reviews the plan and the results | Course instructor and team |

---

## 7. Test Items

**How to run.**

The automated suite, from `TrackModel/`:

```bash
.venv/Scripts/python run_tests.py
```

```bash
.venv/Scripts/python -m pytest
```

```bash
.venv/Scripts/python -m mypy --strict --follow-imports=silent -p track_model -p tests -p test_link -p test_ui -m common.harness.track_model_edges -m main -m run_tests
```

```bash
.venv/Scripts/python -m flake8 --max-line-length=79 track_model tests test_link test_ui main.py run_tests.py ../common/harness
```

For a manual run, from the repository root, start the module window and then the test UI:

```bash
TrackModel/.venv/Scripts/python TrackModel/main.py
```

```bash
TrackModel/.venv/Scripts/python TrackModel/test_ui/main.py
```

**Notation.**

- **S** marks a safety case (section 4).
- *Manual* marks a case run by hand in the windows (`MANUAL_TESTS.md` TC-nn).
- *Provisional* marks a case that tests a rule not yet recorded in truth (section 4).
- Block names are short where the line is clear: `D-13` is `GREEN D-13`.

**Build for all items.**

- Branch `chore/test-plan`, commit `083f659`.
- Python 3.14.8 and PySide6 6.11.2 (`TrackModel/.venv`).
- Last full run: 2026-11-13. `pytest`: 325 passed, 0 failed.
- Static checks, same run: `mypy --strict` reports **5 errors** (`tests/test_wiring.py:447`,
  `tests/test_harness_edges.py:140, 158, 159` twice), all in test code. `flake8` reports **11
  lines** (for example `test_ui/harness.py:505` and `track_model/model.py:84` too long,
  `tests/test_wiring.py:19` unused import). Under section 4 these fail the build until fixed;
  they are not yet in `BUGS.md`.
- Open bugs: none (`BUGS.md`).

### 7.1. Layout loader (layout)

- **Item Description:** `track_model/layout.py`.
  - Reads `*_line.json`, converts units (grade % to degrees, km/h to m/s), parses switch
    text, finds signals, crossings, stations and beacons, and builds the track graph
    (`Layout.next_block`).
- **Version/Build:** as above.
- **Test Approach:** Unit tests on the loader, using the real layouts and small malformed
  files. Direction cases build a layout with `next_blocks` altered, and check the loader
  refuses it.

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| TM-L-01 | All shipped lines load | `green_line.json`, `red_line.json`, `blue_line.json` | Three layouts, no error | REQ-FUNC-015, REQ-INTF-012 | test_layout :: test_all_three_lines_load |
| TM-L-02 | IDs are line-and-section strings | Any loaded block | `"<LINE> <section>-<number>"` | — | test_layout :: test_ids_are_strings_with_line_and_section |
| TM-L-03 | Units convert on read | A block with grade in % and limit in km/h | Grade in degrees, speed limit in m/s | REQ-FUNC-016.1, 016.4 | test_layout :: test_units_are_converted_on_read |
| TM-L-04 | Station side and underground flag | A station row | Platform side and underground flag carried | REQ-FUNC-016.8 | test_layout :: test_station_side_and_underground |
| TM-L-05 | Switch text parses | Every form in the course files: `12-13; 1-13`, `76-77;77-101`, `57-yard`, `Yard-63`, `5 to 11` | Point block and its legs as `(point, leg)` pairs, `None` for the yard | REQ-FUNC-016 | test_layout :: test_switch_text_parses |
| TM-L-06 | Unreadable switch text is refused | Malformed switch text | Error naming the row | REQ-NFR-004 | test_layout :: test_unreadable_switch_text_is_rejected |
| TM-L-07 | Switches and crossings are found | Each line | The expected switch and crossing sets | REQ-FUNC-016.6 | test_layout :: test_switches_found; test_crossings_found |
| TM-L-08 | Segment breaks are not joined | Blocks not joined by rail | No edge between them | REQ-FUNC-019 | test_layout :: test_segment_breaks_are_not_joined |
| TM-L-09 | `next_block` follows the switch as set | A switch set NORMAL, then REVERSE | The next block is the matching leg | F12 | test_layout :: test_next_block_follows_the_given_switch_position |
| TM-L-10 | A trailing move leaves by the fixed side | A train entering a switch from a leg | It leaves by the fixed side | F12 | test_layout :: test_trailing_move_leaves_by_the_fixed_side |
| TM-L-11 | A yard leg and a dead end | The yard switch; a dead-end block | Yard leg returns `None`; dead end stays put | D022 | test_layout :: test_yard_leg_returns_none; test_dead_end_stays_put |
| TM-L-12 | Signals stand at switches; beacons flank stations | Each line | One signal per switch point; a beacon on every neighbour of a station block | REQ-FUNC-016.8 | test_layout :: test_signals_stand_before_each_switch; test_beacons_flank_stations |
| TM-L-13 | Red's yard reading uses the exit direction | `75-yard` on block 9's row | Parsed as a switch at block 75 | — | test_layout :: test_red_yard_interpretation_uses_exit_direction |
| TM-L-14 | Every Green block has `next_blocks` | `green_line.json` | All 150 blocks annotated | REQ-FUNC-016.5 | test_green_direction :: test_every_green_block_has_next_blocks |
| TM-L-15 | Direction at the key points; two-way and one-way runs | Green | Two-way on 13 to 28 and 77 to 85; one way elsewhere; A to C run 12 to 1 then 1 to 13 | REQ-FUNC-016.5 | test_green_direction :: test_next_blocks_at_the_key_points; test_two_way_blocks_are_d_to_f_and_n; test_one_way_runs; test_a_to_c_loop_runs_round_into_d |
| TM-L-16 | The annotation matches the inferred track; every block is reachable from the yard | Green | Same graph as the old inference; no orphan block | REQ-FUNC-016.5 | test_green_direction :: test_annotation_matches_the_old_inferred_track; test_every_block_reachable_from_the_yard |
| TM-L-17 | Red and Blue are annotated two-way | Red, Blue | Every block lists each neighbour | REQ-FUNC-016.5 | test_green_direction :: test_red_and_blue_are_annotated_two_way |
| TM-L-18 | A new train heads the way its block runs | A train placed on a one-way block, and on a two-way block | Follows the block's direction; two-way heads to the higher number; can roll back to the block behind | F12 | test_green_direction :: test_new_train_heads_the_way_the_block_runs; test_new_train_rolls_back_to_the_block_behind |
| TM-L-19 | Bad direction data is refused | Partial annotation, unknown next block, yard without a yard switch, unswitched jump, missing switch leg, block with no way in | The loader refuses each, naming the fault | REQ-NFR-003 | test_green_direction :: test_partial_annotation_is_rejected; test_unknown_next_block_is_rejected; test_yard_without_a_yard_switch_is_rejected; test_unswitched_jump_is_rejected; test_missing_switch_leg_is_rejected; test_block_with_no_way_in_is_rejected |
| TM-L-20 | Green's yard return is protected | Green with the return leg removed, or a leg added to the yard entry | Refused | D022 | test_green_direction :: test_missing_green_yard_return_is_rejected; test_green_yard_entry_cannot_gain_a_return_leg |
| TM-L-21 | Load a layout at run time | A good JSON file of an existing line, then of a new line | The file replaces the line of the same name, or adds one; the module restarts (no trains, devices at rest) | REQ-FUNC-015 | test_load_layout :: test_load_replaces_the_line_of_the_same_name; test_load_restarts_the_module; test_load_a_different_track |
| TM-L-22 | A bad or missing layout file changes nothing | A malformed file; a path that does not exist | An error; every loaded line as it was | REQ-NFR-004 | test_load_layout :: test_bad_file_changes_nothing; test_missing_file_raises |
| TM-L-23 | The system loads Green and Red only | Module started as the harness starts it | Green and Red loaded; Blue not | D023 | test_module_process :: test_the_system_loads_green_and_red_only |
| TM-L-24 | Load a track from JSON in the window | *Manual:* **Load track…** with a good file, then a bad one | Good: line replaced, module restarted. Bad: nothing changes | REQ-FUNC-015 | *Manual* TC-29 |

### 7.2. Green Line data

- **Item Description:** `green_line.json` as loaded by `layout.py`. The Green Line is the
  line the system runs on the Track Controller SW (D021), so its data is tested in detail.
- **Version/Build:** as above.
- **Test Approach:** Unit tests that read the real file and compare with the course data.

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| TM-G-01 | 150 blocks, in order, with the right IDs | `green_line.json` | 150 blocks; the expected ID list | REQ-FUNC-015 | test_green_line :: test_green_has_150_blocks_in_order; test_green_block_ids |
| TM-G-02 | Units converted | Selected Green blocks | Grade in degrees, length in m, limit in m/s, as computed by hand | REQ-FUNC-016.1 to 016.4 | test_green_line :: test_green_units_converted |
| TM-G-03 | Stations | The station list | The expected stations and their blocks | REQ-FUNC-016 | test_green_line :: test_green_station_list; test_green_station |
| TM-G-04 | Station neighbours carry the beacon | Blocks next to a station; Mt Lebanon | Each carries the station's beacon; the Mt Lebanon beacon reaches the 101 branch | REQ-FUNC-016.8, REQ-FUNC-046 | test_green_line :: test_green_station_neighbours_carry_its_beacon; test_mt_lebanon_beacon_reaches_the_101_branch |
| TM-G-05 | Six switches, a signal at each; crossings | Green | Exactly six switches; a signal at each point; the expected crossings | REQ-FUNC-016.6, 023 | test_green_line :: test_green_switches; test_green_has_exactly_six_switches; test_green_signals_stand_at_each_switch; test_green_crossings |
| TM-G-06 | Unjoined ends | Green | The expected unjoined branch ends | — | test_green_line :: test_green_unjoined_ends |
| TM-G-07 | The full course loop | A train driven round Green | It visits the blocks in the course order and returns | F12 | test_green_line :: test_full_green_loop_follows_the_course_route |
| TM-G-08 | Occupancy follows the train round the loop | The same run | Exactly the train's block is occupied each tick | REQ-FUNC-019 | test_green_line :: test_occupancy_follows_the_train_round_the_loop |
| TM-G-09 | Polarity flips at every block change | The same run | Polarity reverses at each boundary, including where switches join odd and even numbers | `signals/track-info` | test_green_line :: test_polarity_flips_at_every_green_block_change |
| TM-G-10 | Switches never move on their own | A long run with no commands | Every switch where it started | F11 | test_green_line :: test_switch_positions_never_change_on_their_own |
| TM-G-11 | Taking each leg at 57 and 77 | Switch 57 NORMAL; switch 77 NORMAL | 57 stays on the line and rejoins at 63; 77 sends the return trip to 76 | F12 | test_green_line :: test_57_normal_stays_on_the_line_and_rejoins_at_63; test_77_normal_sends_the_return_trip_to_76 |
| TM-G-12 | Out of the yard | A new train placed at `Yard-63` | It heads 63 to 64 and does not roll back into the yard | D022 | test_green_line :: test_new_train_at_63_heads_out_of_the_yard; test_train_out_of_the_yard_does_not_roll_back_into_it |
| TM-G-13 | Per-block circuit and light round the loop | A run with a different command per block | Each tick the train gets its block's speed and authority and the light ahead | F6, F13 | test_green_line :: test_per_block_speed_and_authority_round_the_loop; test_light_ahead_every_tick_round_the_loop |
| TM-G-14 | Boarding at Green stations; two trains | Trains stopped at stations; two trains on the line | Each boards at its station; each gets its own block's signal | F3, F4 | test_green_line :: test_boarding_at_green_stations; test_two_trains_on_green_get_their_own_blocks_signal |
| TM-G-15 | End-to-end Green demonstration | *Manual:* TC-20 to TC-25 | As each script states | REQ-FUNC-016, 019, 020 | *Manual* TC-20 to TC-25 |

### 7.3. Commands and device state (model)

- **Item Description:** `TrackModel.step`, steps 1 and 2 (`_validate`, `_apply_commands`), and
  `_controller_outputs`.
  - Switch, light and gate commands from the Track Controller, and the actual state read
    back.
- **Version/Build:** as above.
- **Test Approach:** Component tests through `step`. Each case sends commands, steps, and
  compares the read-back in `TrackControllerOutputs`.

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| TM-C-01 | Commands become states | A switch REVERSE, a light GREEN, a gate closed | Each read back as commanded | REQ-FUNC-023, REQ-INTF-018 | test_wiring :: test_commands_become_states |
| TM-C-02 | An absent command keeps its last value | A command, then a tick without it | The device keeps its value | REQ-INTF-018 | test_wiring :: test_absent_commands_keep_their_last_value |
| TM-C-03 | Devices start safe | A new module | Switches NORMAL, gates up, lights RED, heaters off | F9 | test_wiring :: test_devices_start_at_safe_defaults |
| TM-C-04 | The Track Model does not route | A switch set to a leg; a train arrives | The train takes the leg the switch is set to; nothing else decides | F11 | test_wiring :: test_train_takes_the_commanded_leg |
| TM-C-05 | Commands reach the test UI from the Track Controller panel | *Manual:* set a switch, a light, a gate and a heater; step twice | Read-back shows each; values persist on the second step | REQ-FUNC-023 | *Manual* TC-03 |
| TM-C-06 | Snapshot has no side effects and follows the last step | Call `snapshot()` twice; step; call again | Equal copies; the third reflects the step | — | test_contract :: test_snapshot_has_no_side_effects; test_snapshot_reflects_last_step |
| TM-C-07 | The module matches its protocol | The `TrackModel` class | Conforms statically and by signature; `step` returns outputs | — | test_contract :: test_protocol_conformance_static; test_protocol_members_match_signatures; test_step_returns_outputs |

### 7.4. Track circuit: speed and authority (model)

- **Item Description:** `_feed` (the track circuit part), `_apply_commands`.
  - Commanded speed (m/s) and authority (blocks) per block, delivered to the train in the
    block, valid for one tick.
- **Version/Build:** as above.
- **Test Approach:** Component tests through `step`; the train's feed in
  `TrackModelOutputs.train_feeds` is compared with what was commanded.

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| TM-T-01 | The feed carries the block and its circuit | A train in a commanded block | Track Info for the block, with the block's speed and authority | REQ-FUNC-020.1, `signals/track-info` | test_wiring :: test_feed_carries_the_block_and_track_circuit |
| TM-T-02 | Speed and authority come from the occupied block | Different commands on three blocks; a train in the middle one | The train gets the middle block's values only | REQ-FUNC-020.1 | test_wiring :: test_speed_and_authority_come_from_the_occupied_block |
| TM-T-03 | Values last one tick | Command once; step twice | Delivered on the commanded tick; zero the tick after | `signals/track-signal` | test_wiring :: test_speed_and_authority_last_one_tick |
| TM-T-04 | A value for an empty block is not kept for a later train | Command an empty block; a train arrives later | The train gets zero | `signals/track-signal` | test_wiring :: test_a_value_for_an_empty_block_is_not_kept_for_a_later_train |
| TM-T-05 | Two trains in one block get the same signal | Two trains reported in one block | Both get the block's values | — | test_wiring :: test_two_trains_in_one_block_get_the_same_signal |
| TM-T-06 | An uncommanded block sends zero and no authority | A train in a block never commanded | Speed 0, authority 0 | `signals/track-signal` | test_wiring :: test_uncommanded_block_sends_zero_and_no_authority |
| TM-T-07 | The window shows the circuit | A commanded block; then a dead circuit | The snapshot shows the commanded speed and authority; a dead circuit shows 0 and 0 | REQ-FUNC-016 | test_circuit_and_ambient :: test_snapshot_shows_commanded_speed_and_authority; test_dead_circuit_shows_zero |
| TM-T-08 | The window's Cmd mph and Auth columns | *Manual:* command a block; fail its circuit | Columns show the command, then 0 and 0 | REQ-FUNC-016 | *Manual* TC-05, TC-30 |

### 7.5. Train movement and occupancy (model)

- **Item Description:** `_move_trains`, `_advance`, `_behind`, `_carry_into`,
  `Layout.next_block`.
  - A train's block from its offset, with the carry, rollback, stale-report handling, and
    entry to and exit from the yard.
- **Version/Build:** as above.
- **Test Approach:** Component tests with `report(...)` inputs that put a train at chosen
  offsets, and a full-loop run in 7.2.

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| TM-M-01 | An offset inside the block does not move the train | Offset below the block length | Same block, occupied | REQ-FUNC-019 | test_wiring :: test_offset_inside_the_block_does_not_move_the_train |
| TM-M-02 | An offset past the end advances and flips polarity | Offset at or past the length | Next block occupied; previous cleared; polarity reversed | REQ-FUNC-019, `signals/track-info` | test_wiring :: test_offset_past_the_end_advances_and_flips_polarity |
| TM-M-03 | A stale report does not advance twice | A report still naming the block just left | Ignored; the train stays in the new block | REQ-FUNC-019 | test_wiring :: test_stale_report_does_not_advance_twice |
| TM-M-04 | A negative offset rolls back | Offset below 0 | The train is in the previous block | REQ-FUNC-019 | test_wiring :: test_negative_offset_rolls_back_to_the_previous_block |
| TM-M-05 | Continued and slow rollback | Rollback over several blocks; a slow rollback | Keeps going back; a slow one stays in the block it rolled into | REQ-FUNC-019 | test_wiring :: test_continued_rollback_keeps_going_back; test_slow_rollback_stays_in_the_block_it_rolled_into |
| TM-M-06 | Overshoot is carried into the next block | Offset 52 m on a 50 m block | The new block's true offset is 2 m | REQ-FUNC-019 | test_wiring :: test_forward_overshoot_is_carried_into_the_next_block |
| TM-M-07 | A stale report after a rollback is ignored | Rollback, then a report naming the old block | Ignored | REQ-FUNC-019 | test_wiring :: test_stale_report_after_rollback_is_ignored |
| TM-M-08 | Rollback through a switch follows its position | Roll back across a switch set each way | Enters the leg the switch is set to | F12 | test_wiring :: test_rollback_through_a_switch_follows_its_position |
| TM-M-09 | Two trains each occupy their own block | Two reports | Two blocks occupied | REQ-FUNC-019 | test_wiring :: test_two_trains_each_occupy_their_block |
| TM-M-10 | A train that leaves the inputs leaves the track | A report, then none | Its block clears | REQ-FUNC-019 | test_wiring :: test_train_leaving_the_inputs_leaves_the_track |
| TM-M-11 | A train runs into the yard | A train whose next block is the yard | It is removed; occupancy clears | D022 | test_wiring :: test_train_runs_into_the_yard |
| TM-M-12 | `block_changed` is recorded, not used | A report with the flag set and one with it clear, same offsets | Same result for both | — | test_wiring :: test_block_changed_is_recorded_not_used |
| TM-M-13 | A report with no block yet is ignored | Block `""` | Skipped; the tick is not rejected; the train is not on the track | REQ-NFR-004 | test_wiring :: test_report_with_no_block_yet_is_ignored; test_train_reporting_no_block_leaves_the_track |
| TM-M-14 | Track Model and Train Model agree on position | A train driven by the real Train Model round Green and while rolling back | Positions agree to the nanometre | REQ-FUNC-019 | test_end_to_end :: test_train_travels_and_follows_the_switch; test_green_train_leaves_the_yard_and_reaches_mt_lebanon |
| TM-M-15 | Movement, occupancy and polarity | *Manual:* push a train over a boundary (offset 49, speed 20) | Next block occupied; polarity reversed; the window follows | REQ-FUNC-019 | *Manual* TC-04, TC-06 |
| TM-M-16 | The train takes the leg the switch is set to | *Manual:* switch NORMAL, then REVERSE | Train enters each leg accordingly | F12 | *Manual* TC-07, TC-22 |
| TM-M-17 | Rollback; yard; full loop | *Manual:* roll back; run into and out of the yard; run the full loop | As each script states | REQ-FUNC-019 | *Manual* TC-09, TC-15, TC-20, TC-21 |
| TM-M-18 | Direction of travel | *Manual:* new train on one-way and two-way blocks | Heads the way the block runs | REQ-FUNC-016.5 | *Manual* TC-25 |

### 7.6. Signals and beacons (model)

- **Item Description:** `_signal_state`, `_signal_seen`, `_beacons` (in `layout.py`), and
  the beacon part of `_feed`.
  - One light per switch, at its point. Each train is sent the light ahead of it. Beacons sit
    on every neighbour of a station block.
- **Version/Build:** as above.
- **Test Approach:** Component tests through `step`.

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| TM-S-01 | The signal seen reaches the train every tick | A light commanded GREEN, then RED | `signal_seen` shows the light ahead; a change reaches the train on the next tick | REQ-FUNC-023.2 | test_wiring :: test_signal_seen_every_tick_and_a_change_reaches_it |
| TM-S-02 | An ordinary block sees the light ahead | A train on a block with no light of its own | The first switch ahead it will come onto from the fixed side | REQ-FUNC-023.2 | test_wiring :: test_an_ordinary_block_still_sees_the_light_ahead |
| TM-S-03 | A light is seen from the fixed side only | A train trailing through a switch from a leg | It does not see that switch's light | REQ-FUNC-023.2 | test_end_to_end :: test_signal_colour_follows_the_light_ahead |
| TM-S-04 | No beacon away from stations | A train in a block with no station neighbour | No beacon in its feed | REQ-FUNC-046 | test_wiring :: test_no_beacon_away_from_stations |
| TM-S-05 | Beacon carries the station and platform side | A train next to a station | A beacon with the station name and platform side | REQ-FUNC-046 | test_harness_edges :: test_beacon_maps_to_the_catalog_beacon; test_station_name_and_doors_cross_the_edges |
| TM-S-06 | The beacon payload fits | A beacon whose canonical payload is over 128 characters | Refused at the edge, never truncated | REQ-FUNC-046 | test_harness_edges :: test_beacon_edge_checks_the_complete_payload; test_malformed_beacon_is_rejected_at_the_edge |
| TM-S-07 | A signal is seen once, on entry | *Manual:* a train enters a signal block, then stays | Seen on entry; the train sees the light ahead after | REQ-FUNC-023.2 | *Manual* TC-08, TC-23 |
| TM-S-08 | Beacons next to stations | *Manual:* a train next to and away from a station | Beacon next to the station only | REQ-FUNC-046 | *Manual* TC-10, TC-24 |

### 7.7. Heaters, temperature and ambient (model)

- **Item Description:** `_heater_on`, `_update_track_temps`, ambient handling in `step`.
  - Per-section heaters switched by the Track Model (D026), the section's track temperature
    easing toward a target, and the ambient temperature set in the window or the test UI.
- **Version/Build:** as above.
- **Test Approach:** Component tests that step many ticks and read the temperature, with
  `HEATER_RISE_C` (10 °C) and `TRACK_TIME_CONSTANT_S` (300 s) as the references.
- **Provisional.** D026 gives the Track Model the switching but does not state the rule.
  The cases marked *Provisional* test the owner's working rule: on at or below 0 °C, off
  above it, no hysteresis. A heater command from the Track Controller is accepted but not
  applied. The heater rise and the warm-up time are placeholders. A proposal for the rule
  goes to `truth/_inbox/` before these cases are treated as acceptance evidence.

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| TM-H-01 | Every section has a heater and a temperature | Each loaded line | One heater state and one track temperature per section | REQ-FUNC-016.7, 022 | test_heaters_and_failures :: test_every_section_has_a_heater_and_a_temperature |
| TM-H-02 | An unknown heater section is refused | A heater command for `GREEN Q` | Rejected whole | REQ-NFR-004 | test_heaters_and_failures :: test_unknown_heater_section_is_rejected |
| TM-H-03 | The track starts at ambient | Ambient set; first tick | Track temperature equals ambient | REQ-FUNC-021 | test_heaters_and_failures :: test_track_starts_at_ambient |
| TM-H-04 | A heater warms its section | Ambient below 0 °C; many ticks | The section eases toward ambient + 10 °C | REQ-FUNC-022 | test_heaters_and_failures :: test_heater_warms_its_section_toward_ambient_plus_rise |
| TM-H-05 | A heater does not change ambient | The same run | Ambient is still the input value | REQ-FUNC-022 | test_heaters_and_failures :: test_heater_does_not_change_ambient |
| TM-H-06 | The track follows a change in ambient gradually | Ambient steps from 20 °C to 5 °C | Track temperature eases down over minutes, not in one tick | REQ-FUNC-021 | test_heaters_and_failures :: test_track_follows_a_change_in_ambient_gradually |
| TM-H-07 | A heater off lets the track cool back | Heaters on, then ambient rises above 0 °C | The section cools toward ambient | REQ-FUNC-022 | test_heaters_and_failures :: test_heater_off_lets_the_track_cool_back |
| TM-H-08 | Heaters switch at the freezing point *(Provisional)* | Ambient 0 °C, then 0.1 °C | On at 0 °C and below; off above | D026 | test_heaters_and_failures :: test_heaters_switch_at_the_freezing_point |
| TM-H-09 | No ambient keeps the heaters as they were *(Provisional)* | A tick with no ambient after the heaters came on | Heaters unchanged | D026 | test_heaters_and_failures :: test_no_ambient_keeps_the_heaters_as_they_were |
| TM-H-10 | A heater command is not applied | A Track Controller heater command against the Track Model's own state | Accepted; the Track Model's own state wins | D026 | test_heaters_and_failures :: test_a_heater_command_is_not_applied |
| TM-H-11 | Ambient set in the window beats the test UI | A window value, then a test UI value | The window's value holds until reset | REQ-FUNC-021 | test_circuit_and_ambient :: test_ambient_set_in_ui_beats_the_test_ui |
| TM-H-12 | The test UI's ambient applies until one is set; reset clears the override | Test UI ambient only; then reset | The test UI's value applies; after reset the override is gone | REQ-FUNC-021 | test_circuit_and_ambient :: test_test_ui_ambient_applies_until_one_is_set; test_reset_clears_the_ambient_override |
| TM-H-13 | A non-finite ambient is refused; none keeps the current one | `NaN` or `inf`; an input with no ambient | Rejected whole; the current ambient kept | REQ-NFR-003, 004 | test_circuit_and_ambient :: test_non_finite_ambient_is_rejected; test_no_ambient_sent_keeps_the_current_one |
| TM-H-14 | Ambient is stored | `ambient_temp_c = 12.5` | Read back unchanged | REQ-FUNC-021 | test_wiring :: test_ambient_temperature_is_stored |
| TM-H-15 | Heaters switch themselves; ambient stays put | *Manual:* ambient 20 °F, then 40 °F; watch the heaters and track temperature | Heaters on at or below freezing, off above; temperatures ease; ambient does not move | REQ-FUNC-021, 022 | *Manual* TC-27 |

### 7.8. Failure modes (model)

- **Item Description:** `set_block_failure`, `CIRCUIT_DEAD`, `_circuit_dead`, `_powered_off`,
  and the effects in `_feed`, `_controller_outputs`, `_signal_state`, `_gate_closed`,
  `_heater_on`, `_apply_commands`.
  - Broken rail, track circuit failure and power failure, injected from the window (Murphy)
    or the test UI. Each acts fail-safe.
- **Version/Build:** as above.
- **Test Approach:** Component tests that inject a failure, step (or do not), and check the
  read-back and the train's feed. Cases that protect a safe state are **S**.
- **Note.** The effects are the owner's fail-safe reading and have not been agreed with the
  Track Controller (README, provisional item 6). The Track Controller owners review them
  (section 6).

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| TM-F-01 **S** | A failed block reads occupied | A broken rail, a track circuit failure and a power failure on an empty block | The block reads occupied in each case | REQ-FUNC-024.1 to 024.3 | test_heaters_and_failures :: test_failed_block_reads_occupied |
| TM-F-02 **S** | A failed block carries no track signal | A train in a failed block, with a speed and authority commanded | The train's feed carries 0 and no authority | REQ-FUNC-024 | test_heaters_and_failures :: test_failed_block_carries_no_track_signal |
| TM-F-03 | Clearing a failure restores the block | A failure, then cleared | Occupancy and circuit return to normal | REQ-FUNC-024 | test_heaters_and_failures :: test_clearing_a_failure_restores_the_block |
| TM-F-04 **S** | A failure reaches the outputs before the next step | `set_block_failure` between two ticks | The Track Controller's read-back already shows it | REQ-FUNC-024 | test_heaters_and_failures :: test_failure_shows_as_occupied_before_the_next_step; test_wiring :: test_failure_reaches_the_outputs_between_steps |
| TM-F-05 **S** | A power failure holds the switch | Switch NORMAL; power fails; command REVERSE | Switch stays NORMAL; the command is kept and applies when power returns | REQ-FUNC-024.3 | test_heaters_and_failures :: test_power_failure_freezes_the_switch |
| TM-F-06 **S** | A power failure shows RED, to trains too | A GREEN light; power fails | Read-back RED; the train sees RED | REQ-FUNC-024.3 | test_heaters_and_failures :: test_power_failure_turns_the_light_red_for_trains_too |
| TM-F-07 **S** | A power failure drops the crossing gates | A gate up; power fails | The gate is down | REQ-FUNC-024.3 | test_heaters_and_failures :: test_power_failure_drops_the_crossing_gates |
| TM-F-08 | A power failure stops its section's heaters | Heaters on; power fails in the section | The section's heaters are off; other sections unchanged | REQ-FUNC-024.3, 022 | test_heaters_and_failures :: test_power_failure_stops_its_sections_heaters |
| TM-F-09 | Other failures leave devices powered | A broken rail; a track circuit failure | Switch, light, gate and heaters still follow their commands | REQ-FUNC-024.1, 024.2 | test_heaters_and_failures :: test_other_failures_leave_devices_powered |
| TM-F-10 | A failure reaches the test UI at once | *Manual:* Murphy a block in the window | The test UI shows it occupied with no step | REQ-FUNC-024 | *Manual* TC-12 |
| TM-F-11 | Power failure from the test UI; failure effects on a train | *Manual:* inject each failure under a train | As each script states | REQ-FUNC-024 | *Manual* TC-13, TC-28 |

### 7.9. Stations, tickets and boarding (model)

- **Item Description:** `_sell_tickets`, `_board`, and `_ctc_outputs`.
  - Ticket sales per station, the queue of waiting passengers, boarding of a stopped train
    with a door open, and the sales sent to the CTC Office.
- **Version/Build:** as above.
- **Test Approach:** Component tests through `step`. Rate and demand cases step many ticks
  and compare with the rule: about 12 tickets per simulated minute per station
  (`TrackConfig.tickets_per_minute`). Random cases use a seed.

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| TM-K-01 | Sales go to the CTC Office as station pairs | A run with a train on the line | `ctc` carries `(count, station)` pairs | REQ-FUNC-017.1 | test_wiring :: test_ticket_sales_go_to_the_ctc_office; test_harness_edges :: test_ticket_sales_reach_the_ctc_office_as_station_pairs |
| TM-K-02 | Sales are events with no running total | Several ticks | Each tick reports only that tick's sales | REQ-FUNC-017 | test_wiring :: test_ticket_sales_are_events_with_no_running_total; test_reset_clears_this_ticks_sales |
| TM-K-03 | Sales are reproducible with a seed | Two runs with the same seed | Identical sales | — | test_wiring :: test_ticket_sales_are_reproducible_with_a_seed |
| TM-K-04 | The rate holds at any tick length | The same simulated minutes at `dt` 0.1 s and 1 s | Close to the same number of tickets | REQ-NFR-002 | test_wiring :: test_ticket_rate_holds_at_any_tick_length |
| TM-K-05 | Free spaces and speed raise demand; a full train adds none | Trains with free spaces, full, stopped and moving | More sales with free spaces; none added by a full train; more by faster trains than stopped ones | REQ-FUNC-017 | test_wiring :: test_trains_with_free_spaces_raise_ticket_sales; test_a_full_train_adds_no_demand; test_faster_trains_raise_sales_more_than_stopped_ones |
| TM-K-06 | No tickets sell until a train is on the line | No trains | No sales | REQ-FUNC-017 | test_wiring :: test_no_tickets_sell_until_a_train_is_on_the_line |
| TM-K-07 | Demand opens per line and stays open; the wait is timed from opening | A train on one line | Demand opens on that line only and stays open; waits count from when it opened | REQ-FUNC-017 | test_wiring :: test_demand_opens_per_line_and_stays_open; test_the_wait_is_timed_from_when_demand_opens |
| TM-K-08 | A train idle for two minutes adds no demand | A stopped train for over two minutes | No new demand from it | REQ-FUNC-017 | test_wiring :: test_a_train_idle_for_two_minutes_adds_no_demand |
| TM-K-09 | The queue is capped; a long wait makes people give up | A long run with no train | The queue stops at its cap and then drains | REQ-FUNC-017 | test_wiring :: test_the_queue_at_a_station_is_capped; test_a_long_wait_makes_people_give_up |
| TM-K-10 | A stopped train boards up to its capacity | A train stopped in a station block, door open | Passengers boarded up to capacity; the queue falls by that number | REQ-FUNC-018.1 | test_wiring :: test_stopped_train_boards_up_to_its_capacity |
| TM-K-11 | A moving train, or closed doors, board nobody | A moving train; a stopped train with doors closed | None boarded; the queue unchanged | REQ-FUNC-018.1 | test_wiring :: test_moving_train_does_not_board; test_closed_doors_board_nobody_and_keep_the_queue |
| TM-K-12 | Boarding at Green stations | See TM-G-14 | As there | REQ-FUNC-018.1 | test_green_line :: test_boarding_at_green_stations |
| TM-K-13 | Ticket sales and boarding in the windows | *Manual:* a train at a station, doors open | `sold now` shows sales; boarded count shown; the window follows | REQ-FUNC-017, 018 | *Manual* TC-11 |
| TM-K-14 | Disembarking is shown | *Manual:* the Train Model discharges passengers at a station | The Track Model window shows the number disembarking | REQ-FUNC-018.2 | *Planned:* no automated test; the Track Model receives no disembark count today. Confirm the source with the Train Model owner |

### 7.10. Input validation and reset (model)

- **Item Description:** `_validate`, `reset`, `edit_block`, and the `dt` and clock-time
  checks.
- **Version/Build:** as above.
- **Test Approach:** Component tests that send a bad input and compare `snapshot()` before
  and after, to prove that nothing changed.

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| TM-V-01 | Invalid input changes nothing | An unknown block, switch, signal, crossing or section; a negative or fractional speed; a non-finite number | The tick raises; the snapshot is as before | REQ-NFR-003, 004 | test_wiring :: test_invalid_input_changes_nothing |
| TM-V-02 | A bad `dt` is rejected | `dt` of 0, -0.1, `NaN`, `inf` | Error; nothing changes | REQ-NFR-004, REQ-INTF-013 | test_wiring :: test_bad_dt_is_rejected |
| TM-V-03 | An unknown block failure is rejected | `set_block_failure` on a block that does not exist | Error; nothing changes | REQ-NFR-004 | test_wiring :: test_unknown_block_failure_is_rejected |
| TM-V-04 | Reset clears trains and commands | A running module with trains and commands, then `reset` | No trains; devices at rest | REQ-NFR-005 | test_wiring :: test_reset_clears_trains_and_commands; test_end_to_end :: test_reset_returns_device_commands_to_defaults |
| TM-V-05 | A block edit moves the boundary (test only) | `edit_block` with a new length | The boundary moves to the new length | — | test_wiring :: test_edit_block_changes_where_the_boundary_is |
| TM-V-06 | No clock time by default; a step records it; reset clears it | A step with and without `sim_time_s`; reset | None by default; recorded after a step; cleared by reset | REQ-INTF-013 | test_sim_time :: test_no_clock_time_by_default; test_step_records_clock_time; test_reset_clears_clock_time |
| TM-V-07 | A bad clock time is rejected whole | `sim_time_s` of `NaN` or -1 | Error; nothing changes | REQ-NFR-004 | test_sim_time :: test_bad_clock_time_rejected_whole |
| TM-V-08 | Clock time crosses the edge and the link | `sim_time_s` sent through the harness edge and the test link | Arrives unchanged at the module | REQ-INTF-013 | test_sim_time :: test_edge_passes_clock_time; test_clock_time_crosses_the_link |
| TM-V-09 | Invalid input is rejected whole in the windows | *Manual:* send a bad value from the test UI | The test UI shows the rejection; the module is unchanged | REQ-NFR-004 | *Manual* TC-16 |
| TM-V-10 | Reset | *Manual:* reset after a run | Trains gone, devices safe, ambient override cleared | REQ-NFR-005 | *Manual* TC-19 |

### 7.11. Track Model window (state, QML)

- **Item Description:** `track_model/state.py`, `ui/Main.qml`, `ui/MainView.qml`.
  - The module's state in display units (ft, mph, °F), the block, switch and light tables, the
    selected-block panel, the ambient control, Murphy and Load track.
- **Version/Build:** as above.
- **Test Approach:** There is no automated test of the window itself, because it is a view of
  `snapshot()` (tested in 7.3 and 7.4). The window is checked by the manual script, and
  `state.py`'s conversions by the manual cases below. Adding a unit test for `state.py`'s
  conversions is a gap (section 7.14, risks).

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| TM-U-01 | Display units | *Manual:* compare the window with the test UI for the same block, speed and temperature | The window shows ft, mph and °F; the test UI shows m, m/s and deg | REQ-INTF-001.2 | *Manual* TC-17 |
| TM-U-02 | Segment properties are shown | *Manual:* select a block | Grade, elevation, length, speed limit, direction, crossing, heater and beacon shown | REQ-FUNC-016.1 to 016.8 | *Manual* TC-24, TC-25 |
| TM-U-03 | Occupancy, switch and light state are shown | *Manual:* occupy a block; set a switch and a light | The window shows each | REQ-FUNC-019, 023 | *Manual* TC-03, TC-06 |
| TM-U-04 | Minimum display size | *Manual:* resize the window to 720 × 450 | Nothing needed is cut off or unreachable | REQ-INTF-011 | *Manual:* add a step to `MANUAL_TESTS.md` (not covered by TC-01 to TC-30) |
| TM-U-05 | The window shows the clock and run state | *Manual:* step, run, hold, 10× | Time of day and PAUSED or RUNNING as in TC-02 | REQ-INTF-013 | *Manual* TC-02 |

### 7.12. Harness process and wire format

- **Item Description:** `track_model/module_process.py`, `track_model/wire.py`, and
  `common/harness/track_edges.py`, `track_model_edges.py`.
  - The process the central harness starts (`track_overflow.py --module track-model`), the
    JSON form of its inputs and outputs, and the edges to the other modules.
- **Version/Build:** as above.
- **Test Approach:** Component tests that decode JSON inputs, step, and encode the outputs,
  and round-trip tests through each edge.

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| TM-P-01 | Inputs decode from JSON | A JSON input | A `TrackModelInputs` equal to the expected | D005 | test_module_process :: test_inputs_decode_from_json |
| TM-P-02 | Command maps and ambient may be left out | A JSON input without them | Decodes with defaults | D005 | test_module_process :: test_command_maps_and_ambient_may_be_left_out |
| TM-P-03 | Malformed inputs are refused | Wrong types, missing keys | Refused with a message | REQ-NFR-004 | test_module_process :: test_malformed_inputs_are_refused |
| TM-P-04 | Outputs encode as plain JSON; a beacon as an object | A full output | Every field is plain JSON; the beacon is an object | D005 | test_module_process :: test_outputs_encode_every_field_as_plain_json; test_a_beacon_encodes_as_an_object |
| TM-P-05 | The process steps the model | A `STEP` message | A reply with the outputs, before the next tick | REQ-INTF-013, REQ-NFR-001 | test_module_process :: test_process_steps_the_model |
| TM-P-06 | The window gets the clock's time | A `STEP` with a time | The window shows that time | REQ-INTF-013 | test_module_process :: test_process_gives_the_window_the_clocks_time |
| TM-P-07 | A bad input refuses the tick and changes nothing | A bad `STEP` | An error reply; the model unchanged | REQ-NFR-004 | test_module_process :: test_a_bad_input_refuses_the_tick_and_changes_nothing |
| TM-P-08 | Every edge carries values unchanged | A value through each of the six edges and back | Equal to the original | D005, D008 | test_harness_edges :: test_round_trip_through_every_edge |
| TM-P-09 | An absent train maps to `None` | A train missing from one tick | `None` at the edge | — | test_harness_edges :: test_absent_train_maps_to_none |

### 7.13. Test UI and test link

- **Item Description:** `test_ui/` (`harness.py`, `block_filter.py`, QML), `test_link/`
  (`codec.py`, `link.py`).
  - The stand-in Track Controller, Train Model and clock, and the local-socket link to the
    module. Removable with no change to `track_model/` (D010).
- **Version/Build:** as above.
- **Test Approach:** Round-trip tests of the codec and link, end-to-end tests with the real
  test UI driving the real module over the link, and unit tests of the filter.

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| TM-X-01 | Inputs and outputs round-trip the codec | Full inputs and outputs; a block edit | Equal after encode and decode | F18 | test_codec :: test_inputs_round_trip; test_outputs_round_trip; test_block_edit_round_trip |
| TM-X-02 | A step round-trips the link | A `step` call over the link | The module's reply | F18 | test_link :: test_step_round_trips |
| TM-X-03 | A UI action is pushed between steps; test-only commands | A window action between steps; a test-only command | Delivered; the test-only command works on the link only | F18 | test_link :: test_ui_action_is_pushed_between_steps; test_test_only_commands |
| TM-X-04 | A rejected input comes back as an error | A bad input over the link | An error reply, not a crash | REQ-NFR-004 | test_link :: test_rejected_input_comes_back_as_an_error |
| TM-X-05 | The real test UI drives the real module | The page opens on Green; a rejection is shown, not raised | Green selected; the rejection appears in the UI | F18 | test_end_to_end :: test_page_starts_on_the_green_line; test_rejection_is_shown_not_raised |
| TM-X-06 | Block filter by line, section and range | A range such as `5-20`; a bad range | Filtered; a bad range is reported, not applied; changing the line resets the section | F18 | test_end_to_end :: test_filter_by_section_and_range; test_bad_range_is_reported_not_applied; test_switching_line_resets_the_section; test_block_filter :: test_parse_block_id; test_short_name_drops_the_line; test_parse_range; test_parse_range_rejects; test_lines_and_sections_in_layout_order; test_filter_blocks |
| TM-X-07 | Short labels keep the full IDs | Rows in the test UI | Short names shown; full IDs sent | F18 | test_end_to_end :: test_short_labels_keep_full_ids |
| TM-X-08 | Connection, either start order | *Manual:* start each window first | Both orders connect | F18 | *Manual* TC-01 |
| TM-X-09 | Clock: step, run, hold, 10× | *Manual:* as TC-02 | As TC-02 | REQ-INTF-013, REQ-NFR-002 | *Manual* TC-02 |
| TM-X-10 | The test UI is removable | *Manual:* close the test UI; run the module alone and with the harness | The module keeps running; nothing in `track_model/` imports the test UI | D010 | *Manual* TC-18 |
| TM-X-11 | Block filter in the window | *Manual:* line, section and range | The pickers and rows follow | F18 | *Manual* TC-26 |
| TM-X-12 | Test-only block edit | *Manual:* change a block's length | The boundary moves | F18 | *Manual* TC-14 |

### 7.14. Integration with the central harness

- **Item Description:** The module as a process under the central harness (D005), with the
  real Track Controller SW, the real Train Model and the Train Controller, through the edges in
  `common/harness/`.
- **Version/Build:** To be set when the other modules' endpoints exist. All cases are
  *Planned* unless noted.
- **Test Approach:**
  - Scripted system runs.
  - The harness's CSV event log is compared with the expected sequence.
  - Rubric iteration 3: dispatch a train from the yard to a station.

| ID | Test case | Inputs | Expected output | Req | Status |
|---|---|---|---|---|---|
| TM-I-01 | Spawned and ready | `track_overflow.py --module track-model` starts the harness, which spawns the module | The module answers with its ready message; one driver only | D005, REQ-INTF-013 | Planned |
| TM-I-02 | Tick protocol | `STEP` at 1x and 10x | Every reply carries the same ID and tick, and arrives before the next tick; no tick dropped | REQ-NFR-001, 002 | Planned |
| TM-I-03 | Track Controller SW commands reach the devices | The wayside commands a switch, a light and a gate on Green | The Track Model applies them; the next tick's read-back returns them | REQ-INTF-018 | Planned |
| TM-I-04 | A switch maps to its point; a light through its switch | The Track Controller names a switch by the block it is listed on | The harness maps it to the Track Model's point block | D005 | Planned |
| TM-I-05 | No heater command is sent | A full run | No heater command crosses from the Track Controller | D026 | Planned |
| TM-I-06 | Real Train Model offsets, Track Info and polarity | A train from the real Train Model driven round Green | Positions agree; Track Info and polarity as in `signals/track-info` | REQ-FUNC-019 | Planned |
| TM-I-07 | Real Track Controller fails safe on a failure | The Track Model fails a block under a train | The wayside reports it occupied and holds its neighbours; the train gets 0 | REQ-FUNC-059 | Planned |
| TM-I-08 | Ticket sales reach the CTC Office | A run with trains on Green | The CTC Office's throughput reflects the sales | REQ-FUNC-014, 017.1 | Planned |
| TM-I-09 | CTC creates and retires trains | The CTC Office releases a train from the yard and returns it | The Track Model's roster follows; no orphan | D022 | Planned |
| TM-I-10 | Red Line runs on the hardware Track Controller | The Pis attached | The Red Line devices follow the hardware's commands | D021, D027 | Planned |

**Risks.**

- **Other modules' endpoints.** Their harness endpoints are not all built, which blocks 7.14.
- **Heater rule.** The rule is not in truth (D026 is open on it), so TM-H-08 and TM-H-09 are
  provisional until a proposal is promoted.
- **Failure effects.** They are the owner's fail-safe reading, not yet agreed with the Track
  Controller owners (TM-F-*).
- **Disembarking.** The Track Model has no source for the number of passengers disembarking
  (TM-K-14).
- **No unit test of `state.py`.** Display conversions (REQ-INTF-001.2) rest on the manual
  script only. A short unit test of `FT_PER_M`, `MPH_PER_MPS` and `c_to_f` would close it.
- **Minimum display size.** REQ-INTF-011 has no step in the manual script (TM-U-04).
- **Static checks fail.** `mypy --strict` (5 errors) and `flake8` (11 lines) fail on this build, which section 4 counts as a fail.

---

## 8. Approvals

| Name | Role | Date |
|------|------|------|
| SeeingEyeTree | Track Model owner, test manager | |
| | Course instructor | |
