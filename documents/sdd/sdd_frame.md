<div class="cover-page">

<p class="cover-kicker">ECE 1140 &middot; Work Package 2 &middot; Design Review</p>

# Software Design Description

## For the Railway Simulation Project

<div class="cover-rule"></div>

<p class="cover-meta">Version 1.0<br>Issued for the design review of 2026-10-22<br>IEEE Std 1016-2009</p>

| Module | Owner |
|--------|-------|
| System integration | Braden Bosilovich |
| CTC Office | Landis |
| Track Controller (SW) | Harry Tye |
| Track Controller (HW) | Braden Bosilovich |
| Track Model | Deni Ephraim |
| Train Model | Kevin Schillinger |
| Train Controller (SW and HW) | Jonathan Tsang, Ivan Zheng |

<p class="cover-org">Team 3, Track Overflow<br>University of Pittsburgh &middot; ECE 1140<br>Prepared for the Port Authority of Allegheny County</p>

</div>

<!-- TOC -->

## Revision History

| Name | Date | Reason for changes | Version |
|------|------|--------------------|---------|
| Each module owner | 2026-10-20 to 2026-10-22 | Module contributions: CTC Office (Landis), Track Controller SW (Harry Tye), Track Controller HW (Braden Bosilovich), Track Model (Deni Ephraim), Train Model (Kevin Schillinger), Train Controller (Jonathan Tsang, Ivan Zheng) | 0.x |
| Ivan Zheng | 2026-10-21 | System architecture figure | 0.9 |
| Braden Bosilovich | 2026-10-22 | Combined SDD: system views, software architecture, deployment, representative interaction and system-wide concepts written once for the system; module contributions brought in as Section 5 | 1.0 |

---

## 1. Introduction

### 1.1 Document Purpose

This document describes the design of the Railway Simulation: how the system is divided
into modules, how they exchange data, the concepts every module relies on, and the design of
each module. It follows IEEE Std 1016-2009. Its readers are the team, the integrator of the
central harness, and the course staff who review the design.

### 1.2 Subject Scope

The system being designed is the Railway Simulation, version 1.0: a simulation of a light
rail system for the Port Authority of Allegheny County, run on one Windows 11 PC with two
Raspberry Pi 5 boards attached by USB. The system has five modules, two of which have a
software and a hardware variant, so seven module processes run:

| Module | Variant | Line | Runs on | Owner |
|--------|---------|------|---------|-------|
| CTC Office | one | Green and Red | Host PC | Landis |
| Track Controller | SW | Green | Host PC | Harry Tye |
| Track Controller | HW | Red | Raspberry Pi 5, window on the host PC | Braden Bosilovich |
| Track Model | one | Green and Red | Host PC | Deni Ephraim |
| Train Model | one | Green and Red | Host PC | Kevin Schillinger |
| Train Controller | SW | Green | Host PC | Jonathan Tsang|
| Train Controller | HW | Red | Raspberry Pi 5, window on the host PC | Ivan Zheng |

A central harness, which is not a module, starts every module process, owns the one
simulation clock, maps every module's outputs to its consumers' inputs and writes the event
log (D005, D017).

In scope:

- The system's composition, its interfaces and the central harness (Section 3).
- The key system-wide concepts: route, authority, wayside distribution, timing, vitality,
  the wayside language and the hardware/software interface (Section 3.7).
- The design of every module: use cases, architecture, classes, interfaces, sequences
  and the module's own decisions (Section 5).

Out of scope:

- The Blue Line, which is not part of the final product (D023).
- Moving Block Overlay (D001).
- The requirements themselves (the SRS), the source code, and the test plans and results.

### 1.3 Definitions, Acronyms, and Abbreviations

