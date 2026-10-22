# Test Plan

**Document Version:** 1.0
**Date:** 2026-10-21
**Prepared By:** Harry Tye
**Project Name:** Track Overflow — Track Controller (Software)

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
   * [7.1 SwTrackController (module boundary)](#71-swtrackcontroller-module-boundary)
   * [7.2 TrackController (wayside)](#72-trackcontroller-wayside)
   * [7.3 PLC engine (plc, Program)](#73-plc-engine-plc-program)
   * [7.4 Vital code (vital)](#74-vital-code-vital)
   * [7.5 Track layout (layout)](#75-track-layout-layout)
   * [7.6 Wire format (wire)](#76-wire-format-wire)
   * [7.7 CTC edge mapping (ctc_edges)](#77-ctc-edge-mapping-ctc_edges)
   * [7.8 TrackControllerState (window)](#78-trackcontrollerstate-window)
   * [7.9 StimulusServer (test link)](#79-stimulusserver-test-link)
   * [7.10 StandInWorld and test UI](#710-standinworld-and-test-ui)
   * [7.11 Integration with the central harness](#711-integration-with-the-central-harness)
8. [Approvals](#8-approvals)

---

## 1. Introduction

### 1.1. Purpose
This plan sets out how the software Track Controller is tested. It identifies:

- the items, meaning the classes of `track_ctrl` and `track_ctrl_test`;
- the features and requirements to be tested, and how;
- the test cases with their inputs and expected results;
- who designs, runs and reviews them;
- the risks that limit the plan.

The plan is the evidence that the module meets its SRS requirements (REQ-FUNC-049 to
REQ-FUNC-059 and the interface requirements) before it is integrated with the rest of the
system.

### 1.2. Scope
**System boundary.** The module is `TrackCtrlSW/`:

- `track_ctrl`, the module and its window;
- `track_ctrl_test`, the test UI and its stand-in world;
- `common/harness/ctc_edges`, the CTC-to-Track-Controller mapping.

It runs every wayside of the Green Line (D021). Everything it exchanges crosses
`SwTrackController.step(dt, inputs)` and is keyed by `BlockKey(line, block_id)`.

**Test levels.**

| Level | What | How |
|---|---|---|
| Unit | One class or function: PLC compiler, vital code, layout parser, wire codecs, edge mapping | Automated, `unittest`, headless |
| Component | The whole module through its boundary: `step`, `snapshot`, `load_program`, `reset` | Automated, `unittest`, with `tests/rig.py` wiring the module to `StandInWorld` |
| Integration (module + test UI) | The window and the test UI over the named pipe | Automated (`test_link.py`, offscreen Qt), plus manual runs of both windows |
| Integration (system) | The module under the central harness with the CTC Office and the Track Model | Planned: needs the D005 harness endpoint |
| Acceptance | Rubric 6.0 to 6.9 shown in the iteration demonstrations | Manual, scripted below |

**Constraints and assumptions.**

- Tests run on Windows 11 with Python 3.12 and PySide6 6.8 (`TrackCtrlSW/.venv`).
- The dt is fixed (D006) at 0.1 s in the tests.
- Speeds are whole m/s and authorities are block counts (D013).
- The automated tests need no display: Qt runs with `QT_QPA_PLATFORM=offscreen`.
- The Track Model reports failures as occupancy, so `FAIL_n` is always 0.
- The CTC Office owns the posted-limit clamp and zero speed for zero authority. The module
  is not tested for them.

### 1.3. Definitions, Acronyms, & Abbreviations
| Term | Definition |
|------|------------|
| Wayside | One Track Controller governing a contiguous territory of blocks; `TrackController` in code. Green has six (GTC-01 to GTC-06). |
| PLC | Programmable logic controller. Here: the Boolean program a wayside runs every scan. |
| Vital code | Generated PLC code attached after every user program. It can only make an output more restrictive, and only it writes the `OUT_` outputs. |
| OS | The wayside's input/output wrapper: decodes inputs to PLC bits and encodes `OUT_` bits to commands. It decides nothing. |
| Scan | One evaluation of the user program and the vital code, once per tick. |
| Tick | One step of the shared clock (D017), carrying `dt`. |
| Suggestion | The CTC Office's speed (m/s) and authority (blocks) for one block. |
| Track circuit | The speed and authority sent to the train in a block, through the Track Model. |
| Read-back | The Track Model's report of the actual switch, signal and crossing states. |
| Ready | Every wayside on the line has a committed program. A line that is not ready transmits nothing. |
| Maintenance | Inferred while the CTC Office has a switch command in effect. There is no flag. |
| Rig | `tests/rig.py`: the module wired to `StandInWorld`, ticked without Qt. |
| SUT | System under test. |

### 1.4. References
- SRS — `documents/srs-filled.md`, REQ-FUNC-012, REQ-FUNC-049 to 059, REQ-INTF-001.5, 009, 011
  to 013, 017 to 020, REQ-NFR-002 to 004.
- Rubric map — `documents/rubrics/rubric-to-requirements-map.md`, Track Controller 6.0 to 6.9.
- SDD contribution — `documents/sdd/track_ctrl_sw.md`: use cases UC-01 to UC-18, class
  and sequence diagrams.
- Decisions on `truth`: D005 (harness and process protocol), D006 (fixed dt), D013
  (authority in blocks), D017 (shared clock), D021 (Green to SW, Red to HW).
- Module README — `TrackCtrlSW/README.md`, for how to run the window, the test UI and the tests.
- Test case template — `documents/test-case-template.xlsx`.
- Hardware variant — `TrackCtrlHw/`, used for the PLC language equivalence tests.

### 1.5. Overview
- Section 2 lists the features under test against their requirements, and section 3 the
  features excluded.
- Section 4 gives the pass, fail, suspension and resumption criteria.
- Section 5 lists the deliverables, and section 6 who does what.
- Section 7 is the body of the plan. For each class or group of classes it gives the item,
  the build, the approach, and a table of test cases with inputs and expected results. Each
  automated case names the test that implements it (`file :: test`).

---

## 2. Features to Be Tested

| # | Feature | Requirements | Use cases | Test items |
|---|---|---|---|---|
| F1 | Receive speed and authority suggestions per block | REQ-FUNC-049, REQ-INTF-019 | UC-10 | 7.1, 7.7, 7.10 |
| F2 | Load a PLC program file | REQ-FUNC-050 | UC-03, UC-06 | 7.8 |
| F3 | Boolean-only PLC language, identical to HW | REQ-FUNC-051, REQ-INTF-009 | UC-04, UC-05 | 7.3 |
| F4 | Switches set by PLC execution | REQ-FUNC-052 | UC-13 | 7.2, 7.4 |
| F5 | Signal aspects set by PLC execution | REQ-FUNC-053 | UC-14 | 7.2, 7.4 |
| F6 | Train presence received from the Track Model | REQ-FUNC-054, REQ-INTF-018 | UC-12 | 7.1, 7.10 |
| F7 | Occupancy, read-back and readiness reported to the CTC | REQ-FUNC-055, REQ-INTF-020 | UC-17 | 7.1 |
| F8 | Railway crossings activated | REQ-FUNC-056 | UC-15 | 7.4 |
| F9 | Maintenance mode known; CTC switch commands obeyed; hand-set switch | REQ-FUNC-057, REQ-FUNC-012 | UC-08, UC-11 | 7.1, 7.4, 7.8 |
| F10 | Safety-critical architecture: vital code, run before commit, nothing transmitted when not ready | REQ-FUNC-058, REQ-FUNC-058.1 | UC-05, UC-06, UC-16, UC-18 | 7.2, 7.4, 7.8 |
| F11 | Failures protected as occupancy | REQ-FUNC-059 | UC-12 | 7.1 |
| F12 | Track layout loaded from JSON; wayside count fixed by the track | REQ-INTF-012 | UC-01 | 7.5, 7.8 |
| F13 | Invalid input rejected without changing state | REQ-NFR-003, REQ-NFR-004 | UC-01, UC-09 | 7.1, 7.5, 7.6, 7.9 |
| F14 | Stepped by one shared clock with a fixed dt | REQ-INTF-013, REQ-NFR-002 | UC-09 | 7.1, 7.9 |
| F15 | Software GUI: select a wayside, monitor in imperial units | REQ-INTF-001.5, REQ-INTF-011 | UC-02, UC-07 | 7.8 |
| F16 | Separate test UI for inputs and outputs | Rubric iteration 2, item 1.4 | — | 7.9, 7.10 |

---

## 3. Features Not to Be Tested

- **Posted-limit clamp and zero speed for zero authority.** These belong to the CTC Office.
  The wayside passes the suggestion unchanged, halves it or sends 0, and only that is tested.
- **Distinguishing failure types (broken rail, track circuit, power).** The Track Model
  reports every failure as an occupied block, and `FAIL_n` is always 0, so the module cannot
  tell them apart. Only protection as occupancy is tested (F11).
- **The Red Line.** The hardware variant runs it (D021). The layout tests read
  `red_line.json` only to check that the parser is general.
- **The hardware variant's internals.** They are tested by its owner. Only the shared PLC
  language is tested here (7.3).
- **Moving block overlay.** Out of scope per the SRS (3.2.7).
- **Pixel layout and visual style of the QML window.** These are checked by review against
  `documents/UI_Style_Guide.md`, not by test cases.
- **Real-time performance at 10x.** This needs the central harness, and is deferred to
  system integration (7.11).

---

## 4. Item Pass/Fail Criteria

| Criteria | Description |
|----------|--------------|
| Pass | Every automated test of the item passes (`unittest` reports `OK`), `mypy` reports no errors, and every manual case of the item gives its expected result. |
| Fail | Any automated test fails or errors, or any manual case gives a result other than the expected one. |
| Critical failure | Any failure in a safety case. These are marked **S** in section 7. An example is the vital code granting authority to a closed or occupied block, moving a switch under a train, or a not-ready line transmitting a command. A critical failure fails the whole module, whatever else passes. |
| Suspension | Testing stops when the build does not start, the suite cannot be imported, or a critical failure is found. Other cases would only hide its cause. |
| Resumption | After the fix, the full automated suite is re-run, not only the failed case. The affected manual cases are then repeated. |
| Not run | A planned case whose dependency is missing, such as the harness endpoint (7.11). It is recorded as *Planned*, not as a pass. |

Results are recorded in `documents/test-case-template.xlsx`, one row per case: Test Case,
Inputs, Expected Output, Pass/Fail, Failure Description, Tester, Date Tested.

---

## 5. Test Deliverables

- This test plan.
- **Automated suites** in `TrackCtrlSW/tests/`:
  - `test_boundary.py`, `test_world.py` and `test_hw_language.py`;
  - `test_layout.py` and `test_ctc_edge.py`;
  - `test_stimulus.py` and `test_link.py`;
  - the shared rig, `rig.py`.
- **Test data:**
  - the track layouts `TrackModel/green_line.json` and `red_line.json`;
  - the small layouts and malformed files built inside `test_layout.py` and `test_stimulus.py`;
  - the starter and HW example PLC programs.
- **Test tools:**
  - the test UI (`test_main.py`, `track_ctrl_test`), with its stand-in CTC Office, Track
    Model and clock;
  - the stimulus pipe (`StimulusServer`).
- **The completed test case sheet** (`test-case-template.xlsx`), including the manual
  cases.
- **The suite's console log** for each recorded run (`unittest -v` and `mypy`).
- **Defect notes** for every failure, linked from the sheet's Failure Description.

---

## 6. Responsibilities

| Role | Responsibility | Owner |
|------|-----------------|-------|
| Test manager | Owns this plan; keeps sections 2 and 7 in step with the SRS and the SDD | Harry Tye |
| Test designer | Writes the automated cases and the manual scripts | Harry Tye |
| Test executor | Runs the suite before every push and the manual cases before each demonstration; records results | Harry Tye |
| Language equivalence | Agrees the shared PLC names and examples with the HW variant (7.3) | Harry Tye, Braden |
| Interface reviewer (CTC) | Confirms the `TrainSuggestion` mapping and the readiness rule (7.7, 7.1) | CTC Office owner |
| Interface reviewer (Track Model) | Confirms the occupancy, read-back and command formats | Track Model owner |
| Integration | Runs the module under the central harness (7.11) | Harry Tye, with the harness owner |
| Reviewer | Reviews the plan and the results | Course instructor and team |

---

## 7. Test Items

**How to run.**

The automated suite, from `TrackCtrlSW/`:

```bash
QT_QPA_PLATFORM=offscreen .venv/Scripts/python -m unittest discover -s tests -v
```

```bash
.venv/Scripts/python -m mypy main.py test_main.py track_ctrl/ track_ctrl_test/
```

For a manual run, start the module window and then the test UI:

```bash
.venv/Scripts/python main.py
```

```bash
.venv/Scripts/python test_main.py
```

**Notation.**

- In the tables, `GTC-01` is the first Green wayside: blocks 1 to 25, switch 12 and
  crossing 19. The rig steps it with `dt = 0.1 s`.
- **S** marks a safety case (section 4).
- *Manual* marks a case run by hand in the windows.

**Build for all items.**

- Branch `Track-Ctrl-SW`, commit `f6900f5`.
- Python 3.12.10 and PySide6 6.8.3.
- Last full run: 2026-10-21. 191 tests, `OK`. `mypy` clean.

### 7.1. SwTrackController (module boundary)

- **Item Description:** `track_ctrl/module.py`, `track_ctrl/interface.py`, `track_ctrl/errors.py`.
  - The whole module behind the `TrackController` Protocol: `load_track`, `step`,
    `snapshot`, `load_program` and `reset`.
  - Readiness per line, and one `CtcReport` per wayside.
- **Version/Build:** as above.
- **Test Approach:** Black-box component tests through the boundary types only.
  - Each case builds `TrackControllerInputs`, calls `step`, and compares the
    `TrackControllerOutputs` with the expected values.
  - The rejection cases also compare `snapshot()` before and after, to prove that nothing
    changed.

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| SW-M-01 | Outputs are keyed by line and block | One tick of Green with suggestions | Every key in every output map is a `BlockKey` with `line == "Green"` | REQ-INTF-009 | test_boundary :: test_every_output_is_keyed_by_line_and_block |
| SW-M-02 | A suggestion reaches its block's circuit | `Suggestion(9, 2)` on Green block 8 only | `track_circuits` holds only `Green:8`, with speed ≤ 9 and authority ≤ 2 | REQ-FUNC-049 | test_boundary :: test_suggestion_per_block_reaches_that_blocks_circuit |
| SW-M-03 | No suggestion, no circuit | No suggestion on a block | That block is absent from `track_circuits` | REQ-FUNC-049 | test_boundary :: test_block_without_suggestion_sends_nothing |
| SW-M-04 **S** | A failure is just an occupied block | Block reported occupied with no train | Protected exactly like an occupied block; no failure field crosses the boundary | REQ-FUNC-059 | test_boundary :: test_a_failure_is_just_an_occupied_block; test_no_failure_or_heater_field_crosses_the_boundary |
| SW-M-05 | Report carries the read-back | The Track Model reports a switch, an aspect and a crossing state | Each wayside's `CtcReport.blocks` holds those values for its blocks | REQ-FUNC-055, REQ-INTF-020 | test_boundary :: test_report_carries_the_track_models_readback |
| SW-M-06 | One report per wayside | A Green tick | Six `CtcReport`s, in load order | REQ-FUNC-055 | test_boundary :: test_one_report_per_wayside_in_load_order |
| SW-M-07 | A CTC switch command is obeyed and means maintenance | `switch_commands = {Green:12: reverse}` | The switch is commanded reverse; `snapshot().maintenance_mode` is true | REQ-FUNC-057, REQ-FUNC-012 | test_boundary :: test_a_ctc_switch_command_is_obeyed_and_is_maintenance |
| SW-M-08 | Withdrawing the command ends maintenance | Command present, then absent | `maintenance_mode` becomes false | REQ-FUNC-057 | test_boundary :: test_withdrawing_the_command_ends_maintenance |
| SW-M-09 | A command for an ungoverned switch is not maintenance | A Green-only module; `switch_commands = {Red:12: reverse}` | `maintenance_mode` stays false | REQ-FUNC-057 | test_boundary :: test_a_command_for_a_switch_it_does_not_govern_is_not_maintenance |
| SW-M-10 | There is no maintenance flag | The `CtcInputs` fields | No maintenance field exists | REQ-FUNC-057 | test_boundary :: test_there_is_no_maintenance_flag_on_the_boundary |
| SW-M-11 **S** | A closed block is held at zero | A closed block with a suggestion | Its circuit is `(0, 0)` | REQ-FUNC-058.1 | test_boundary :: test_closed_block_holds_its_circuit_at_zero |
| SW-M-12 | Unknown blocks are ignored | Inputs for a block no wayside governs | No error; no output for it | REQ-NFR-004 | test_boundary :: test_unknown_blocks_are_ignored |
| SW-M-13 | Snapshot follows the last tick | Two ticks with different time | The snapshot shows the second tick's time and values | REQ-INTF-013 | test_boundary :: test_snapshot_follows_the_last_tick |
| SW-M-14 | A new module is not ready | `SwTrackController()` with no track | `ready` false, reason "no track is loaded"; no track circuits even with suggestions | REQ-FUNC-058 | test_boundary :: test_a_new_module_is_not_ready_and_says_why |
| SW-M-15 **S** | One missing program stalls the line | Five of six waysides programmed | Every Green wayside reports not ready; no command for the line | REQ-FUNC-058 | test_boundary :: test_one_missing_program_stalls_every_wayside; test_a_loaded_line_without_programs_stalls |
| SW-M-16 | The last program starts the line | The sixth program committed | Every report is ready; commands flow | REQ-FUNC-055 | test_boundary :: test_the_last_program_starts_the_module; test_loading_the_last_program_by_hand_makes_it_ready |
| SW-M-17 | A new line or a reset stalls it again | A ready module, then `load_track` or `reset` | Not ready again | REQ-FUNC-058 | test_boundary :: test_a_new_line_or_a_reset_stalls_a_ready_module_again |
| SW-M-18 | Readiness is per wayside on the wire | A partly programmed line | Each report carries its own `ready` and `reason`; `outputs.ready` is true only when all are | REQ-FUNC-055 | test_boundary :: test_each_wayside_reports_its_own_readiness; test_the_whole_is_ready_only_when_every_wayside_is; test_readiness_crosses_the_wire_per_wayside |
| SW-M-19 | A bad dt is rejected unchanged | `dt` of 0, -0.1, NaN or inf | `InvalidInputError`; snapshot unchanged | REQ-NFR-004, REQ-INTF-013 | test_boundary :: test_bad_dt |
| SW-M-20 | A bad time is rejected unchanged | `time_s` of NaN or -1 | `InvalidInputError`; snapshot unchanged | REQ-NFR-004 | test_boundary :: test_bad_time |
| SW-M-21 | A bad suggestion is rejected unchanged | `Suggestion(-1, 1)`, `(1, -1)`, `(1.5, 1)`, `(1, True)` | `InvalidInputError`; snapshot unchanged | REQ-NFR-003, REQ-NFR-004 | test_boundary :: test_bad_suggestions |
| SW-M-22 | A bad position or aspect is rejected | Switch command `"up"`; aspect `"blue"` | `InvalidInputError`; snapshot unchanged | REQ-NFR-004 | test_boundary :: test_bad_position_and_aspect |
| SW-M-23 | `load_program` checks its target and program | An unknown wayside; a program with errors; a good program | `UnknownIdError`; `InvalidProgramError` with nothing changed; `ProgramInfo` with iteration 1 | REQ-FUNC-050 | test_boundary :: test_unknown_wayside; test_program_with_errors_is_refused; test_good_program_is_committed |
| SW-M-24 | Errors share one base | Every error class | Subclass of `TrackControllerError` | — | test_boundary :: test_every_error_shares_one_base |

### 7.2. TrackController (wayside)

- **Item Description:** `track_ctrl/controller.py`.
  - One wayside: its `ControllerInputs` and the OS functions (`build_scan_inputs` to
    decode, `encode_outputs` to encode).
  - Its programs: `check_program`, `run_program` for the sandbox, `commit` and `scan`.
  - Its iteration history (last five) and hand-set switches.
- **Version/Build:** as above.
- **Test Approach:** Rig tests (`tests/rig.py`) that change one world input on GTC-01, tick
  once, and check the wayside's outputs and the names of the vital rules that fired.
  Commit-gate cases call `check_program` and `commit` directly.

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| SW-W-01 | Occupancy reaches the input card | Block 3 occupied, then cleared | `inputs.occupancy["3"]` true and `trains["3"] == "TEST"`; then false, with no train | REQ-FUNC-054 | test_world :: test_occupancy_reaches_the_input_card |
| SW-W-02 | Occupancy on the signal block turns it red | Block 12 occupied | Signal at 12 commanded RED | REQ-FUNC-053 | test_world :: test_occupancy_on_the_signal_block_turns_it_red |
| SW-W-03 | Occupancy ahead gives yellow | Block 14 occupied | Signal at 12 commanded YELLOW by the program | REQ-FUNC-053 | test_world :: test_occupancy_ahead_makes_the_program_show_yellow |
| SW-W-04 **S** | A train holds the blocks beside it | Suggestions `(12, 4)` everywhere; block 6 occupied | Blocks 5 and 7 get `(0, 0)`; block 3 keeps `(12, 4)` | REQ-FUNC-058.1 | test_world :: test_a_train_holds_the_blocks_beside_it |
| SW-W-05 | Signals and crossings come back as read-back | One tick | The world's read-back equals the commands; the next report carries it | REQ-FUNC-055 | test_world :: test_signals_and_crossings_come_back_as_readback |
| SW-W-06 | Closing a block zeroes only that block | Block 7 closed, then reopened; suggestions `(12, 4)` | Block 7 `(0, 0)` while closed, block 9 still `(12, 4)`; block 7 back to `(12, 4)` when reopened | REQ-FUNC-058.1 | test_world :: test_closing_a_block_zeroes_that_blocks_circuit_only |
| SW-W-07 | Suggestions are per block | Different suggestions on two blocks | Each circuit carries its own | REQ-FUNC-049 | test_world :: test_suggestions_are_per_block; test_one_part_of_a_suggestion_can_change_alone |
| SW-W-08 | A suggestion passes unchanged | `Suggestion(15, 0)` on block 3 (over the limit, zero authority) | Circuit `(15, 0)`: the wayside applies no numeric rule; that is the CTC Office's | REQ-FUNC-049 | test_world :: test_the_wayside_passes_a_suggestion_unchanged |
| SW-W-09 | A program that withholds a block sends it nothing | A bare program that never grants `AUTH_n` | Block 5's circuit `(0, 0)` | REQ-FUNC-058 | test_world :: test_a_program_that_withholds_a_block_sends_it_nothing |
| SW-W-10 **S** | A wayside with no program transmits nothing | Default Green module with no programs; `Suggestion(9, 2)` on block 3 | `track_circuits`, `switch_commands`, `signal_commands` and `crossing_commands` all empty | REQ-FUNC-058 | test_world :: test_a_wayside_with_no_program_transmits_nothing |
| SW-W-11 | Every program has the vital code attached | Commit any program | The scan runs the vital code after the program; the outputs are the `OUT_` bits | REQ-FUNC-058 | test_world :: test_every_program_gets_the_vital_code_attached |
| SW-W-12 | A warning blocks commit like an error | A program that reads an undeclared name | `commit` refused; `blocks_commit` true | REQ-FUNC-058 | test_stimulus :: test_a_warning_blocks_commit_like_an_error; test_the_controller_itself_refuses_a_program_with_warnings |
| SW-W-13 | An unassigned output blocks commit | A program that declares `SW_12` but never assigns it | One diagnostic naming the output; commit refused | REQ-FUNC-052 | test_stimulus :: test_an_unassigned_output_blocks_commit; test_many_unassigned_outputs_are_one_message |
| SW-W-14 | A program for another wayside is refused | GTC-02's program committed to GTC-01 | Diagnostics name the foreign I/O; commit refused | REQ-FUNC-050 | test_stimulus :: test_a_program_for_another_wayside_is_flagged_against_this_one; test_a_program_that_fits_another_controller_is_refused_here |
| SW-W-15 | Fixing the warning lets it commit | The same program with the warning fixed | Commit succeeds; iteration + 1 | REQ-FUNC-050 | test_stimulus :: test_fixing_the_warning_lets_it_commit |
| SW-W-16 | Starter programs are clean | Every wayside's starter program | No diagnostics | REQ-FUNC-051 | test_stimulus :: test_every_starter_program_has_no_diagnostics |

### 7.3. PLC engine (plc, Program)

- **Item Description:** `track_ctrl/plc.py`: `compile_program`, `Program`, `Diagnostic`,
  `blocks_commit` and `has_errors`.
  - Boolean only: `VAR_IN`, `VAR_OUT`, `:=`, `NOT`, `AND`, `XOR`, `OR`, `0`, `1` and
    parentheses.
- **Version/Build:** as above. The HW comparator is `TrackCtrlHw/track_ctrl_hw` on the same
  branch.
- **Test Approach:**
  - Differential testing against the hardware variant's compiler: the same random and
    malformed programs must compile, fail and evaluate identically in both.
  - Example-based cases for declarations, ranges and diagnostics.

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| SW-P-01 | Random programs mean the same in SW and HW | 600 seeded random Boolean programs and their input vectors | Identical outputs from both compilers for every vector | REQ-FUNC-051, REQ-INTF-009 | test_hw_language :: test_random_programs_mean_the_same_thing |
| SW-P-02 | Malformed statements are errors in both | 600 seeded random token soups as the right-hand side of `Z :=` | Both compilers accept or reject each one alike, with the same diagnostics | REQ-FUNC-051, REQ-NFR-003 | test_hw_language :: test_malformed_statements_are_errors_in_both |
| SW-P-03 | Declarations and ranges expand the same | `VAR_IN OCC_1..5`, `OCC_A .. OCC_C` | The same name lists in both | REQ-FUNC-051 | test_hw_language :: test_declarations_and_ranges_expand_the_same |
| SW-P-04 | Odd but legal programs | Comments, blank lines, nested `NOT`, constants | Compiles and evaluates the same in both | REQ-FUNC-051 | test_hw_language :: test_odd_but_legal_programs |
| SW-P-05 | HW's wayside program runs here | `TrackCtrlHw` wayside 1 example program | No diagnostics; the same outputs as HW; runs through the attached vital code | REQ-INTF-009 | test_hw_language :: test_the_hw_wayside_1_program_has_no_diagnostics_here; test_the_hw_program_computes_the_same_outputs_in_both; test_the_hw_program_runs_through_the_attached_vital_code |
| SW-P-06 | HW's error and warning examples are flagged | HW's bad example programs | The same diagnostics here | REQ-INTF-009 | test_hw_language :: test_the_hw_error_and_warning_examples_are_still_flagged |
| SW-P-07 | I/O names are HW's | GTC-01 `input_names` and `output_names` | `OCC_n`, `CLOSED_n`, `FAIL_n`, `SWREV_s`, `MAINT`; `AUTH_n`, `SW_s`, `SIG_s_R/_Y/_G/_SG`, `XING_c` | REQ-INTF-009 | test_hw_language :: test_inputs_and_outputs_are_the_hw_names |
| SW-P-08 | An undeclared read is caught at compile time | `X := UNKNOWN AND 1` | A warning on that line; commit blocked | REQ-FUNC-058 | test_stimulus :: test_reading_an_undeclared_name_is_caught_at_compile_time |
| SW-P-09 | Vital-only names cannot be declared | A program declaring `CTCCMD_12` or `HAND_12` | Refused against the wayside's I/O | REQ-FUNC-058 | *Manual* (Program tab, Run) |

### 7.4. Vital code (vital)

- **Item Description:** `track_ctrl/vital.py`: `vital_source` generates each wayside's
  vital PLC code, `idle_outputs` gives a wayside that runs nothing, and `report_overrides`
  lists what the vital code changed, for display.
- **Version/Build:** as above.
- **Test Approach:** Rig tests on GTC-01 that pair a permissive program with an unsafe world
  state, and check that the final `OUT_` result is the restrictive one and that the named
  rule appears in the overrides. Every case here is a safety case.

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| SW-V-01 **S** | A crossing arms when a train is beside it | Crossing 19 inactive; then block 18 (on its approach) occupied | Crossing 19 commanded active (`OUT_XING_19 = 1`) | REQ-FUNC-056 | test_world :: test_the_crossing_arms_when_a_train_is_beside_it |
| SW-V-02 **S** | A switch that will not follow stops its block | The program throws switch 12 reverse; the switch machine is stuck | Block 12's speed 0; rule `switch_moving`. If it follows, the switch is reverse and nothing is held | REQ-FUNC-058.1 | test_world :: test_a_switch_that_will_not_follow_stops_its_block; test_a_switch_that_follows_is_not_held |
| SW-V-03 **S** | A switch under a train does not move | Block 12 occupied; maintenance; CTC commands reverse | `switches["12"]` stays normal; rule `switch_locked_under_train` | REQ-FUNC-058.1 | test_world :: test_a_switch_under_a_train_does_not_move |
| SW-V-04 | Yellow halves its block's speed | Block 14 occupied (yellow at 12); `Suggestion(11, 3)` on 12 | Aspect YELLOW; circuit `(5, 3)`; rule `aspect_speed_cap` | REQ-FUNC-053 | test_world :: test_yellow_halves_the_speed_of_its_block |
| SW-V-05 | CTC switch command obeyed only in maintenance | A CTC command with and without maintenance in effect | Followed while a command is in effect | REQ-FUNC-012 | test_world :: test_a_ctc_switch_command_is_obeyed_only_in_maintenance |
| SW-V-06 | The CTC command beats a hand-set switch | Hand-set normal; CTC reverse | `OUT_SW_12` reverse | REQ-FUNC-012 | test_world :: test_the_ctc_command_beats_a_hand_set_switch |
| SW-V-07 | Hand-set is obeyed without a CTC command | Maintenance; hand-set reverse; no command for 12 | `OUT_SW_12` reverse | REQ-FUNC-057 | test_world :: test_a_hand_set_switch_is_obeyed_when_the_ctc_has_not_commanded |
| SW-V-08 | Ending maintenance releases everything | Maintenance ends | Hand-set and CTC positions dropped; the program's `SW_12` again | REQ-FUNC-057 | test_world :: test_ending_maintenance_releases_commands_and_hand_settings |
| SW-V-09 | Maintenance is system-wide and does not hold traffic | A command on one wayside's switch | Every wayside shows maintenance; speeds and authorities still pass | REQ-FUNC-057 | test_world :: test_maintenance_mode_is_system_wide; test_maintenance_does_not_hold_speed_or_authority |
| SW-V-10 **S** | Not exactly one aspect means red | A program that lights `_G` and `_Y` together, or none | `OUT_SIG_12_R = 1`, the others 0 | REQ-FUNC-053 | *Manual* (Program tab, Run: sandbox shows the override) |
| SW-V-11 | Vital overrides reach the window | Any override in a scan | Listed in the window with its rule and message | REQ-FUNC-058 | test_link :: test_vital_overrides_reach_the_ui |

### 7.5. Track layout (layout)

- **Item Description:** `track_ctrl/layout.py`: `load_layout_file`, `parse_layout`,
  `build_line`, `WAYSIDE_COUNTS`, and the classes `LineLayout`, `ControllerConfig`,
  `Block`, `Switch`, `WaysideSignal` and `Crossing`. Also `track_ctrl/display.py` for the
  unit conversions.
- **Version/Build:** as above, with `TrackModel/green_line.json` and `red_line.json`.
- **Test Approach:** Parse the real course files and compare the counts with the files.
  Check the partition invariants. Feed malformed layouts, one fault each, and expect
  `LayoutError` with a reason.

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| SW-L-01 | Green has the blocks, switches and crossings in the file | `green_line.json` | Counts equal the file's; blocks in number order with their real limits | REQ-INTF-012 | test_layout :: test_green_has_the_blocks_switches_and_crossings_in_the_file; test_blocks_are_in_block_number_order_with_real_limits |
| SW-L-02 | Switch strings read normal first, then reverse | Green switch entries | `normal_end` and `reverse_end` as in the file | REQ-INTF-012 | test_layout :: test_switch_strings_are_read_normal_first_then_reverse |
| SW-L-03 | Every block belongs to exactly one wayside | Green divided into 6 | The territories are disjoint, contiguous, nearly equal and cover every block | REQ-FUNC-058 | test_layout :: test_every_block_belongs_to_exactly_one_controller; test_territories_are_contiguous_and_nearly_equal |
| SW-L-04 | A switch belongs to the wayside that owns its block | Green | Each switch is in exactly one `ControllerConfig`, with its block | REQ-FUNC-052 | test_layout :: test_a_switch_belongs_to_the_wayside_that_owns_its_block |
| SW-L-05 | A signal at every switch and nowhere else | Green | One `WaysideSignal` per switch block | REQ-FUNC-053 | test_layout :: test_a_signal_stands_at_every_switch_and_nowhere_else |
| SW-L-06 | A crossing is armed by its block and neighbours | Green crossing 19 | `approach_block_ids` contains 18, 19 and 20 | REQ-FUNC-056 | test_layout :: test_a_crossing_is_armed_by_its_own_block_and_its_neighbours |
| SW-L-07 | The wayside count is what the line allows | `build_line(Green, n)` with n = 0, 1, 151, -3, `True`, 2.5 | `LayoutError` for each; the default system builds Green into 6 (`WAYSIDE_COUNTS`) | REQ-INTF-012 | test_layout :: test_the_wayside_count_is_limited_to_what_the_line_allows |
| SW-L-08 | PLC names use block numbers | GTC-01's first switch, signal and crossing | `SW_12`, `SIG_12_R`, `XING_19` | REQ-INTF-009 | test_layout :: test_plc_names_use_block_numbers |
| SW-L-09 | Malformed layouts are refused with a reason | Wrong shape; a bad block field; a duplicate block; a bad switch string; unreadable files | `LayoutError` naming the fault | REQ-NFR-003 | test_layout :: test_shape_errors; test_block_errors; test_a_duplicate_block_is_refused; test_switch_string_errors; test_unreadable_files |
| SW-L-10 | A wayside database is not a track layout | A single-wayside JSON file | Refused with that reason | REQ-NFR-003 | test_layout :: test_a_wayside_database_is_not_a_track_layout |
| SW-L-11 | Unsupported line refused | `blue_line.json` | Refused with the reason | REQ-NFR-003 | test_layout :: test_blue_is_refused_with_the_reason |
| SW-L-12 | Units | mph and m/s values | The factor from `units.md`; a typed mph speed becomes whole m/s rounded down, never faster | REQ-INTF-001.5 | test_layout :: test_the_factor_is_the_one_in_units_md; test_a_typed_speed_becomes_whole_mps_rounded_down; test_rounding_down_can_only_make_a_typed_speed_slower |

### 7.6. Wire format (wire)

- **Item Description:** `track_ctrl/wire.py`: the JSON codecs for the boundary types
  (`inputs_to_wire` and `inputs_from_wire`, `outputs_to_wire` and `outputs_from_wire`,
  `snapshot_to_wire`).
- **Version/Build:** as above.
- **Test Approach:** Round-trip tests (encode, `json.dumps`, `json.loads`, decode, compare)
  and strict-decoding tests with one fault each.

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| SW-J-01 | Inputs round-trip | A full `TrackControllerInputs` | Equal after encode, JSON and decode | REQ-INTF-009 | test_boundary :: test_inputs_round_trip_through_json |
| SW-J-02 | Outputs round-trip | A full `TrackControllerOutputs` with reports | Equal after the round trip | REQ-INTF-009 | test_boundary :: test_outputs_round_trip_through_json |
| SW-J-03 | Snapshot is JSON-ready | `snapshot()` | `json.dumps` succeeds | — | test_boundary :: test_snapshot_is_json_ready |
| SW-J-04 | Decoding is strict | A missing field, a wrong type, an unknown key, a bad enum | `WireFormatError` | REQ-NFR-003 | test_boundary :: test_decoding_is_strict; test_outputs_decoding_is_strict |

### 7.7. CTC edge mapping (ctc_edges)

- **Item Description:** `common/harness/ctc_edges.py`: `ctc_to_track_controller` maps the
  CTC Office's `TrainSuggestion`s, closures and switch commands to `CtcInputs`.
- **Version/Build:** as above.
- **Test Approach:** Unit tests on the mapping, plus one end-to-end case through the module.

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| SW-C-01 | A train suggestion becomes its block's suggestion | `TrainSuggestion("T1", "Green", "63", 18, 2)` | `suggestions[Green:63] == Suggestion(18, 2)` | REQ-FUNC-049, REQ-INTF-019 | test_ctc_edge :: test_a_train_suggestion_becomes_its_blocks_suggestion |
| SW-C-02 | The train ID stops at the edge | `T1` on Green 63 and `T2` on Red 63 | Two block suggestions (one per line); no train ID in `CtcInputs` | REQ-INTF-019 | test_ctc_edge :: test_the_train_id_stops_at_the_edge |
| SW-C-03 **S** | Two suggestions for one block take the more restrictive | `(18, 1)` and `(9, 4)` on Green block 5 | `Suggestion(9, 1)`: the lower speed and the lower authority, taken separately | REQ-FUNC-058.1 | test_ctc_edge :: test_two_suggestions_for_one_block_take_the_more_restrictive |
| SW-C-04 | Closures and switch commands carry over | Closed blocks and `SwitchCommand`s | The same sets in `CtcInputs` | REQ-FUNC-012 | test_ctc_edge :: test_closed_blocks_and_switch_commands_carry_over |
| SW-C-05 | Nothing sent maps to nothing | Empty CTC output | Empty `CtcInputs` | — | test_ctc_edge :: test_nothing_sent_maps_to_nothing |
| SW-C-06 | The mapped suggestion reaches the circuit | The mapped inputs stepped through a ready module | The block's circuit carries `(18, 2)` | REQ-FUNC-049 | test_ctc_edge :: test_the_mapped_suggestion_reaches_the_blocks_circuit |

### 7.8. TrackControllerState (window)

- **Item Description:** `track_ctrl/state.py`, `track_ctrl/stimulus.py` and
  `track_ctrl/models.py`, with the QML in `ui/`.
  - **Track and selection:** load a track, select a line and a wayside.
  - **Programs:** load, write and run a program, commit it, browse the history.
  - **Switches:** hand-set and release a switch.
  - **Display:** the view rows in mph, and the NOT READY header.
- **Version/Build:** as above.
- **Test Approach:**
  - Automated cases drive `TrackControllerState` through the same user operations the QML
    calls (`stimulus.apply_user`), with Qt offscreen.
  - Manual cases check what only a person at the window can see.

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| SW-U-01 | The window starts with no track and an empty editor | Start `main.py` | No line or wayside listed; empty buffer; NOT READY | REQ-FUNC-058 | test_stimulus :: test_the_ui_starts_with_no_track_and_an_empty_editor |
| SW-U-02 | Inspecting a file reports the fixed wayside count | Inspect `green_line.json` | Line Green; block, switch and crossing counts; 6 waysides; nothing changed | REQ-INTF-012 | test_stimulus :: test_inspecting_a_file_reports_the_fixed_wayside_count; test_inspecting_changes_nothing |
| SW-U-03 | Loading uses the track's wayside count | Load Green | 6 waysides, none programmed; the first selected; empty editor | REQ-INTF-012 | test_stimulus :: test_loading_uses_the_waysides_the_track_is_built_with; test_a_loaded_track_has_no_programs_and_an_empty_editor; test_the_programmer_is_taken_to_what_was_loaded |
| SW-U-04 | Reloading a line replaces it and makes it not ready | Load Green twice, the first time with programs | Programs dropped; not ready | REQ-FUNC-058 | test_stimulus :: test_reloading_a_line_replaces_its_programs; test_loading_a_line_makes_a_ready_module_not_ready_again |
| SW-U-05 | Bad track files are refused | A wayside database; a non-layout file | Refused with the reason; state unchanged | REQ-NFR-003, REQ-NFR-004 | test_stimulus :: test_a_wayside_database_is_refused_with_the_reason; test_a_file_that_is_not_a_layout_is_refused |
| SW-U-06 | Selection and tabs | Select a line, a wayside and a tab; then an unknown wayside | Selection follows; the unknown one is refused, unchanged | REQ-INTF-001.5 | test_stimulus :: test_selection_and_tabs; test_bad_selection_is_refused |
| SW-U-07 | Load a program from a path | A `.plc` path | The source in the buffer, NOT COMMITTED | REQ-FUNC-050 | test_stimulus :: test_load_program_from_a_path |
| SW-U-08 | New gives an empty buffer | New | Empty buffer | — | test_stimulus :: test_new_gives_an_empty_buffer |
| SW-U-09 **S** | Commit is gated on a clean run | Commit before Run; Run with a warning, then Commit; Run clean, then Commit | Refused; refused; committed | REQ-FUNC-058 | test_stimulus :: test_commit_is_gated_on_a_run_exactly_as_in_the_ui |
| SW-U-10 | History is read-only | Open an older iteration and edit it | Read-only; Commit disabled | REQ-FUNC-050 | test_stimulus :: test_history_is_read_only |
| SW-U-11 | Vital code can be read, not edited | Open the attached vital code | Shown read-only | REQ-FUNC-058 | test_stimulus :: test_the_attached_vital_code_can_be_read_not_edited |
| SW-U-12 | An oversized edit is refused | A 5000-character append | `StimulusError`; buffer unchanged | REQ-NFR-003 | test_stimulus :: test_oversized_append_is_refused |
| SW-U-13 | The programmer cannot set maintenance or close blocks | A user op to set maintenance or close a block | Refused: only the CTC can | REQ-FUNC-057 | test_stimulus :: test_the_programmer_cannot_set_maintenance_mode; test_the_controller_ui_cannot_close_blocks |
| SW-U-14 | Maintenance is shown when the CTC sets it | A CTC switch command in effect | The maintenance indicator is on | REQ-FUNC-057 | test_stimulus :: test_maintenance_mode_is_shown_when_the_ctc_sets_it |
| SW-U-15 | Hand-set switch needs maintenance | `setSwitch` with and without a CTC command in effect | Refused without; accepted with; the dialog shows the CTC's command | REQ-FUNC-057 | test_stimulus :: test_manual_switch_needs_the_ctc_to_have_maintenance_on; test_the_switch_dialog_reports_the_ctc_command; test_maintenance_ending_takes_the_hand_set_switch_back |
| SW-U-16 | Views show speeds in mph | Block 1: circuit and suggestion of 12 m/s, 4 blocks | Both rows read `26.8 MPH · 4 BLK` | REQ-INTF-001.5 | test_stimulus :: test_the_views_show_speeds_in_mph |
| SW-U-17 | Clock shown from the sender | Steps with times; a paused clock state | The header shows each step's time and the sender's paused or speed state; no time before the first tick | REQ-INTF-013 | test_stimulus :: test_before_the_first_tick_there_is_no_time; test_each_step_shows_and_stamps_the_time_it_carries; test_the_senders_clock_state_is_only_shown |
| SW-U-18 | NOT READY header with its reason | *Manual:* load Green and commit to five of six waysides | NOT READY shown; hovering names the wayside with no program; it clears after the sixth commit | REQ-FUNC-055 | *Manual* |
| SW-U-19 | File dialogs | *Manual:* Load track… and Load .plc file, then cancel and pick | Cancel changes nothing; a pick loads the file | REQ-FUNC-050 | *Manual* |
| SW-U-20 | Run shows the sandbox and overrides | *Manual:* run a program that sets `XING_19 := 0` with a train on block 18 | The sandbox shows `OUT_XING_19 = 1` and the override listed; the live outputs are unchanged | REQ-FUNC-058 | *Manual* |
| SW-U-21 | Minimum display resolution | *Manual:* resize the window to 720 × 450 | All controls usable. **Known failure:** the minimum window size is 1100 × 720 (SDD open item 10). | REQ-INTF-011 | *Manual* |

### 7.9. StimulusServer (test link)

- **Item Description:** `track_ctrl/link.py`. `StimulusServer` and `_PipeServer` accept one
  test client on a named pipe and apply its `step`, `user`, `clock` and `hello` messages to
  `TrackControllerState`.
- **Version/Build:** as above.
- **Test Approach:** In-process integration tests. A real `TestClientState` connects to a
  real `StimulusServer` over the pipe, with Qt offscreen, and each case waits for the reply
  or the state change.

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| SW-T-01 | The test UI ticks the module with its clock | Connect; let the clock run | The module's tick count rises; nothing ticks before a client connects | REQ-INTF-013 | test_link :: test_the_test_ui_ticks_the_controller_with_its_clock; test_nothing_ticks_until_a_test_ui_connects |
| SW-T-02 | Paused clock stops the ticks; the clock state reaches the header | Pause; set the speed | No steps while paused; the header shows paused and the speed | REQ-INTF-013 | test_link :: test_a_paused_clock_stops_the_ticks; test_the_clock_state_reaches_the_programmers_header |
| SW-T-03 | A slow module is not buried in steps | 10 000 owed ticks | At most 50 queued (`MAX_OWED_TICKS`) | REQ-NFR-002 | test_link :: test_a_slow_controller_is_not_buried_in_steps |
| SW-T-04 | Nothing runs until the module is started up | Connect with no programs | Reports not ready; no commands | REQ-FUNC-058 | test_link :: test_nothing_runs_until_the_controller_is_started_up |
| SW-T-05 | Exactly one driver | A second client connects | Refused: "already driving"; a new client may connect after the first leaves | — | test_link :: test_a_second_test_ui_is_refused; test_a_new_test_ui_can_connect_after_the_first_leaves; test_connecting_marks_the_controller_as_driven; test_disconnecting_marks_it_idle_again |
| SW-T-06 | Physical inputs round-trip | Set occupancy, closure, a stuck switch, mph suggestions | The module changes and the read-back returns; mph arrives as whole m/s; a stuck switch holds its block | REQ-FUNC-054, REQ-FUNC-049 | test_link :: test_a_physical_input_changes_the_controller_and_comes_back; test_the_track_models_readback_returns_to_the_world; test_a_switch_the_machine_will_not_follow_is_held; test_a_speed_typed_in_mph_arrives_as_whole_mps; test_a_suggestion_can_be_sent_to_every_block_or_withheld |
| SW-T-07 | CTC maintenance and commands over the link | A stand-in CTC switch command | Every wayside in maintenance; the switch follows | REQ-FUNC-012, REQ-FUNC-057 | test_link :: test_the_ctcs_maintenance_mode_reaches_every_controller; test_a_ctc_switch_command_is_obeyed_in_maintenance |
| SW-T-08 | User inputs drive the window; the two kinds stay apart | `user` ops; physical inputs | User ops change only the window; physical inputs only the world; the window is told of both | REQ-INTF-001.5 | test_link :: test_a_user_input_drives_the_programmer_ui; test_the_programmer_ui_is_told_about_a_physical_input; test_the_two_kinds_of_input_touch_different_things |
| SW-T-09 | Refused inputs change nothing | A refused user op; a bad physical input; a block the target does not own; a refused step | An error reply; state unchanged; a refused step is not applied | REQ-NFR-004 | test_link :: test_a_refused_user_input_comes_back_as_an_error; test_a_bad_physical_input_changes_nothing; test_a_block_the_target_does_not_own_is_refused; test_a_refused_step_comes_back_as_an_error_and_is_not_applied |
| SW-T-10 | Garbage does not take the server down | Invalid bytes on the pipe | An error reply; the server still serves | REQ-NFR-003 | test_link :: test_garbage_does_not_take_the_server_down |
| SW-T-11 | Aspects reach the test UI | Yellow and super green states | The test UI shows them; an invalid combination shows red | REQ-FUNC-053 | test_link :: test_yellow_and_super_green_reach_the_test_ui_and_fail_safe |
| SW-T-12 | A new track updates the test UI | Load Green with a client connected | The client sees the new topology (wayside IDs and blocks) | REQ-INTF-012 | test_link :: test_loading_a_track_configuration_updates_a_connected_test_ui; test_stimulus :: test_the_test_ui_sees_the_new_topology |
| SW-T-13 | Nothing sent with no client | A stimulus with no client | Not sent; no error | — | test_link :: test_a_stimulus_with_no_client_connected_is_not_sent |

### 7.10. StandInWorld and test UI

- **Item Description:** `track_ctrl_test/world.py` (`StandInWorld`, `Train`) and
  `track_ctrl_test/client.py` (`TestClientState`). These are the stand-in CTC Office, Track
  Model and clock used to drive the module, so they are themselves test tools and must
  behave predictably.
- **Version/Build:** as above.
- **Test Approach:**
  - Unit tests on the world alone.
  - Rejection tests with one bad value each, each checking that the world is unchanged.
  - A manual run of both windows.

| ID | Test case | Inputs | Expected output | Req | Test |
|---|---|---|---|---|---|
| SW-X-01 | Suggests for every block by default, under the posted limit | A fresh world | A suggestion on every block, each at or under the block's limit | REQ-FUNC-049 | test_world :: test_it_suggests_for_every_block_by_default; test_the_stand_in_ctc_suggests_under_the_posted_limit |
| SW-X-02 | Trains move by simulated time | `advance(dt)` repeatedly | A train moves one block per 2 s of simulated time; it arrives at the module as occupancy | REQ-FUNC-054 | test_world :: test_trains_move_by_simulated_time; test_a_train_reaches_the_controller_as_occupancy |
| SW-X-03 | Hand edits survive moving trains | Hand occupancy while trains move | The edit persists; a hand clear masks only its block | — | test_world :: test_hand_edits_survive_while_trains_move; test_a_hand_clear_masks_only_its_own_block; test_clear_occupancy |
| SW-X-04 | Regrouping keeps the world; a changed line restarts it | A new topology, same or different line | Kept; restarted | — | test_world :: test_regrouping_the_waysides_keeps_the_world; test_a_line_that_changed_starts_again |
| SW-X-05 | Bad values are refused | Unknown block or switch, a block on no line, negative or fractional speeds, a bad position | Refused; every block as it was | REQ-NFR-004 | test_world :: test_unknown_blocks_and_switches; test_a_block_on_no_line_is_unknown; test_speeds_and_authorities_are_whole_non_negative_numbers; test_a_bad_value_leaves_every_block_as_it_was; test_switch_positions_are_validated |
| SW-X-06 | Snapshot describes the track for the world | `build_snapshot` | JSON; topology, switch commands and maintenance included | — | test_stimulus :: test_snapshot_is_json_and_reflects_a_stimulus; test_snapshot_describes_the_track_for_the_world; test_snapshot_carries_switch_commands_and_maintenance; test_the_test_ui_snapshot_works_with_no_track |
| SW-X-07 | End-to-end demonstration (rubric 6.0 to 6.9) | *Manual:* start both windows; load Green; commit the starter program on every wayside; then in the test UI: occupy blocks, close a block, set suggestions, command a switch, stick a switch | READY; signals, switches, crossings and circuits change as in SW-W and SW-V; the CTC report reflects occupancy | Rubric 6.0 to 6.9 | *Manual* |

### 7.11. Integration with the central harness

- **Item Description:** The module as a process under the central harness (D005), with the
  real CTC Office and Track Model through `ctc_edges` and the Track Model edge.
- **Version/Build:** To be set when the harness endpoint exists. All cases are *Planned*.
- **Test Approach:**
  - Scripted system runs.
  - The harness's CSV event log is compared with the expected sequence.
  - Rubric iteration 3: dispatch a train from the yard to a station.

| ID | Test case | Inputs | Expected output | Req | Status |
|---|---|---|---|---|---|
| SW-I-01 | Spawned and ready | `TrackOverflow.exe` starts the harness, which spawns the module | The module answers with its ready message; one driver only | REQ-INTF-013 | Planned |
| SW-I-02 | Not ready holds the Green Line | Harness running; Green loaded without programs | The CTC Office shows Green not ready; no commands reach the Track Model | REQ-FUNC-058 | Planned |
| SW-I-03 | Tick protocol | `step` with a request ID and a tick number at 1x and 10x | Every reply carries the same ID and tick, and arrives before the next tick; no tick dropped | REQ-NFR-001, REQ-NFR-002 | Planned |
| SW-I-04 | Real CTC suggestions | The CTC Office dispatches a train | Track circuits carry the suggestion; the reports show occupancy moving | REQ-FUNC-049, REQ-FUNC-055 | Planned |
| SW-I-05 | Real Track Model read-back and failures | The Track Model fails a block | The block is reported occupied; its neighbours are held | REQ-FUNC-059 | Planned |
| SW-I-06 | Maintenance from the CTC Office | The dispatcher closes a block and commands a switch | The switch moves when its block is clear; the block's circuit is 0 | REQ-FUNC-012, REQ-FUNC-057 | Planned |
| SW-I-07 | HW/SW equivalence | The same PLC program file loaded on SW (Green) and HW (Red) | Both accept it (needs the PLC names agreed; SDD open item 3) | REQ-INTF-009 | Planned |

**Risks.**

- **Harness.** The harness endpoint is not built, which blocks 7.11.
- **PLC names.** The names differ from HW PR #43, which blocks SW-I-07.
- **Window size.** REQ-INTF-011 fails today (SW-U-21).
- **Green Line only.** The window still accepts the Red Line (SDD open item 1), so a manual
  tester could load the wrong line.

---

## 8. Approvals

| Name | Role | Date |
|------|------|------|
| Harry Tye | Track Controller (SW) owner, test manager | |
| | Course instructor | |
