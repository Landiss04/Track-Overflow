# Software Requirements Specification
## For ECE1140 Train Management System

Version 1.0  
Prepared by Team 3  
University of Pittsburgh  
2026-08-28

## Table of Contents
<!-- TOC -->
* [1. Introduction](#1-introduction)
    * [1.1 Document Purpose](#11-document-purpose)
    * [1.2 Product Scope](#12-product-scope)
    * [1.3 Definitions, Acronyms, and Abbreviations](#13-definitions-acronyms-and-abbreviations)
    * [1.4 References](#14-references)
    * [1.5 Document Overview](#15-document-overview)
* [2. Product Overview](#2-product-overview)
    * [2.1 Product Perspective](#21-product-perspective)
    * [2.2 Product Functions](#22-product-functions)
    * [2.3 Product Constraints](#23-product-constraints)
    * [2.4 User Characteristics](#24-user-characteristics)
    * [2.5 Assumptions and Dependencies](#25-assumptions-and-dependencies)
    * [2.6 Apportioning of Requirements](#26-apportioning-of-requirements)
* [3. Requirements](#3-requirements)
    * [3.1 External Interfaces](#31-external-interfaces)
    * [3.2 Functional](#32-functional)
    * [3.3 Quality of Service](#33-quality-of-service)
    * [3.4 Compliance](#34-compliance)
    * [3.5 Design and Implementation](#35-design-and-implementation)
    * [3.6 AI/ML](#36-aiml)
* [4. Verification](#4-verification)
* [5. Appendixes](#5-appendixes)
<!-- TOC -->

## Revision History

| Name   | Date       | Reason For Changes     | Version |
|--------|------------|------------------------|---------|
| Team 3 | 2026-08-28 | Initial document draft | 1.0     |

## 1. Introduction

This SRS defines the software requirements for the ECE1140 Train Management System, a simulated rail network developed for the North Shore Extension project contract by PAAC. It covers functional behavior, quality attributes, and verification criteria for the system.

### 1.1 Document Purpose

This document defines what the ECE1140 Train Management System must do. It is intended for the development team and the customer, the Port Authority of Allegheny County, and serves as the baseline for design and testing throughout the project lifecycle.

### 1.2 Product Scope

The ECE1140 Train Management System is a Python-based application that provides a train management service with a graphical user interface. It allows operators to dispatch, monitor, and manage trains on a simulated rail network.

### 1.3 Definitions, Acronyms, and Abbreviations

| Term | Definition |
| --- | --- |
| API       | Application Programming Interface |
| Authority | The maximum distance a train is permitted to travel before stopping |
| Block     | A discrete section of track that can be occupied by at most one train |
| CTC       | Centralized Traffic Control — the operator dispatching interface |
| SRS       | Software Requirements Specification |
| UI        | User Interface |
| UML       | Unified Modeling Language |
| PAAC      | Port Authority of Allegheny County |

### 1.4 References

| # | Title | Author | Date | Type |
|---|-------|--------|------|------|
| 1 | ECE1140 Course Project Description | University of Pittsburgh | 2026-08 | Normative |
| 2 | IEEE Std 830-1998: Recommended Practice for SRS | IEEE | 1998 | Informative |

### 1.5 Document Overview

Section 2 provides product context, functions, and constraints. Section 3 contains all verifiable requirements. Section 4 maps each requirement to a verification method. Section 5 contains supporting appendixes. Requirements marked "shall" are mandatory; "should" is recommended; "may" is optional.

---

## 2. Product Overview

### 2.1 Product Perspective

The ECE1140 Train Management System is a new, standalone Python application developed for the ECE1140 course project. It is not a replacement for any existing system. The system simulates a complete commuter rail network and exposes operator, driver, and maintenance interfaces through a graphical UI.

### 2.2 Product Functions

The system provides a train management service through a graphical UI, including:

- Dispatching and monitoring trains on a simulated network
- Displaying live track and train status to the operator
- Enforcing safe train separation and speed limits
- Simulating train motion, station stops, and failure conditions

### 2.3 Product Constraints

- The system shall be implemented in Python 3.10 or later
- The system shall run on a standard, modern Windows 11 PC

### 2.4 User Characteristics

| User Class | Description | Expertise |
|------------|-------------|-----------|
| CTC Operator | Dispatches trains and monitors the network | No programming knowledge required |
| Train Driver | Controls a single train in manual mode | Basic operational training |
| Maintenance Engineer | Injects failures for testing | Technical; understands system internals |
| Course Instructor | Evaluates the system against the grading rubric | Full technical expertise |

### 2.5 Assumptions and Dependencies

| # | Assumption / Dependency | Impact if False |
|---|------------------------|-----------------|
| A1 | Course-provided track layout JSON files are correct and complete | Track simulation would require rework |
| A2 | Lab machines have Python 3.10+ available | Additional setup time required |
| A3 | Module interface contracts are agreed by end of Sprint 1 | Late-stage integration failures |
| A4 | Sprint end dates do not change after Week 2 | Requirement phasing may need revision |

### 2.6 Apportioning of Requirements

| Functional Area | Sprint 1 | Sprint 2 | Sprint 3 | Sprint 4 |
|----------------|----------|----------|----------|----------|
| Dispatching & Scheduling | Basic UI shell | Schedule entry | Auto-dispatch | Full dispatch |
| Safety & Control | Interface contracts | Authority logic | Switch/signal control | Full safety demo |
| Train & Track Simulation | Layout file loading | Physics/occupancy | Failure injection | Complete simulation |
| Station Operations | — | Door logic | Passenger counts | Full station behavior |

---

## 3. Requirements

Each requirement has a unique, stable identifier (`REQ-<AREA>-<NUM>`) used for traceability to Section 4 and to test cases. Numbers are never reused if a requirement is removed.

### 3.1 External Interfaces

#### 3.1.1 User Interfaces

REQ-INTF-001: The system shall provide a graphical user interface (GUI) for each defined submodule.

REQ-INTF-002: The system shall provide a GUI for CTC operators to dispatch and monitor trains.

REQ-INTF-003: The system shall provide a GUI for train drivers to view train status and control their train in manual mode.

REQ-INTF-004: The system shall provide a GUI for maintenance engineers to inject and clear simulated failures.

#### 3.1.2 Hardware Interfaces

REQ-INTF-005: The system shall provide a separate hardware variation for the Wayside Controller submodule.

REQ-INTF-006: The system shall provide a separate hardware variation for the Train Controller submodule.

REQ-INTF-007: The system shall accept user input via a standard mouse, keyboard, and monitor.

REQ-INTF-008: The system shall require no physical hardware beyond the standard mouse, keyboard, and monitor, with all train and track behavior simulated in software.

#### 3.1.3 Software Interfaces

REQ-INTF-009: The system shall load track layout data from JSON files at startup.

REQ-INTF-010: All submodules shall share a single simulation clock.

### 3.2 Functional

REQ-FUNC-001: The system shall allow operators to dispatch trains manually.

REQ-FUNC-002: The system shall allow operators to dispatch trains from a pre-loaded schedule.

REQ-FUNC-003: The system shall display the current state of all trains, track blocks, switches, and signals in the UI.

REQ-FUNC-004: The system shall track block occupancy for every block.

REQ-FUNC-005: The system shall limit each train's movement to prevent collisions based on block occupancy.

REQ-FUNC-006: The system shall command each train's speed within the speed limit of its current block.

REQ-FUNC-007: The system shall position each switch according to the route of the train approaching it.

REQ-FUNC-008: The system shall bring a train to a stop when its authority is exhausted.

REQ-FUNC-009: The system shall bring a train to a stop when a failure is detected.

REQ-FUNC-010: The system shall bring a train to a stop when the driver requests emergency braking.

REQ-FUNC-011: The system shall simulate each train's velocity and position based on power, braking, and track grade.

REQ-FUNC-012: The system shall manage door open/close cycles at each station stop.

REQ-FUNC-013: The system shall manage passenger counts at each station stop.

REQ-FUNC-014: The system shall detect injected failures.

REQ-FUNC-015: The system shall respond to detected failures safely without requiring a full restart.

REQ-FUNC-016: The system shall support running the simulation in real-time speed.

REQ-FUNC-017: The system shall support running the simulation in fast-forward speed.

### 3.3 Quality of Service

#### 3.3.1 Performance

REQ-NFR-001: The system shall run smoothly in real-time mode.

REQ-NFR-002: The system shall maintain simulation correctness while running in fast-forward mode.

#### 3.3.2 Security

REQ-NFR-003: The system shall validate all user inputs.

REQ-NFR-004: The system shall reject invalid user input entries without altering simulation state.

#### 3.3.3 Reliability

REQ-NFR-005: The system shall operate without crashes during normal simulation runs.

REQ-NFR-006: The system shall operate without unhandled errors during normal simulation runs.

#### 3.3.4 Availability

REQ-NFR-007: The system shall start up and be ready for use within a reasonable time after launch.

#### 3.3.5 Observability

REQ-NFR-008: The system shall produce a log of significant simulation events for debugging and review.

### 3.4 Compliance

REQ-COMP-001: The team shall produce UML class diagrams as required by the course rubric.

REQ-COMP-002: The team shall produce UML sequence diagrams as required by the course rubric.

REQ-COMP-003: The team shall produce a UML use case diagram as required by the course rubric.

REQ-COMP-004: All source code and documentation shall be maintained in the course Git repository.

REQ-COMP-005: All commits shall be linked to issue tracker tickets.

REQ-COMP-006: Each team member shall contribute code commits in every sprint.

### 3.5 Design and Implementation

#### 3.5.1 Installation

REQ-DSN-001: The system shall be launchable with `python main.py` after running `pip install -r requirements.txt` with no additional configuration.

<!-- TODO: rewrite REQ-DSN-001 to require a standalone Windows 11 executable instead of a `python main.py` launch; source-install path is no longer the delivery target -->

#### 3.5.2 Build and Delivery

REQ-DSN-002: The repository shall include a `requirements.txt` with pinned package versions so the system installs and runs consistently on any compatible machine.

<!-- TODO: revisit REQ-DSN-002 once packaged as an executable — pinned requirements.txt may no longer be the delivery artifact; may need a build/packaging step (e.g. PyInstaller) instead -->

#### 3.5.3 Distribution

REQ-DSN-003: The system shall run on a single machine with no external services or network connections required.

#### 3.5.4 Maintainability

REQ-DSN-004: Software modules shall interact through defined interfaces rather than accessing each other's internal state directly.

#### 3.5.5 Reusability

REQ-DSN-005: Common utilities such as the simulation clock and event logger shall be implemented as standalone modules usable by any part of the system.

#### 3.5.6 Portability

REQ-DSN-006: The system shall use platform-neutral file path handling so it runs correctly regardless of the developer's operating system.

#### 3.5.7 Cost

No financial cost targets apply. All required tools (Python, Git, IDE) are free.

#### 3.5.8 Deadline

| Milestone | Date | Deliverables |
|-----------|------|--------------|
| Sprint 1 | 2026-09-25 | Module interfaces, track loader, dispatch UI shell, POC demo |
| Sprint 2 | 2026-10-16 | Train dynamics, occupancy, authority, basic scheduling |
| Sprint 3 | 2026-11-06 | Full safety logic, switch/signal control, failure injection |
| Final Demo | 2026-11-20 | Complete integrated system; public presentation |
| Documentation | 2026-11-25 | UML, SRS, and test reports submitted |

#### 3.5.9 Proof of Concept

REQ-DSN-007: A Sprint 1 POC shall demonstrate a simulated train moving between track blocks under authority control with a basic dispatch UI, validating the core data flow before full implementation begins.

#### 3.5.10 Change Management

REQ-DSN-008: Requirement changes after Sprint 1 shall require full team agreement and shall be recorded in the Revision History table.

### 3.6 AI/ML

Not applicable. All logic is deterministic and rule-based. No machine learning is used in v1.0.

---

## 4. Verification

| Area | Verification Method |
|------|---------------------|
| User interfaces (map, dispatch form, driver display, failure UI) | Demonstration |
| Functional behavior (dispatch, scheduling, occupancy, authority, speed, switching, braking, physics, doors, failures) | Test + Demonstration |
| Performance and reliability | Test |
| Input validation | Test |
| Event logging | Inspection |
| UML documentation, version control, team contributions | Inspection |
| Installation and single-machine deployment | Demonstration |
| Module independence and shared utilities | Inspection |

---

## 5. Appendixes

### Appendix A — Track Layout File Format

Track layout files are JSON files provided by the course instructor (see `TrackModel/`). Each file lists a line name and an array of blocks; each block includes a block number, section letter, length (m), grade (%), speed limit (km/h), elevation and cumulative elevation (m), and an optional `infrastructure` object describing features such as stations, switches, railway crossings, beacons, and transponders.

### Appendix B — Safe Braking Distance Formula

```
d = v² / (2 × a)
```

Where _d_ is stopping distance (m), _v_ is current speed (m/s), and _a_ is deceleration (m/s²). 
