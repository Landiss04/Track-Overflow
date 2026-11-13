# Quality Assurance & Test Plan

**Document Version:** 0.1 (draft)
**Date:** 2026-11-13
**Prepared By:** Team 3
**Project Name:** Track Overflow — ECE1140 Train Management System

This is the group plan. It follows IEEE 829 and combines the Level Test Plan and the
Test Procedure into one document, as the course allows. Each module keeps its own
detailed plan (section 1.4). This plan sets the rules for every module plan and holds
the system-level tests.

---

## Table of Contents
1. [Introduction](#1-introduction)
   * [1.1 Purpose](#11-purpose)
   * [1.2 Scope](#12-scope)
   * [1.3 Definitions, Acronyms, and Abbreviations](#13-definitions-acronyms-and-abbreviations)
   * [1.4 References](#14-references)
   * [1.5 Overview](#15-overview)
2. [Quality Management](#2-quality-management)
   * [2.1 Resources, Roles and Responsibilities](#21-resources-roles-and-responsibilities)
   * [2.2 Schedules](#22-schedules)
   * [2.3 Control Procedures](#23-control-procedures)
   * [2.4 Dependencies](#24-dependencies)
   * [2.5 Risks and Assumptions](#25-risks-and-assumptions)
3. [Testing Strategy](#3-testing-strategy)
   * [3.1 Unit Testing](#31-unit-testing)
   * [3.2 Component Testing](#32-component-testing)
   * [3.3 Performance and Stress Testing](#33-performance-and-stress-testing)
   * [3.4 Automated Regression Testing](#34-automated-regression-testing)
   * [3.5 Beta Testing](#35-beta-testing)
   * [3.6 User Acceptance Testing](#36-user-acceptance-testing)
4. [Environment Requirements](#4-environment-requirements)
5. [Features Not to Be Tested](#5-features-not-to-be-tested)
6. [Test Procedure](#6-test-procedure)
7. [Approvals](#7-approvals)

---

## 1. Introduction

### 1.1. Purpose
This plan sets out how Team 3 shows that the Train Management System meets its
Software Requirements Specification (SRS). It states:

- who tests what, and when;
- how defects and changes are reported and controlled;
- the levels of testing, from unit tests to user acceptance;
- the environment the tests need;
- the system-level test procedure, with its inputs, expected outcomes and result
  record.

### 1.2. Scope
The system under test is the integrated Train Management System for the Green and Red
Lines:

- the five modules: CTC Office, Track Controller (SW and HW), Train Controller (SW and
  HW), Track Model and Train Model;
- the central harness that starts the modules, runs the shared clock, maps each
  module's outputs to its neighbours' inputs and writes the event log (D005, D017);
- the link to the Raspberry Pis that run the hardware variants (D021, D027).

Testing covers four levels: unit, component (one module), integration (modules through
the harness) and system (the whole executable on the lab machine). The out-of-scope
items are in section 5.

Every test is derived from a requirement in the SRS or a recorded design decision, not
from the code.

### 1.3. Definitions, Acronyms, and Abbreviations
| Term | Definition |
|------|------------|
| Authority | The number of blocks ahead a train may travel (D013) |
| CI | Continuous integration: tests run automatically on every push |
| CTC | Centralized Traffic Control; the CTC Office module |
| Harness | The central process that starts every module, drives the shared clock and passes messages between modules (D005) |
| HW / SW | The hardware (Raspberry Pi) and software variants of the Track Controller and Train Controller |
| IEEE 829 | IEEE Standard for Software and System Test Documentation |
| Pi | Raspberry Pi |
| PLC | Programmable Logic Controller; the Track Controller's Boolean program |
| Regression test | A re-run of the existing tests to show a change broke nothing |
| Safety case | A test whose failure could let a train into an unsafe state; marked **S** |
| Tick | One step of the shared simulation clock; 0.1 s of simulated time by default (D017) |
| UAT | User acceptance testing |

### 1.4. References
- `documents/srs-filled.md` — Software Requirements Specification v1.0
- `documents/sdd/` — Software Design Description
- `documents/system-integration-design.md` — harness and inter-module design
- `documents/UI_Style_Guide.md` — UI style guide
- `documents/Coding Standards (Group).docx` and `documents/PYTHON_STYLE_GUIDE.md`
- `documents/test_plan_track_ctrl_sw.md` — Track Controller SW test plan
- `TrackCtrlHw/docs/Track_Controller_HW_Test_Plan.docx` — Track Controller HW test plan
- `documents/test-case-template.xlsx` — test result record
- `documents/Project_Information/ECE1140 Deliverable Descriptions v4.pdf`
- `documents/Project_Information/Iterations v3.pdf`
- IEEE 829-2008, Standard for Software and System Test Documentation

### 1.5. Overview
Section 2 covers who does the testing, when, and how defects and changes are
controlled. Section 3 describes each level of testing. Section 4 lists the hardware,
software and tools. Section 5 lists what is not tested and why. Section 6 is the
system test procedure and its result record.

---

## 2. Quality Management

### 2.1. Resources, Roles and Responsibilities
Each module owner tests their own module. The harness owner tests the integration.
Every member runs the system tests.

| Role | Responsibility | Owner |
|------|-----------------|-------|
| QA lead | Owns this plan; keeps it in step with the SRS; runs the weekly bug count | [team to assign] |
| CTC Office owner | Module test plan, unit and component tests, CTC system cases | Landis Stroh |
| Track Controller SW owner | Module test plan, unit and component tests | Harry Tye |
| Track Controller HW owner | Module test plan, unit, component and Pi tests | Braden Bosilovich |
| Train Controller SW owner | Module test plan, unit and component tests | Jonathan Tsang [confirm] |
| Train Controller HW owner | Module test plan, unit, component and Pi tests | Ivan Zheng [confirm] |
| Track Model owner | Module test plan, unit and component tests | Deni Ephraim |
| Train Model owner | Module test plan, unit and component tests | Kevin Schillinger |
| Harness and integration | Edge-mapping, clock and end-to-end tests; CI workflow | Kevin Schillinger |
| HW/SW equivalence | Shows the two variants of a module expose the same interface (REQ-INTF-009, REQ-INTF-010) | Both variant owners of that module |
| System tester | Runs section 6 on the lab machine and records results | Every team member |
| Reviewer | Reviews the plan and its results | Course instructor and team |

### 2.2. Schedules
| Milestone | Date | Testing deliverable |
|-----------|------|---------------------|
| Iteration 2 — Sub-System Presentations | 2026-10-08 | Each module runs standalone with its test UI |
| WP2 | 2026-10-22 | Module test plans |
| Iteration 3 — System Presentations | 2026-11-12 | Dispatch a train from the yard to a station, all modules communicating |
| Lab 1 — QA & Testing | 2026-11-13 | This plan drafted; bug tracking starts in GitHub Issues; pytest runs in CI |
| WP3 / Iteration 4 — Final Demo | 2026-12-10 | Executed test plans, defect reports and the weekly bug count |

From 2026-11-13 until the final demo:

- unit and component tests run on every push (section 3.4);
- the system cases of section 6 are run before each demonstration and at least once a
  week;
- the bug count is taken every week from GitHub Issues (REQ-COMP-009).

### 2.3. Control Procedures

#### 2.3.1. Problem Reporting
Every major defect is recorded as a GitHub Issue in the team repository. A major
defect is one that:

- fails a test in this plan or a module plan;
- crashes a module or the harness, or leaves an unhandled error (REQ-NFR-005,
  REQ-NFR-006);
- lets a train into an unsafe state;
- is found by someone other than the module's owner.

Each issue carries:

- the `bug` label and a label for the module (`ctc`, `track-ctrl-sw`, `track-ctrl-hw`,
  `train-ctrl-sw`, `train-ctrl-hw`, `track-model`, `train-model`, `harness`);
- a severity label:
  - `critical` — a safety failure, a crash, or the system cannot run;
  - `major` — a requirement is not met, with no workaround;
  - `minor` — a requirement is met badly, or a workaround exists;
- the build (branch and commit), steps to reproduce, the expected and the actual
  result;
- the test case ID, where a test found it.

The fixing commit or pull request references the issue (`Fixes #n`). The issue closes
when the fix is merged to `development` and the failing test passes. The weekly bug
count, opened and closed per week, is taken from the issue history (REQ-COMP-009).

Small defects an owner finds and fixes in the same sitting need no issue.

#### 2.3.2. Change Request
- **Requirements.** A change to the SRS after WP1 needs the whole team's agreement and
  is recorded in its Revision History (REQ-DSN-009).
- **Interfaces and decisions.** A change to a signal, an interface or a recorded
  decision is proposed through the `truth` branch process in `AGENTS.md`. A change to a
  module with two variants needs both variant owners to review it.
- **Code.** All work happens on feature branches cut from `development` and merges back
  through a pull request. `main` is release-only (D003). A pull request merges only
  when the automated tests pass (section 3.4).
- **This plan.** A change to a test's inputs or expected outcome is made by the module
  owner and reviewed by the QA lead.

### 2.4. Dependencies
- System tests need every module integrated under the harness.
- Hardware-variant tests need both Raspberry Pis connected over USB (D027).
- A Track Controller line carries traffic only once its waysides have PLC programs
  loaded (REQ-FUNC-050).
- A new train runs only once an engineer has set its gains (D024).
- Module tests depend on the course track layout files for the Green and Red Lines
  (REQ-INTF-012).

### 2.5. Risks and Assumptions
| Risk | Effect | Mitigation |
|------|--------|------------|
| A Raspberry Pi is unavailable or its link fails | The Red Line and the HW variants cannot be tested | Test the HW variants' logic on the host first; keep a spare Pi and cable |
| Two modules disagree on a value or unit | Wrong behaviour that each module's own tests miss | Each producer-to-consumer edge is mapped and tested in one place, the harness (D005) |
| The system behaves differently on Windows 11 than on developer machines | A demo fails on the lab machine | Run section 6 on Windows 11 before each demo |
| The lab machine cannot sustain 10x | Simulated time runs slower than requested | Performance tests on the lab machine (section 3.3) |
| Tests are written from the code, not the requirements | Tests pass while a requirement is unmet | Every test names its requirement or decision; the QA lead reviews the trace |
| Little time remains before 2026-12-10 | Not every case is run | Safety cases and the demo use case run first |

**Assumptions:**
- The course track layout files are correct.
- The lab machines run Windows 11.
- The customer accepts the recorded deviations, such as the 0.1 s tick (D017).

---

## 3. Testing Strategy

### 3.1. Unit Testing
- **What:** classes and functions inside one module, with no other module running.
- **Who:** the module owner.
- **How:**
  - Tests are written with `pytest`, or with `unittest`, which `pytest` also runs.
  - Each module keeps its tests in its own `tests/` folder, apart from the code it
    delivers.
  - Each test is derived from a requirement and names it in its module plan.
  - Floating-point results are compared with `pytest.approx`, never with `==`.
  - Invalid inputs are tested as well as valid ones, including that a rejected input
    leaves the state unchanged (REQ-NFR-003, REQ-NFR-004).
  - Tests that build a Qt window run with `QT_QPA_PLATFORM=offscreen`.
- **Pass:** every unit test of the module passes.

### 3.2. Component Testing
- **What:** one whole module through its boundary types, its window and its test UI.
- **Who:** the module owner.
- **How:**
  - Each module's test UI stands in for its neighbours and feeds the module inputs
    (Iteration 2).
  - Black-box tests drive the module only through its public interface and check its
    outputs.
  - Each hardware variant is tested against the same cases as its software variant, to
    show both expose the same interface (REQ-INTF-009, REQ-INTF-010).
  - Integration tests in `common/harness/tests/` drive real modules through the harness
    and check each edge mapping.
- **Pass:** every component and integration test passes, and every manual case gives
  its expected result.

### 3.3. Performance and Stress Testing
- **What:** the system's speed and its behaviour under load and bad input.
- **Who:** the harness owner, with each module owner for their module.
- **How:**
  - Run the full system at 1x and at 10x on a Windows 11 lab machine. Check that no tick
    is dropped (REQ-NFR-001.2) and that results at 10x match those at 1x
    (REQ-NFR-002).
  - Measure the time from launch to ready (REQ-NFR-007, 20 s or less).
  - Stall a module, and check that the harness pauses the clock and names it (D017).
  - Run several trains on both lines at once.
  - Enter out-of-range, non-numeric and extreme values in every input field
    (REQ-NFR-003, REQ-NFR-004).
- **Pass:** the system cases marked *Performance* in section 6 pass, and no crash or
  unhandled error occurs (REQ-NFR-005, REQ-NFR-006).

### 3.4. Automated Regression Testing
- Every push and pull request to `development` or `main` runs every module's unit and
  component tests in GitHub Actions (`.github/workflows/pytest.yml`).
- Each module's tests run from its own folder, since each module imports its own
  packages from there.
- A pull request does not merge while the run fails.
- Each owner runs their module's tests before every push.

### 3.5. Beta Testing
- Team members who do not own a module run the integrated system on the lab machine and
  use that module's window as its intended user would.
- Each problem they find is filed as a GitHub Issue (section 2.3.1).
- Beta testing runs from Iteration 3 (2026-11-12) to the final demo.

### 3.6. User Acceptance Testing
- The customer, represented by the course instructor, accepts the system at the
  demonstrations.
- Acceptance follows the system cases of section 6, starting with the Iteration 3 use
  case: dispatch a train from the yard to a station with every module communicating.
- Each module is judged against its persona and the UI style guide (REQ-INTF-003).

---

## 4. Environment Requirements

### 4.1. Hardware Requirements
- A Windows 11 lab machine, with mouse, keyboard and a monitor of at least 720 × 450
  (REQ-INTF-008, REQ-INTF-011).
- Two Raspberry Pis, one for the Track Controller HW and one for the Train Controller HW,
  each connected to the host over USB (D021, D027).
- Developer machines on Windows, Linux or macOS, for unit and component tests.

### 4.2. Software Requirements
- Python 3.10 or later.
- PySide6 6.11.2 and PyInstaller 6.22.2, as pinned in `requirements.txt`, installed in
  a virtual environment.
- The Green and Red Line layout files (REQ-INTF-012).
- The built Track Overflow executable for system tests.

### 4.3. Tools Required
| Tool | Use |
|------|-----|
| `pytest` | Runs every unit and component test |
| `unittest` | Test framework used by some modules; run by `pytest` |
| `mypy` | Static type checks, where a module uses them |
| `flake8`, `pylint` | Style and naming checks per the coding standards |
| GitHub Actions | Runs the regression tests on every push |
| GitHub Issues | Defect tracking and the weekly bug count |
| `test-case-template.xlsx` | Records the result of each manual case |
| The event log (CSV) | Evidence of what happened during a system run (REQ-NFR-008) |

---

## 5. Features Not to Be Tested
| Feature | Reason |
|---------|--------|
| Moving Block Overlay (MBO Controller and Scheduler) | Out of scope (D001) |
| The Blue Line | Not part of the final product (D023) |
| The inside of the yard | The yard is a black box; only release and return are tested (D022) |
| 1 ms simulation ticks (REQ-NFR-001.1) | Recorded deviation; the tick is 0.1 s (D017) |
| Module test UIs in the integrated system | Removed at integration (D005, D010); tested only at component level. The Track Controller HW test UI stays for standalone use and is tested there |
| Speeds other than 1x and 10x | Not offered (D017) |
| Compliance and documentation requirements (REQ-COMP, most REQ-DSN) | Verified by inspection, not by test (SRS section 4) |

---

## 6. Test Procedure

Each module's detailed cases live in its own plan (section 1.4). The cases below test
the whole system, are run on the lab machine with the built executable, and are
recorded here and in `test-case-template.xlsx`.

**Before each run:**
1. Connect both Raspberry Pis.
2. Launch the executable with no arguments. The harness starts every module.
3. Load a PLC program into every wayside on both lines.

**Recording:**
- *Pass/Fail*, *Tester* and *Date tested* are filled in for every run.
- A failure gets a *Failure description* and the number of its GitHub Issue.
- **S** marks a safety case: one failure fails the system.

| ID | Test | Req | Inputs | Expected outcome | Pass/Fail | Failure description | Tester | Date tested |
|----|------|-----|--------|------------------|-----------|---------------------|--------|-------------|
| ST-01 | Startup | REQ-NFR-007, REQ-INTF-012 | Launch the executable; start a stopwatch | Every module window opens and reports ready within 20 s; Green and Red Lines are loaded; simulated time reads 05:00:00 | | | | |
| ST-02 | Dispatch on the Green Line | REQ-FUNC-004, REQ-FUNC-009, REQ-FUNC-005 | CTC Office, manual mode: dispatch a train to Glenbury with an arrival time 10 min ahead; set the train's Kp and Ki in its Train Controller | The train is released into block 63; occupancy shows in the CTC Office and the Track Model; the train stops in block 65 (Glenbury), opens its doors and dwells 45 s (D007, D022) | | | | |
| ST-03 | Dispatch on the Red Line (HW variants) | REQ-INTF-006, REQ-INTF-007, D021 | CTC Office: dispatch a Red Line train to Herron Ave; set its gains | The train is released into block 9, driven by the Train Controller HW and protected by the Track Controller HW; it runs 9 → 10 → … → 15, never back toward 8; the block 16 switch is set to the 15 leg; it stops in block 16 (Herron Ave), then continues to 17 | | | | |
| ST-04 | Manual speed change | REQ-FUNC-025, REQ-FUNC-031 | During ST-02, switch the Train Controller to manual mode and set 20 mph, below the block's limit | The train's speed settles at 20 mph; it never exceeds the suggested speed or the block limit | | | | |
| ST-05 | PLC moves a switch | REQ-FUNC-050, REQ-FUNC-052, REQ-FUNC-053 | Load the Track Engineer's PLC program into the Green wayside that holds a switch; route a train across it | The switch moves as the program commands; the light colours follow the program; the CTC Office and the Track Model show the new position | | | | |
| ST-06 **S** | Closed block | REQ-FUNC-011, REQ-FUNC-058 | CTC Office: close a block ahead of a running train | The train gets no authority into the closed block and stops before it | | | | |
| ST-07 | Switch in maintenance | REQ-FUNC-012, REQ-FUNC-057 | CTC Office: close the block of a switch, then set the switch to its other position | The Track Controller enters maintenance mode and moves the switch; the Track Model shows the new position | | | | |
| ST-08 **S** | Broken rail | REQ-FUNC-024, REQ-FUNC-059 | Track Model: set a broken rail on a block ahead of a running train | The block shows as occupied; the train stops before it | | | | |
| ST-09 **S** | Passenger emergency brake | REQ-FUNC-047, D011 | Train Model: press the passenger emergency brake while the train moves | The train brakes to a stop; the passenger cannot release the brake | | | | |
| ST-10 **S** | Train failure | REQ-FUNC-048, REQ-FUNC-038 | Train Model: set an engine failure on a moving train | The Train Controller window shows the failure, and the Train Controller applies the emergency brake; the train stops | | | | |
| ST-11 | Pause and resume | REQ-FUNC-003, D017 | CTC Office: pause for 30 s, then resume | Simulated time and every train stop while paused, and continue from the same values after resuming | | | | |
| ST-12 *Performance* | 10x speed | REQ-FUNC-002, REQ-NFR-002, REQ-NFR-001.2 | Repeat ST-02 at 10x | Simulated time runs about 10 times faster; the train stops in the same block as at 1x; no tick is dropped | | | | |
| ST-13 | Automatic mode | REQ-FUNC-007, REQ-FUNC-010, D020 | CTC Office: switch to automatic mode and load the Green Line schedule | Trains are dispatched from the schedule and stop only at their scheduled stations | | | | |
| ST-14 | Invalid input | REQ-NFR-003, REQ-NFR-004, REQ-INTF-004 | Enter -5 as Kp, `abc` as a temperature setpoint, and an empty destination | Each is rejected with an error message in the common format; nothing in the simulation changes | | | | |
| ST-15 *Performance* | A module stalls | D017, REQ-NFR-006 | Suspend one module process during a run | Within about 1 s the harness pauses the clock and names the late module; no other module crashes | | | | |
| ST-16 | Event log | REQ-NFR-008, REQ-INTF-015 | After ST-02, open the event log | One CSV file holds the dispatch, the release and the station stop, each with its simulated time | | | | |
| ST-17 | Return to yard | D022 | CTC Office: send the train from ST-02 back to the yard | The train is retired at block 57; the block clears; the CTC Office marks the run done | | | | |

---

## 7. Approvals

| Name | Role | Date |
|------|------|------|
| | QA lead | |
| Landis Stroh | CTC Office | |
| Harry Tye | Track Controller SW | |
| Braden Bosilovich | Track Controller HW | |
| | Train Controller SW | |
| | Train Controller HW | |
| Deni Ephraim | Track Model | |
| Kevin Schillinger | Train Model, harness | |