| Term | Definition |
|------|------------|
| Authority | The number of blocks ahead of a train's current block that it may still enter before it must stop; a non-negative integer (D013). 0 means stop before leaving the current block. |
| Beacon | Station data heard near a station: station name, platform side and whether the track is underground. |
| Block | The smallest unit of track. At most one train occupies it. Named by its line and number. |
| Commanded speed | The speed, in whole m/s, the Track Controller sends down a block's track circuit. |
| CTC | Centralized Traffic Control: the CTC Office, which dispatches trains and suggests speed and authority. |
| Edge | The connection from a producing module to a consuming one. The harness owns one mapping per edge. |
| Fail-safe | The most restrictive state, which a fault drives a vital module to. |
| Harness | The central harness: the process that starts and steps every module, owns the clock and maps every edge (D005). |
| HW, SW | The hardware and software variants of the Track Controller and Train Controller (D021). |
| Line | A complete track layout: Green or Red. |
| Murphy | The tester persona who injects failures. |
| PLC | Programmable logic controller. Each wayside runs a Boolean PLC program. |
| Protocol | A `typing.Protocol`: a Python structural interface type, used for module contracts. |
| Route | The sequence of blocks a train runs from the yard to its stations and back, in the order the track reaches them. |
| SDD, SRS | Software Design Description (this document); Software Requirements Specification. |
| Suggested speed | The CTC Office's speed for a block, before the wayside decides what to send. |
| Tick | One simulation step. Its length, dt, is fixed at 0.1 s (D006, D017). |
| Track circuit | The circuit of one block. It detects a train and carries the commanded speed and authority to it. |
| Truth | The `truth` branch: the team's record of normative facts (decisions D001 to D027, signals, conventions). |
| Vital | Safety-critical: must be correct and must fail to a safe state. |
| Wayside | One wayside controller of the Track Controller. It governs a contiguous run of blocks and its devices. |
| Yard | Where a line's trains enter and leave service (D022). |

Each module chapter adds the terms specific to it.

### 1.4 References

| Reference | Owner / Location | Normative? |
|-----------|------------------|------------|
| IEEE Std 1016-2009, Systems Design: Software Design Descriptions | IEEE | Structure of this document |
| Software Requirements Specification v1.0 | Team / `documents/srs-filled.md` | Yes |
| Truth store: decisions D001 to D027, signals, arbitration rules, conventions | Team / `truth/` on the `truth` branch | Yes |
| System integration design | Kevin Schillinger / `documents/system-integration-design.md` | No (how the harness was built) |
| SDD template | Team / `documents/Railway_Sim_SDD_Template.md` | Structure of Sections 1 to 4 |
| Module SDD contributions | Each owner / `documents/sdd/*.md`, `documents/Railway_Sim_SDD_Train_*.md` | Sources of Section 5 |
| Final Project deck; Deliverable Descriptions; Track Layout & Vehicle Data | Course / `documents/Project_Information/` | Yes |
| Coding standard | Team / `documents/PYTHON_STYLE_GUIDE.md` | Yes |
| UI style guide | Team / `truth/ui/style-guide.md` | Yes, for every window |

### 1.5 Document Overview

Section 2 lists the stakeholders, their concerns and the viewpoints that answer them.
Section 3 gives the system-level views and the system-wide concepts. Section 4 records the
system-wide design decisions. Section 5 holds one chapter per module, each with its use
cases, architecture, classes, interface and sequence diagrams. Section 6 holds the
appendixes: the figure register and the requirements traceability index.

**Conformance to IEEE 1016-2009.**

| IEEE 1016 content | Where |
|-------------------|-------|
| Identification: date, status, scope, organization, authorship, change history (4.2) | Cover page, Revision History, 1.2 |
| References, glossary, context (4.2) | 1.3, 1.4, 3.1 |
| Stakeholders and design concerns (4.3) | 2.1 |
| Design viewpoints (4.4) | 2.2 |
| Design views (4.5) | Section 3 (system), Section 5 (modules) |
| Design rationale (4.8) | Section 4; each module's design decisions in Section 5 |

---

## 2. Design Overview

### 2.1 Stakeholder Concerns

| Stakeholder | Concern | Addressed by |
|-------------|---------|--------------|
| Customer: Port Authority of Allegheny County | Trains never meet, never pass a stop, never exceed their commanded speed; failures end in a safe state | 3.7 (authority, vitality); 5.2, 5.3, 5.6 |
| Dispatcher | Dispatch by hand or by schedule; see occupancy, throughput and notices | 5.1 |
| Wayside programmer and maintainer | Load a territory and a PLC program per wayside; see the wayside's state | 3.7 (wayside language); 5.2, 5.3 |
| Track Builder | Load a line and inspect its blocks | 5.4 |
| Murphy | Inject and clear failures on track and trains | 5.4, 5.5 |
| Train driver and engineer | Clear Manual control; gains set once before a train moves | 5.6 |
| Passengers | Emergency brake, doors on the platform side, announcements | 5.5, 5.6 |
| Module owners | Stable, module-owned boundary types; one place where two modules' types meet | 3.3, 3.4; 4.1, 4.2, 4.5 |
| Harness integrator | One call per tick per module; the same behaviour at 1x and 10x; clear rejection | 3.4, 3.5, 3.7 (timing); 4.6 |
| Course staff | Requirements traced; the rubric's diagrams present | Section 5; 6.2 |

### 2.2 Selected Viewpoints

| IEEE 1016 viewpoint | Concerns | System view | Module views |
|---------------------|----------|-------------|--------------|
| Context | What the system and each module do, and for whom | 3.1 System context | Use case diagrams and descriptions |
| Composition | Parts and their responsibilities | 3.2 Software architecture | Module architecture (component view) |
| Logical | Classes and types | 3.3 Boundary types | Class diagrams |
| Interface | What crosses each boundary | 3.4 Harness protocol and edges | Interface sections and dictionaries |
| Interaction | How the parts cooperate over time | 3.5 Representative interaction | One sequence diagram per use case |
| Deployment (user-defined, added for the rubric) | Where each part stands along the railway and how it is linked | 3.6 Deployment | (system view only) |
| Algorithm, State dynamics | How the key decisions are computed | 3.7 System-wide concepts | CTC routing, Train Controller speed law, Track Model block states |

Omitted: Physical, Structure, Dependency, Information, Concurrency, Patterns and Resources;
concurrency is reduced to the harness's single tick (3.5).

---

## 3. Design Views

### 3.1 001-context: System Context

- **Viewpoint:** Context
- **Representation:**

![System architecture: modules, users and the information between them](../uml/system/system_architecture.png)

Commands pass down from the CTC Office through the waysides and the track to the train,
and status passes back up the same path. The Track Model also sends the signal light ahead
straight to the Train Controller, and ticket sales straight to the CTC Office. In the
running system every arrow passes through the central harness (D005).

| Module | Its users | It receives from | It sends to |
|--------|-----------|------------------|-------------|
| CTC Office | Dispatcher | Track Controller (occupancy, switches, crossings, readiness); Track Model (ticket sales) | Track Controller (suggested speed and authority, closures, maintenance switch commands); harness (clock pause and speed) |
| Track Controller SW / HW | Wayside programmer | CTC Office; Track Model (occupancy, switch read-back) | Track Model (switch, signal and crossing commands; speed and authority per track circuit); CTC Office |
| Track Model | Track Builder, Murphy | Track Controller; Train Model (position) | Track Controller; Train Model (track circuit, grade, beacon, boarding); Train Controller (signal light ahead); CTC Office (ticket sales) |
| Train Model | Passenger, Murphy | Train Controller (commands); Track Model | Train Controller (speed, brake, door, light, temperature feedback; track circuit and beacon passed through); Track Model (block and offset) |
| Train Controller SW / HW | Driver, engineer | Train Model; Track Model | Train Model (power, brakes, doors, lights, temperature, announcement) |

### 3.2 002-composition: Software Architecture

- **Viewpoint:** Composition
- **Representation:** the top-level class diagram of the whole system, in two parts.

**Part 1: harness and module processes.** One executable. Run without arguments it is the
central harness; run with `--module <name>` it is one module process. Each module process
holds its module and a `ModuleLink` to the harness.

![Software architecture, part 1: the central harness, shared utilities and the seven module processes](../uml/system/system_classes_harness.png)

**Part 2: module contracts and their implementations.** Each module owns its boundary types
and its contract (a `typing.Protocol`); each variant implements it. A HW variant's host
process holds a remote proxy, and the module's core runs on its Raspberry Pi behind
`PiLinkServer`.

![Software architecture, part 2: module contracts, implementations, remote proxies and Pi cores](../uml/system/system_classes_modules.png)

- **More information:** the parts of each module are in its chapter, under
  "architecture (component view)". Design patterns used throughout: Mediator (the harness
  maps every edge), Proxy (the HW hosts), Observer (Qt signals push snapshots to each QML
  window), and a Qt-free module core under every window.

### 3.3 003-logical: Boundary Types

- **Viewpoint:** Logical
- **Representation:**
  - **Each module owns its boundary types** and never imports another module's (D005,
    D008). The stale shared catalog `common/interfaces.py` is not used.
  - Every boundary type is a frozen dataclass or an enumeration, so a value cannot change
    after it is sent.
  - **Backend units are SI**: m, m/s, m/s², W, °C; the windows show imperial units (D002).
    Authority is a whole number of blocks (D013); commanded speed a whole number of m/s.
  - **Every reference carries its line**, since block numbers repeat across lines. A
    switch, signal or crossing is named by the block the layout lists it on.
  - Enumerated values crossing a boundary are in capitals (`conventions/naming`).
  - Speed and authority are **per block**, never per train: the waysides know which blocks
    are occupied, not which train is in them.
- **More information:** each module's boundary class diagram is in its chapter.

### 3.4 004-interface: Harness Protocol and Edges

- **Viewpoint:** Interface
- **Representation:** every module process speaks the same protocol to the harness:
  newline-delimited JSON over a local socket (`QLocalSocket`), each message carrying a
  request ID and the tick number (D005).

| Message | From | Meaning |
|---------|------|---------|
| `READY` | Module | The module is loaded and can step; names the module and the protocol version |
| `STEP` | Harness | One tick: dt, the unwrapped simulation time at the end of the step, and the module's inputs, mapped from its producers' last outputs |
| `OUTPUTS` | Module | The reply to a `STEP`: the module's outputs for that tick |
| `REJECTED` | Module | The reply to a `STEP` the module refused, with a reason; its state did not change |
| `STATE` | Module | A change made between ticks, such as the CTC Office pausing the clock |
| `CLOCK_STATE` | Harness | Paused or running, 1x or 10x, sent to the HW hosts initially and on every change |
| `SHOW` | Harness | Reopen the module's window |
| `QUIT` | Harness | End the process |

The same messages travel over USB serial to a Raspberry Pi (D027). The protocol is
`utils/harness_protocol.py`.

For each module, the modules whose outputs it reads (`PRODUCERS`, `common/harness/modules.py`):

| Consumer | Producers |
|----------|-----------|
| CTC Office | Track Controller SW, Track Controller HW, Track Model |
| Track Controller SW, HW | CTC Office, Track Model |
| Track Model | Track Controller SW, Track Controller HW, Train Model |
| Train Model | Track Model, Train Controller SW, Train Controller HW |
| Train Controller SW, HW | Train Model, Track Model |

- **More information:** the harness's edge functions are pure: one per producer and
  consumer pair, translating one module's types into the other's without changing units.
  Every field of every edge is listed in the module chapters' interface sections.

### 3.5 005-interaction: Representative Interaction, Movement Authority

- **Viewpoint:** Interaction
- **Representation:** a train is given authority, across ticks *k* to *k*+5. Each module
  steps on the inputs of its tick, which are the outputs of the tick before, so a decision
  reaches the train a few ticks after it is made.

![Representative interaction: movement authority from the CTC Office to the train, tick by tick](../uml/system/system_seq_authority.png)

- **More information:** the harness steps every module on each tick and waits for every
  reply before the next (D017). Each module's own sequence diagrams, one per use case, are
  in its chapter.

### 3.6 006-deployment: Deployment

- **Viewpoint:** Deployment (user-defined)
- **Representation:** the system as it would stand along a real railway. The CTC Office
  runs in the operations control center. A non-vital fiber network links it to the wayside
  cabinets: six on the Green Line (software Track Controller) and three on the Red Line
  (hardware Track Controller). Each cabinet is wired to the field equipment of its
  territory: track circuits, switch machines, signals and crossings. A train receives
  speed and authority only through the rails of the block it is in, and beacon data from
  transponders near stations. Its carborne controller (Train Controller) commands the
  vehicle (Train Model). Stations report ticket sales over the same network.

![Deployment: the operations control center, wayside cabinets, field equipment and a light rail vehicle](../uml/system/system_deployment.png)

- **More information:** in the simulation, one Windows 11 PC runs the harness and every
  module process. It stands in for the control center, the Green Line cabinets, the track
  and every vehicle. One Raspberry Pi 5 stands in for the three Red Line cabinets and
  another for the Red Line carborne controllers; each is linked to the PC by USB (D021,
  D027).

<!-- CONCEPTS -->

---

## 4. Decisions

The system-wide decisions, in the template's order. D-numbers are the team's decisions on
`truth`. Each module's own decisions are in its chapter.

### 4.1 Interface Contract Mechanism

- **ID:** D005: a central harness sits between the modules
- **Context:** each module needs data from others. If modules imported each other's
  structures, every pair would be coupled and one field change would break the neighbours.
- **Options:**
  - Each module defines its own boundary types and a `typing.Protocol`; the harness owns
    one pure mapping per edge.
  - A shared catalog of types every module imports (`common/interfaces.py`).
  - Modules call each other directly.
- **Outcome:** the first. The harness is the single driver of every module, one process per
  module, newline JSON. The Train Controller's Protocol is still to be added; under D005 its
  absence breaks nothing at integration.

### 4.2 Shared Boundary Data Types

- **ID:** D002, D013, D008
- **Context:** a value that crosses a boundary must mean the same to every module,
  units included.
- **Options:**
  - Frozen dataclasses per module, SI units, converted only in the display layer.
  - Mixed units chosen per module.
  - Shared types imported across modules (ruled out by D005).
- **Outcome:** the first. Authority is a block count. The stale catalog is superseded
  (D008). The Train Controller reads a validated `dict` per train today; a frozen inputs
  dataclass is its open option.

### 4.3 Contract Enforcement

- **ID:** none on record; module practice
- **Context:** an unchecked contract drifts.
- **Options:**
  - A static type check plus contract tests per module.
  - Each module's own self-test, run by hand.
  - No enforcement.
- **Outcome:** each module tests its own contract (Protocol conformance, edge
  mappings, rejection without change); the harness has its own tests of every edge. A shared
  CI job is not set up; this is an open item (4.9).

### 4.4 Stand-ins and Stub-First Development

- **ID:** D010, D018
- **Context:** each module had to run before its neighbours existed.
- **Options:**
  - A stub at the real import path from day one.
  - The real module, with a separate test UI standing in for its neighbours.
  - No stand-ins; integrate only when every module is real.
- **Outcome:** the second. Every module has a test UI in a separate process that reaches it
  only through its public boundary. The harness can also run any module as a stub
  (`common/harness/stub_module.py`). The test UIs stay for the whole project; the harness
  never starts them (D005).

### 4.5 Contracts Ownership

- **ID:** D005
- **Context:** the boundary types are what other modules depend on.
- **Options:**
  - Each module owns its types; only the harness's edge functions know two modules' types.
  - One shared contracts package with one owner.
- **Outcome:** the first. A module with two variants has one contract shard on `truth`
  with a single named owner, and one shard per variant; the Track Controller contract is
  owned by Harry Tye.

### 4.6 External Input Validation

- **ID:** none on record; REQ-NFR-003, REQ-NFR-004
- **Context:** inputs come from other modules, from windows and from files. A wrong value
  must not corrupt state.
- **Options:**
  - Check the whole tick first and reject it whole, so nothing changes.
  - Check each value as it is used and keep the valid part.
  - Trust the caller.
- **Outcome:** the first, at every module's boundary. The one deliberate exception is the
  Train Model's process adapter, which rejects a bad train's inputs and still steps the
  other trains (5.5).

### 4.7 Knowledge Capture and Decision Logging

- **ID:** `AGENTS.md`: the `truth` branch is the record of decisions
- **Context:** the reasons for design choices get lost between work packages.
- **Options:**
  - A `truth` branch of normative facts, one file per entry, changed only by proposals a
    person promotes.
  - Decisions only in chat and issue comments.
- **Outcome:** the first. Status (what is built, what is stubbed) is read from the
  repository, never written into truth.

### 4.8 Rejected Tooling: Summary Table

| Tool or approach | Why it was rejected |
|------------------|---------------------|
| `common/interfaces.py` shared catalog | Stale: authority in metres, failures reported by the Train Model; superseded (D008) |
| Direct imports between modules | Couples every pair of modules; replaced by the harness's edge mappings (D005) |
| One process for the whole system | A module's window or fault would stall the others; one process per module instead (D005) |
| A fixed COM port number for the Pis | Changes between PCs; the Pis are found by their USB product name (D027) |
| A variable time step | 1x and 10x would give different results; dt is fixed at 0.1 s (D006, D017) |

### 4.9 Open Items: Not Yet Decided

| Item | Owner |
|------|-------|
| The read-only vital PLC block: whether every wayside runs a fixed generated block after the user's program; the SW variant's Python supervisor to be moved into PLC code | Harry Tye |
| One PLC language, identical names in both Track Controller variants (the SW variant keeps `MAINT`) | Harry Tye, Braden Bosilovich |
| The Red Line's three wayside territories (proposed in 3.7) | Braden Bosilovich |
| Powering a Raspberry Pi 5 through the USB-C port that carries the link | Braden Bosilovich, Jonathan Tsang, Ivan Zheng |
| A 10x tick on a HW variant: USB round trip plus scan under 10 ms | Braden Bosilovich, Jonathan Tsang, Ivan Zheng |
| The Train Controller's Protocol and typed inputs (4.1, 4.2) | Jonathan Tsang, Ivan Zheng |
| A shared CI job for every module's contract tests (4.3) | Team |
| Spelling of the fourth signal aspect: `SUPER_GREEN` on truth, `SUPER GREEN` in the Train Controller | Deni Ephraim, Jonathan Tsang |

Each module's own open items are at the end of its chapter.

---

<!-- MODULES -->

---

<!-- APPENDIXES -->

---

*End of document.*
