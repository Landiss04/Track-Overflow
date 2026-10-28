# Software Design Description
## For the Railway Simulation Project - Train Model Contribution

Version: 0.2 - Train Model draft  
Prepared by: Kevin Schillinger  
Organization: Track Overflow, Team 3, ECE 1140  
Date Modified: 2026-10-20

This is a separate, completed Train Model contribution based on
`Railway_Sim_SDD_Template.md` on `development`. The template is unchanged.
Other modules appear only where needed to explain Train Model interfaces.
Diagram insertion points are intentional: insert the author's existing diagrams.
Version 0.2 incorporates Kevin Schillinger's review decisions of October 20, 2026.
It specifies the intended design; the product changes and related documentation
updates remain deferred to the three prompts provided in the accompanying chat. No product
code, tests, other existing documents, or promoted truth entries were changed
for this revision.

## Table of Contents

- [1. Introduction](#1-introduction)
  - [1.1 Document Purpose](#11-document-purpose)
  - [1.2 Subject Scope](#12-subject-scope)
  - [1.3 Definitions, Acronyms, and Abbreviations](#13-definitions-acronyms-and-abbreviations)
  - [1.4 References](#14-references)
  - [1.5 Document Overview](#15-document-overview)
- [2. Design Overview](#2-design-overview)
  - [2.1 Stakeholder Concerns](#21-stakeholder-concerns)
  - [2.2 Selected Viewpoints](#22-selected-viewpoints)
- [3. Design Views](#3-design-views)
  - [001-context - System Context](#001-context---system-context)
  - [002-composition - Module Composition](#002-composition---module-composition)
  - [003-logical - Shared Boundary Types](#003-logical---shared-boundary-types)
  - [004-interface - Module Interface Contracts](#004-interface---module-interface-contracts)
  - [005-interaction - Representative Interaction: Train Motion Tick](#005-interaction---representative-interaction-train-motion-tick)
  - [006-use-cases - Actors and Use Case Descriptions](#006-use-cases---actors-and-use-case-descriptions)
  - [007-deployment - Train Model Deployment](#007-deployment---train-model-deployment)
- [4. Decisions](#4-decisions)
  - [4.1 Interface Contract Mechanism](#41-interface-contract-mechanism)
  - [4.2 Shared Boundary Data Types](#42-shared-boundary-data-types)
  - [4.3 Contract Verification](#43-contract-verification)
  - [4.4 Stub-First Development](#44-stub-first-development)
  - [4.5 Contracts Package Ownership](#45-contracts-package-ownership)
  - [4.6 External Input Validation](#46-external-input-validation)
  - [4.7 Knowledge Capture and Decision Logging](#47-knowledge-capture-and-decision-logging)
  - [4.8 Rejected Tooling - Summary Table](#48-rejected-tooling---summary-table)
  - [4.9 Resolved Review Items and Deferred Work](#49-resolved-review-items-and-deferred-work)
- [5. Appendixes](#5-appendixes)
  - [A. Requirements Traceability](#a-requirements-traceability)
  - [B. Rubric Coverage](#b-rubric-coverage)
  - [C. Diagram Insertion Register](#c-diagram-insertion-register)
  - [D. Verification References](#d-verification-references)

## Revision History

| Name | Date | Reason For Changes | Version |
|------|------|--------------------|---------|
| Kevin Schillinger | 2026-10-20 | Train Model contribution using the development SDD template, course rubrics, CTC design reference, promoted decisions, and repository evidence; existing diagrams reserved for insertion. | 0.1 |
| Kevin Schillinger | 2026-10-20 | Incorporated review decisions, removed the testing actor, clarified developer utilities, and separated deferred UI/backend/documentation work. | 0.2 |

---

## 1. Introduction

### 1.1 Document Purpose

This Software Design Description explains how the Train Model converts Train
Controller commands and Track Model data into simulated motion, passenger load,
and onboard equipment state. It documents Kevin Schillinger's Train Model
contribution for incorporation into the Railway Simulation group SDD.

The intended readers are module and integration developers and the course
reviewers. The document connects requirements to responsibilities,
boundary types, use cases, deployment, and verification evidence. It describes
both the integrated design and the separate test setup used to exercise the
module before integration.

### 1.2 Subject Scope

The Railway Simulation has five functional modules: CTC Office, Track Controller,
Track Model, Train Model, and Train Controller. The Track Controller and Train
Controller have hardware and software variants. The Train Model is software,
owned by Kevin Schillinger. Moving Block Overlay and the operational Blue Line
are outside system scope under D001 and D023. The Blue Line remains a standalone
Train Model test fixture under D010.

The Train Model contribution covers:

- Longitudinal motion under power, grade, rolling resistance, and braking.
- A fixed five-module Bombardier FLEXITY 2 consist, with one physical state per train.
- Passenger boarding, disembarking, capacity, and their effect on operating mass.
- Door and light states, cabin temperature, and announcement presentation.
- Passenger emergency brake activation and Train Controller release.
- Engine, signal pickup, and service brake failure injection.
- The module window, fleet selection, boundary types, process adapter, and removable test UI.

Routing, authority allocation, dispatch, occupancy calculation, speed control,
station stopping, and control interlocks are responsibilities of the other
modules. The Train Model applies commands and reports physical consequences.
Its configured maximum speed is vehicle data; it is not a speed governor (D009).

### 1.3 Definitions, Acronyms, and Abbreviations

| Term | Definition |
|------|------------|
| API | Application Programming Interface. |
| Authority | Nonnegative integer count of blocks ahead of the current block that a train may enter; zero requires stopping before leaving the current block (D013). |
| Beacon | Station information received near a station: station name, platform side, and underground flag. |
| CTC | Centralized Traffic Control Office, responsible for dispatch and route suggestions. |
| dt / tick | Simulated duration of one external step; normally 0.1 s, fixed during a run. |
| Fleet | The collection of individual Train Model states, indexed by opaque train ID. |
| Harness | Integration infrastructure that owns the clock, starts module processes, maps interfaces, and routes messages. |
| Murphy | The user who injects simulated failures. |
| Protocol | A Python `typing.Protocol` describing a structural interface. |
| Reference mass | Fixed two-thirds-load mass used to derive traction and braking force limits. |
| Operating mass | Empty vehicle mass plus crew and passengers; used in the force balance. |
| SDD / SRS | Software Design Description / Software Requirements Specification. |
| Snapshot | Full observable state for the module's own window; distinct from cross-module outputs. |
| Stub | A stand-in producer or module used to exercise an interface before integration. |

### 1.4 References

| Reference | Owner / Location | Role and authority |
|-----------|------------------|--------------------|
| R1. Railway Simulation SDD template | `documents/Railway_Sim_SDD_Template.md` on `origin/development`, commit `de7a98f` | Document structure; read directly from the branch. |
| R2. Promoted repository facts | `origin/truth`, commit `84c7d44`: Train Model shard; conventions for units, files/paths and toolchain; D005, D006, D008, D009, D010, D017; relevant signals and arbitration | Authoritative decisions and contracts. Read through Git; local inbox proposals are not facts. |
| R3. Software requirements | [srs-filled.md](srs-filled.md), especially sections 3.1, 3.2.5, 3.3, and 4 | Requirement IDs and verification methods; later promoted decisions govern documented changes. |
| R4. Course rubrics | [Rubric image index](rubrics/detailed-png/README.md) and the eleven images it lists; [requirements mapping](rubrics/rubric-to-requirements-map.md) | Deliverable criteria. Direct image review governs over stale mapping notes. |
| R5. CTC Office: System Architecture & Design | Landis, October 16, 2026; supplied `CTC_Office_Design.pdf`, `/home/kevin/Downloads/CTC_Office_Design.pdf` | Reference for organization, architecture topics, use case format, and peer-module context. Its older integration statements do not override R2. |
| R6. Train Model documentation | [Physics](../TrainModel/docs/physics.md), [module interface](../TrainModel/docs/module-interface.md), [integration](../TrainModel/docs/integration.md), [README](../TrainModel/README.md) | Detailed design and implementation explanations, checked against current code and R2. |
| R7. Train Model implementation | [interface.py](../TrainModel/train_model/interface.py), [model.py](../TrainModel/train_model/model.py), [state.py](../TrainModel/train_model/state.py), [fleet.py](../TrainModel/train_model/fleet.py), [module_process.py](../TrainModel/train_model/module_process.py), [wire.py](../TrainModel/train_model/wire.py) | Evidence of current behavior at working-tree baseline `a7f568b`; code is not a source of new normative decisions. |
| R8. Integration design and mappings | [system-integration-design.md](system-integration-design.md), [train_edges.py](../common/harness/train_edges.py) | Integration context and implemented edge mappings. |
| R9. Existing UML source | [train-model.mdj](../TrainModel/docs/diagrams/train-model.mdj), [diagram brief](../TrainModel/docs/uml-diagram-brief.md), [draw.io brief](../TrainModel/docs/uml-drawio-prompt.md) | Existing diagram material for author insertion; older diagram descriptions need the checks in Appendix C. |
| R10. SDD review resolutions | Kevin Schillinger, direct replies in this conversation, 2026-10-20; beacon encoding selected at his request | Source of the revised intended design. Where this supersedes older promoted text, the follow-up documentation prompt calls for proposals and human promotion. |

### 1.5 Document Overview

Section 2 identifies stakeholder concerns and the selected viewpoints. Section 3
describes system context, composition, data, interfaces, a simulation tick, use
cases, and deployment. Section 4 records the applicable decisions and unresolved
differences. Section 5 maps the contribution to requirements, grading criteria,
existing diagrams, and test sources. The latest review resolutions are listed
separately from remaining implementation work in section 4.9.

The template's movement-authority-request example is replaced with a Train Model
motion tick. Deployment and use case views are added because the rubric explicitly
requires them. The template's shared-types heading is retained, but the design
uses module-owned types and harness mappings under D005 and D008.

---

## 2. Design Overview

### 2.1 Stakeholder Concerns

| Stakeholder | Concern | Addressed By |
|-------------|---------|--------------|
| Passenger | Emergency brake response, doors, announcements, and cabin conditions. | UC-TM-03 through UC-TM-06; failure behavior. |
| Murphy | Independent, composable fault injection and visible effects on the selected train. | UC-TM-07; Train Model window. |
| Observer / reviewer | Understandable motion, dimensions, mass, occupancy of the cabin, and equipment readouts. | UC-TM-02; UI snapshot and display units. |
| Train Controller developer | Typed commands, predictable physical response, brake feedback, and speed/signal data. | Interface dictionaries and tick ordering. |
| Track Model developer | Grade and circuit inputs; position, block changes, and available capacity outputs. | Track dictionaries and UC-TM-04/05. |
| Integration developer | Fixed timing, train identity, process lifecycle, and isolated train rejection. | Composition, interaction, and deployment views. |
| Module developer | Repeatable inputs, removable stand-ins, and rejection without partial physical updates. This is a development concern, not a product actor. | Developer Test Utility; validation; Appendix D. |

### 2.2 Selected Viewpoints

| Template viewpoint | Application in this contribution |
|--------------------|----------------------------------|
| 2.2.1 Context | Train Model responsibilities, external producers/consumers, route and authority context, timing, and vitality boundaries. |
| 2.2.2 Composition | Physics, Qt wrapper, fleet, process adapter, QML window, and test scaffolding. |
| 2.2.3 Logical | Immutable dataclasses, configuration, model state, and class relationships. |
| 2.2.6 Interface | Complete Train Model input/output dictionaries, validation, and signal semantics. |
| 2.2.7 Interaction | One accepted/rejected tick and actor-oriented use case descriptions. |
| Added: Deployment | Host processes, local transport, test arrangement, and integrated lifecycle. |

Algorithm and state behavior are explained within the logical and interaction
views. Separate physical railway, database, and hardware resource views belong to
the relevant module owners. Diagram placeholders are listed in Appendix C.

---

## 3. Design Views

### 001-context - System Context

**Viewpoint:** Context.  
**Representation:** Module boundary description and system context diagram.

The CTC Office dispatches trains and suggests routes, speed, and authority to the
Track Controller. Trackside logic supplies the resulting commanded speed and
authority through the Track Model's circuit data. The Train Model receives those
values and passes them to the Train Controller. The Train Controller computes
power and equipment commands; the Train Model returns actual motion and equipment
state. All integrated exchanges pass through harness mappings (D005).

| Architecture topic from rubric | Train Model contribution |
|--------------------------------|--------------------------|
| Route | Receives current block and terrain; integrates signed offset. Route selection, switch traversal, and occupancy belong outside the Train Model. A polarity transition identifies a block change. |
| Authority | Passes `authority_blocks` to the Train Controller. It does not allocate authority or brake merely because authority is zero. CTC suggested speed and downstream commanded speed are distinct. |
| Wayside distribution | Has no wayside database or territory logic. The Track Model supplies the terrain and circuit input for each train, independent of the upstream hardware/software implementation. |
| Timing | The harness supplies fixed dt and simulation time on each rising edge. Default dt is 0.1 s; 1x/10x changes tick frequency, and pause stops ticks (D006, D017). |
| Vitality | Train Controller and Track Controller contain the vital control responsibilities. The Train Model simulates the plant and failures; this document makes no safety certification claim for it. Communications channels are non-vital under REQ-INTF-021. |

The integrated clock starts at 05:00:00 and sends unwrapped simulation seconds.
At 1x, the default is 10 ticks per real second; at 10x, it is 100. The harness
waits for module replies before issuing the next tick. Consumers receive the
previous tick's producer outputs, so module execution order does not change the
input snapshot for a tick. The Train Model does not own a timer that advances physics.

The window displays the harness-supplied time of day during integrated operation.
The module also keeps an independent estimate derived from each train's accepted
elapsed steps. Every 15 harness ticks it compares that estimate with the supplied
unwrapped simulation time. A train's initial epoch accounts for its creation time,
so a late-created train does not appear to have drifted simply because its elapsed
time starts at zero. Display reconciliation never overwrites elapsed physics time
or silently clears a drift discrepancy. The backend/UI work is deferred.

**Figure TM-1. Train Model system context.**

> **DIAGRAM PLACEHOLDER TM-1:** Insert the existing architecture/context diagram.
> Label the Train Controller and Track Model boundary exchanges and the harness's
> clock and mappings. Show CTC/waysides only as upstream context, outside the
> Train Model boundary.

### 002-composition - Module Composition

**Viewpoint:** Composition.  
**Representation:** Responsibility and source-file decomposition.

The five system modules retain separate ownership. The CTC Office owns dispatch
and routing suggestions; the Track Controller owns wayside control; the Track
Model owns railway state; the Train Controller owns onboard control; the Train
Model owns physical response. This section details only the Train Model.

| Part | Responsibility | Source |
|------|----------------|--------|
| Boundary contract | Frozen input, output, snapshot, and configuration dataclasses; structural model protocol. | `train_model/interface.py` |
| Physics core | Input validation, force balance, integration, passengers, block-change detection, cabin temperature, and output construction. Has no Qt dependency. | `train_model/model.py` |
| Qt state wrapper | Owns one physical model; exposes snapshot properties and change signals; receives selected-train UI actions. | `train_model/state.py` |
| Fleet | Owns one state per train ID; adds/removes trains and exposes the selected train to QML. | `train_model/fleet.py` |
| Process adapter | Connects to the harness, follows its roster, decodes each train's inputs, steps valid trains, and returns outputs/rejections. | `train_model/module_process.py` |
| Wire conversion | Converts nested JSON objects to module types and outputs back to plain values. | `train_model/wire.py` |
| Main window | Readouts, train selector, passenger brake, failure buttons, and announcement popup. | `ui/Main.qml`, `ui/MainView.qml` |
| Bootstrap | Creates the Qt application, QML engine, theme, and context objects. | `train_model/app.py`, `main.py` |
| Test setup | Separate test UI, local socket link, track stand-in, speed limiter, and test clock driver; removed at integration under D010. | `test_ui.py`, `train_model/harness.py`, `link.py`, `track_stub.py`, `speed_limiter.py`, `ui/TestMain.qml`, `ui/TestView.qml` |

Paths in this table are relative to `TrainModel/`. The production harness transport
uses shared `utils/module_link.py`; it is distinct from the removable test link.

One Train Model process holds the fleet; there is no process per train. Each train
has independent motion, passengers, cabin state, failures, and random generator.
The fleet derives a repeatable seed from its train ID unless a configuration is
provided. Selecting a train changes the window binding, not which trains step.
With no trains the window uses an idle state that is never stepped.

The process adapter validates and steps trains separately. A bad input for one
train holds that train's physical state and returns its last outputs while the
other trains advance. The `TrainModelFleet.step_all` helper instead validates the
whole fleet before advancing any train; the process adapter does not use that
helper for integrated stepping.

**Figure TM-2. Train Model software composition.**

> **DIAGRAM PLACEHOLDER TM-2:** Insert the existing software architecture diagram
> showing the physics core, state wrapper, fleet, process adapter, QML window,
> and separately marked test scaffolding.

### 003-logical - Shared Boundary Types

**Viewpoint:** Logical.  
**Representation:** Class model, configuration, and physical state relationships.

Boundary types are shared between the Train Model's own layers. Other modules
define their own types; the harness maps between them. The module does not import
the stale `common/interfaces.py` catalog (D008).

| Type / class | Main relationships and purpose |
|--------------|--------------------------------|
| `TrainConfig` | Frozen primitives and derived force/mass properties; referenced by the physical model. |
| `TrainModelInputs` | Contains one `ControllerCommands` and one `TrackInputs`. |
| `TrackInputs` | Contains `TrackInfo`, `TrackSignal`, optional `Beacon`, and a boarding count. |
| `TrainModelOutputs` | Contains one `ControllerOutputs` and one `TrackOutputs`. |
| `TrainModelSnapshot` | Full UI observation, including failures, passengers, mass, acceleration, elapsed time, last inputs, and outputs. |
| `interface.TrainModel` | Protocol defining `step`, `snapshot`, failure injection, and passenger-brake operations, including a test-only clear hook. |
| `model.TrainModel` | Implements the physical behavior; owns mutable physical state and a per-train random generator. |
| `TrainModelState` | QObject owning one model and publishing `snapshotChanged`, `failuresChanged`, and `runningChanged`. |
| `TrainModelFleet` | QObject holding zero or more states by ID, plus selected/idle state for the window. |
| `TrainModelProcess` | Holds the fleet and a harness `ModuleLink`; orchestrates roster and individual train steps. |

**Figure TM-3. Train Model class diagram.**

> **DIAGRAM PLACEHOLDER TM-3:** Insert the existing class diagram. Keep the
> protocol and concrete `TrainModel` distinguishable by package name. Mark frozen
> dataclasses, Qt objects, multiplicities, and test-only classes. Check whether
> the existing drawing includes the newer fleet/process adapter before
> insertion, and that it shows no `passenger_brake_release` field (withdrawn
> 2026-10-28).

#### Vehicle configuration and mass

| Parameter | Default value / derivation | Qualification |
|-----------|----------------------------|---------------|
| Vehicle | Bombardier FLEXITY 2, fixed five-module consist | Train Model contract, R2. |
| Length / width / height | 32.2 m / 2.65 m / 3.42 m | Vehicle data recorded in R2. |
| Empty / datasheet loaded mass | 40,900 kg / 56,700 kg | Loaded figure is the datasheet reference load. |
| Crew / passenger capacity | 5 / 222 | Passenger capacity excludes crew. |
| Mass per person | 77.1107 kg | Applies to crew and passengers. |
| Maximum power | 480,000 W | Confirmed by Kevin Schillinger in R10. |
| Vehicle maximum speed | 70/3.6 m/s | Recorded, not enforced by this module. |
| Reference mass | `40,900 + (2/3)*(56,700 - 40,900)` = approximately 51,433 kg | Used to derive the fixed force limits. |
| Traction limit | `m_ref * 0.5` = approximately 25,717 N | Derived from rated reference-load acceleration. |
| Service brake force | `m_ref * 1.2` = 61,720 N | Fixed force; actual deceleration varies with operating mass. |
| Emergency brake force | `m_ref * 2.73` = 140,413 N | Same reference-load basis. |
| Rolling coefficient / gravity | 0.002 / 9.81 m/s² | Current configured values; rolling resistance is the only passive resistance term in scope. |

Operating mass is `m_empty + (n_crew + n_passengers) * passenger_mass`.
It ranges from approximately 41,286 kg with crew only to 58,404 kg at passenger
capacity. The datasheet's loaded mass sizes the reference forces; it is not a
clamp on operating mass.

#### Motion and equipment behavior

Positive velocity is forward and positive grade is uphill in that direction.
For moving trains, the force balance is:

```text
P_effective = min(power_cmd_w, p_max_w), or 0 under engine failure
F_traction = min(P_effective / abs(v), F_max) when v != 0
F_traction = F_max when v == 0 and P_effective > 0, otherwise 0
F_grade = m * g * sin(grade_deg * pi / 180)
F_roll = C_rr * m * g * cos(grade_deg * pi / 180)
F_net = F_traction - F_grade - sign(v) * (F_brake + F_roll)
a = F_net / m
```

Traction acts forward during rollback as well. At rest, brakes and rolling
resistance act as holding forces. A sufficiently steep grade can produce
rollback; a brake stops motion without itself reversing the train. Applying
power while braking remains physically meaningful: the Train Controller owns
the traction cut decision.

The implementation uses exact constant-force segments and midpoint evaluation
in the power-limited regime, with internal event/substep boundaries at stops
and traction-regime changes. Position uses the average of segment endpoint
velocities. Kevin has approved keeping this algorithm. Internal segments allow
accurate handling of stopping and traction-regime transitions, while evaluating
power-limited traction at midpoint velocity preserves the commanded work over
each segment and avoids artificial energy gain. The external step still advances
exactly dt at either simulation speed. D006 must be updated through the follow-up
documentation work to explain these reasons and remove its no-substep statement.

Cabin temperature begins at 20 °C and approaches the commanded setpoint using
`T_next = T_set + (T - T_set) * exp(-dt/300)`. Doors and lights follow controller
commands. The Train Controller is responsible for keeping doors closed when necessary;
the Train Model does not impose a door-speed interlock. Rolling resistance is
the only passive resistance term modeled. Grade remains a gravitational force
and braking remains a commanded force; aerodynamic drag, wheel slip, and brake
build-up are outside the selected model.

Service and emergency brakes may be engaged simultaneously. The intended brake
states are independent: emergency follows the controller command or passenger
latch, and service follows its command unless service brake failure is active.
Both engaged brakes contribute their configured forces to the total brake force.
This force-combination rule is the physical implementation selected for the
simultaneous-application decision. Current code still suppresses service when
emergency is active; the backend prompt specifies the required change.

Passengers board only when stopped with a door open, capped by remaining
capacity. Once per stop, the first eligible open-door tick draws a uniform
disembark count from zero through the number aboard. Reopening a door does not
draw again until the train moves and begins another stop. The Track Model owns
the station restriction and sends boarding events only at stations. The Train
Model checks rest, open doors, valid counts, and remaining capacity; it does not
add a station-presence gate. Boarding changes operating mass before that tick's
motion is integrated.

### 004-interface - Module Interface Contracts

**Viewpoint:** Interface.  
**Representation:** Module-owned typed contract and signal dictionaries.

The physical entry point is `step(dt, TrainModelInputs) -> TrainModelOutputs`.
`snapshot()` observes full module UI state without advancing time. Failure
injection and a passenger pull are local UI actions, not fields sent by another
module. The normal passenger-release command is a controller input.

#### Train Controller to Train Model: `ControllerCommands`

| Field | Type / backend unit | Meaning |
|-------|---------------------|---------|
| `power_cmd_w` | finite float, W, >= 0 | Requested traction power, saturated at the configured physical power limit. |
| `service_brake` | bool | Apply service brake unless service brake failure is active; emergency braking does not suppress it in the intended design. |
| `emergency_brake` | bool | Controller emergency-brake command, separate from the passenger latch. |
| `interior_lights`, `exterior_lights` | bool each | Requested equipment states. |
| `door_left_open`, `door_right_open` | bool each | Requested door states. |
| `temp_setpoint_c` | finite float, °C | Cabin temperature target. |
| `announcement` | str | Passenger announcement text. |

#### Track Model to Train Model: `TrackInputs`

| Field | Type / backend unit | Meaning |
|-------|---------------------|---------|
| `track_info.block_id` | str | Current block identifier. |
| `track_info.grade_deg` | finite float, degrees, strictly between -90 and 90 | Positive uphill; source layout grade percent is converted upstream. |
| `track_info.elevation_m` | finite float, m | Terrain metadata. |
| `track_info.speed_limit_mps` | finite float, m/s, >= 0 | Block limit passed through in model outputs. |
| `track_info.polarity` | bool | Flip on block entry; a change resets offset and raises the block-change event. |
| `track_info.station_name` | str or `None` | Station in the current block; implementation uses `None` off-station. |
| `track_signal.commanded_speed_mps` | finite float, m/s, >= 0 | Track-circuit commanded speed passed to the controller. |
| `track_signal.authority_blocks` | int, 0 through 2³¹ - 1 | Remaining authority in blocks. |
| `beacon` | `Beacon` or `None` | `station_name: str`, `platform_side: L/R/LR`, `underground: bool`. The entire canonical beacon payload must fit 128 characters; the encoding below replaces the current station-name-only check. |
| `passengers_boarded` | int, 0 through 2³¹ - 1 | Event count; zero otherwise. Replaying a nonzero count can board more passengers on later ticks. |

#### Train Model to Train Controller: `ControllerOutputs`

| Field | Type / backend unit | Meaning |
|-------|---------------------|---------|
| `actual_speed_mps` | float, m/s | Signed physical velocity, including rollback. |
| `emergency_brake_active`, `service_brake_active` | bool each | Independent engaged states; both may be true. Current precedence behavior requires the deferred backend change. |
| `door_left_open`, `door_right_open` | bool each | Actual simulated door states. |
| `interior_lights_on`, `exterior_lights_on` | bool each | Actual simulated light states. |
| `cabin_temp_c` | float, °C | Simulated cabin temperature. |
| `commanded_speed_mps`, `authority_blocks` | float m/s or null; int blocks or null | Track-signal pass-through; both become null under signal pickup failure, invalid data rather than a valid 0 (Kevin Schillinger 2026-10-28; zero before, R10). |
| `speed_limit_mps` | float, m/s | Block speed limit, unaffected by pickup failure. The current controller edge drops this field because that consumer has no separate speed-limit input. |
| `beacon` | `Beacon` or `None` | Current tick's beacon; the consumer retains station information if needed. |

Failure flags are available to the Train Model window through its snapshot.
They are not sent to the Train Controller. The controller must observe physical
response and feedback rather than receive Murphy's fault flags.

#### Train Model to Track Model: `TrackOutputs`

| Field | Type / backend unit | Meaning |
|-------|---------------------|---------|
| `block_id` | str | Current block, supplied by Track Info. |
| `offset_m` | float, m | Signed integrated offset of the train's front since the last polarity transition. |
| `actual_speed_mps` | float, m/s | Same physical speed reported to the controller. |
| `block_changed` | bool | True only on the polarity-transition tick; the first polarity sample is not a change. |
| `passenger_capacity` | int, persons | Free passenger spaces after this tick's exchange. |

The UI snapshot additionally contains mass, acceleration, crew and passenger
counts, passenger latch, failures, last inputs, and elapsed model time. These
are not automatically cross-module signals.

#### Beacon payload encoding

The chosen logical beacon payload is a compact JSON array in fixed order:
`[station_name, platform_side, underground]`, for example
`["Central","LR",false]`. Canonical serialization uses ASCII escapes for
non-ASCII text (`ensure_ascii=True`) and no optional whitespace
(`separators=(",", ":")`). All JSON syntax, quotes, brackets, commas, and escape
characters count toward the 128-character limit. ASCII output makes character
count equal to encoded byte count. Invalid or overlength beacons are rejected
before state mutation; names are never silently truncated.

Existing typed `Beacon` objects and named fields in harness JSON envelopes remain
the readable module boundary. Canonical array encoding defines the bounded beacon
payload, not a replacement for the entire harness protocol. Producers and the
Train Model must enforce the same rule. `None` remains the output between beacon
ticks; the Train Controller retains the last beacon if its control logic needs it.
This encoding is specified here for follow-up implementation and documentation.

#### Validation and units

Validation occurs before any physical state, elapsed time, or random-generator
state changes. Invalid dt raises `InvalidTimeStepError`; invalid inputs raise
`InvalidInputError`, both within the `TrainModelError` hierarchy. dt must be finite,
positive, and at most 60 s; accepting that range defensively does not authorize
varying dt during a run. Flags must be actual booleans; counts must be integers
and cannot be booleans. Numbers must be finite, and text fields must be strings.
Malformed nested objects are rejected during wire decoding.

State and interface payloads use backend units. QML converts speed to mph,
distance/dimensions to ft, acceleration to ft/s², mass to short tons, and cabin
temperature to °F. Power displays in kW. Authority remains a count of blocks.
The Power command readout is a command, not measured energy consumption.

### 005-interaction - Representative Interaction: Train Motion Tick

**Viewpoint:** Interaction.  
**Representation:** Ordered step description and sequence-diagram insertion point.

**Preconditions:** The module is ready, the harness has a roster, and previous
producer outputs are available. A newly introduced train receives inert commands
until its Train Controller supplies commands.

1. The harness maps the preceding producer outputs into each train's controller
   and track inputs and sends a `STEP` with request ID, tick, dt, and simulation time.
2. `TrainModelProcess` follows the roster: it adds newly named trains and removes
   trains no longer named. Train ID and line are fleet metadata.
3. For each train, the adapter decodes its nested objects and validates the step.
4. For an accepted train, the model clears the passenger latch if the one-shot
   release command is true, then applies doors and passenger exchange using
   velocity at the start of the tick.
5. It detects a polarity transition, resetting block offset if necessary,
   integrates forces over dt, ends the passenger stop once moving, and updates
   cabin temperature.
6. It saves the accepted inputs, advances elapsed time using compensated
   summation, constructs outputs, and refreshes the Qt snapshot.
7. The adapter encodes each train's outputs in a `trains` object. Rejected trains
   retain their previous physical outputs and are named in a `rejected` object.
8. The module reconciles the displayed clock with the supplied harness time,
   independently checks per-train elapsed time for drift every 15 harness ticks,
   and publishes clock diagnostics without modifying physics time. This is deferred
   backend work specified by this design.
9. The harness receives the reply, logs rejections, and supplies the outputs to
   consumers on the following tick. The window observes Qt change signals.

If the top-level `trains` object is missing, the adapter rejects the module tick.
If one train's decoded inputs are invalid, the other trains still advance. The
roster update occurs before per-train validation; rejection preserves a train's
physical step, not an all-or-nothing roster transaction.

An action performed between ticks updates local model outputs and its window
immediately. In the integrated system other modules receive that change through
the next harness exchange. Physics advances only on an accepted step. The
standalone test link can publish changed outputs immediately even while paused.

**Figure TM-4. One accepted or rejected Train Model tick.**

> **DIAGRAM PLACEHOLDER TM-4:** Insert the existing simulation-step sequence
> diagram. Identify whether it depicts the standalone test path or integrated
> harness path. Include validation/rejection, physical update, output return,
> and UI notification. Do not label a standalone socket sequence as integrated.

### 006-use-cases - Actors and Use Case Descriptions

**Viewpoint:** Interaction / use cases.  
**Representation:** Actor inventory and use case narratives following the CTC
reference's preconditions, trigger, success scenario, and alternate-flow format.

| Actor | Role |
|-------|------|
| Passenger | Pulls the emergency brake and receives announcements; participates in simulated boarding/alighting. |
| Murphy | Injects and clears selected-train failures through the module window. |
| Observer | Views state and selects a train. |
| Train Controller | Supplies onboard commands, receives feedback, and releases a passenger pull. |
| Track Model | Supplies terrain, circuit, beacon and boarding data; consumes position and capacity. |
| Harness / simulation clock | Supplies fixed-duration ticks, routes boundary data, and manages the integrated roster. |

The train driver acts through the Train Controller, rather than through direct
speed or brake-command controls on the Train Model window. The developer test UI
is a utility outside this product actor model; it is not a use case actor, and
its operations are not product use cases.

**Figure TM-5. Train Model use case diagram.**

> **DIAGRAM PLACEHOLDER TM-5:** Insert the existing use case diagram with actors
> visible and the Train Model subject boundary labeled. Exclude the testing role
> and developer utility operations. Use UC-TM IDs below as caption cross-references.

#### UC-TM-01: Advance physical motion

**Primary actor:** Harness / simulation clock. **Supporting actors:** Train
Controller and Track Model. **Requirements:** REQ-FUNC-039, REQ-INTF-013.

**Preconditions:** A train exists and has valid controller and track inputs.
**Trigger:** A fixed-duration tick arrives.

**Main success scenario:** Validate inputs; determine operating mass and active
forces; integrate signed motion; update temperature and elapsed time; return
controller and track outputs. The window refreshes the train's readouts.

**Alternate flows:** Invalid input rejects that train's step without changing its
physical state. Engine failure removes traction. A grade may hold the train or
cause rollback. Pause produces no new physical step.

**Postcondition:** Accepted outputs describe the end of the tick.

#### UC-TM-02: View and select a train

**Primary actor:** Observer. **Requirements:** REQ-FUNC-040.1 through 040.6,
REQ-FUNC-041.1/041.2, REQ-INTF-001.3.

**Preconditions:** The module window is open. **Trigger:** A train is selected or
its state changes.

**Main success scenario:** Select a fleet entry; bind to its state; display
dimensions, operating mass, acceleration, speed, crew/passenger counts, power
command, doors, brakes, lights, cabin temperature, position, and station data.
Convert values only for display.

**Alternate flows:** An empty fleet displays the idle state. Removing the selected
train selects another remaining entry. Arrival time is omitted from the intended
window; station name and platform-side information remain. Selecting an unknown
ID is ignored.

**Postcondition:** The window observes the selected train; every active train
continues to be stepped independently.

#### UC-TM-03: Apply onboard equipment commands

**Primary actor:** Train Controller. **Supporting actor:** Passenger.
**Requirements:** REQ-FUNC-043, 044, 045.

**Preconditions:** Valid equipment commands are available. **Trigger:** A tick
contains new or held door, light, temperature, or announcement commands.

**Main success scenario:** Apply door and light states; move cabin temperature
toward the target; report resulting states; show each new announcement in a
passenger popup.

**Alternate flows:** Invalid flags or values reject the step. The Train Model
follows door commands at any speed; the Train Controller owns the door interlock.

**Postcondition:** Feedback represents equipment state and temperature; the UI
presents the announcement without advancing physics independently.

#### UC-TM-04: Receive track circuit, terrain, and beacon data

**Primary actor:** Track Model. **Supporting actor:** Train Controller.
**Requirements:** REQ-FUNC-042, 046.

**Preconditions:** Valid block data and any current beacon are supplied.
**Trigger:** A track input accompanies a tick.

**Main success scenario:** Use grade in the force balance; detect a block transition
from polarity; pass commanded speed, authority, speed limit, and the current beacon
to controller outputs; publish block, offset, and transition flag to the Track Model.

**Alternate flows:** The first polarity sample establishes a baseline. Under pickup
failure, commanded speed and authority become zero; terrain and beacon pass-through
remain available. A tick without a beacon reports `None`.

**Postcondition:** The controller receives the modeled pickup information, and the
Track Model receives current position feedback.

#### UC-TM-05: Board and disembark passengers

**Primary actors:** Passenger and Track Model. **Requirement:** REQ-FUNC-041;
passenger exchange supports the displayed count and physical mass.

**Preconditions:** The train is stopped with at least one door open.
**Trigger:** An eligible stopped tick, optionally containing a boarding event.

**Main success scenario:** Draw the disembark count once for the stop; subtract
those passengers; add the received boarding count up to remaining capacity;
recompute operating mass; return remaining capacity and update the window count.

**Alternate flows:** A boarding event while moving or with both doors shut is
ignored and not deferred. Negative or out-of-range counts reject the step.
Door reopening during the same stop does not cause another disembark draw.

**Postcondition:** Passenger count stays within 0 to 222, with mass consistent
with that count. Station scheduling and the 45 s dwell remain control/test duties.

#### UC-TM-06: Pull and release the passenger emergency brake

**Primary actor:** Passenger. **Supporting actor:** Train Controller.
**Requirement:** REQ-FUNC-047; release rule asserted by Kevin Schillinger
2026-10-28.

**Preconditions:** The selected train exists. **Trigger:** The passenger activates
the emergency-brake button in the Train Model window.

**Main success scenario:** Latch the passenger pull; report emergency brake active
immediately; apply its physical braking force on subsequent steps. The Train
Controller takes the pull up as its own emergency brake; when the driver
releases it, the controller's `emergency_brake` goes from true to false and the
pull clears.

**Alternate flows:** A brake failure does not disable the emergency brake. A pull
made after the controller's last true is kept through that release. The module
window provides no passenger-release action.

**Postcondition:** The pull remains latched until the Train Controller's
emergency brake goes from true to false.

#### UC-TM-07: Inject or clear a failure

**Primary actor:** Murphy. **Requirements:** REQ-FUNC-048.1, 048.2, 048.3.

**Preconditions:** A train is selected in the module window. **Trigger:** Murphy
toggles an engine, signal pickup, or brake failure button.

**Main success scenario:** Change only that train's failure flag; update its
window indicator; recompute discrete outputs; apply the physical effect on the
next step. Multiple independent flags may be active together.

| Failure | Simulated effect |
|---------|------------------|
| Engine | Zero traction despite a nonzero power command. |
| Signal pickup | Null commanded speed and authority in controller feedback. |
| Brake | Block service braking; emergency braking remains available. |

**Alternate flows:** Clearing a failure restores the relevant command path.
The test UI has no independent failure injection controls. The Train Controller
receives effects and equipment states, not the failure flags.

**Postcondition:** The selected train reflects the fault combination; other trains
retain their own independent failure states.

#### Developer Test Utility

The separate test UI exists only to help developers exercise the public boundary.
It is not part of the functional actor/use case model. Developers can stage input
values, run or pause the standalone clock, select 1x/10x, advance one tick, and
inspect cross-module outputs. Invalid values are rejected before model advancement.
The local link permits one driver; test-only reset and latch-clear hooks support
repeatable experiments. Disconnection holds the utility clock.

Track traversal, speed limiting, and the 45 s dwell are stand-ins used by this
utility and are removed at integration under D010. The integrated clock check
specified here runs every 15 harness ticks. The utility's existing 30-tick drift
check belongs to its older standalone path; updating that separate cadence is
not required by this review.

### 007-deployment - Train Model Deployment

**Viewpoint:** Deployment.  
**Representation:** Standalone and integrated runtime arrangements.

| Arrangement | Processes and responsibilities | Communication |
|-------------|--------------------------------|---------------|
| Standalone development | `TrainModel/main.py` hosts the model window and test link server; `TrainModel/test_ui.py` separately hosts the developer utility window and stand-ins. | `QLocalSocket`/`QLocalServer`, newline-delimited JSON. |
| Integrated system | The executable's default mode hosts the central harness; `--module train-model --harness <server>` runs one Train Model process containing the fleet and window. Other modules run in their own processes. | Shared harness protocol, local newline-delimited JSON carrying IDs and tick numbers. |
| Delivered application | Prebuilt executable on the Windows 11 host; the same executable launches module modes. The Train Model has no separate physical hardware target. | Local host communication; no external runtime service required. |

The module connects and announces readiness once its event loop runs. Harness
steps and Qt state updates execute on the owning Qt thread. Closing the module
window hides it; the harness controls process termination. QUIT ends the process;
loss of the harness also ends it. Each running train remains an object within the
fleet rather than a separate OS process.

The test setup is removable under D010. Production keeps the boundary contract,
physics, state, fleet, window, bootstrap, wire conversion, and process adapter.
Removing test files is an integration task, not an action performed by this SDD.

**Figure TM-6. Train Model deployment.**

> **DIAGRAM PLACEHOLDER TM-6:** Insert the existing deployment diagram. Label
> standalone test processes separately from the integrated harness deployment.
> Show the host device, execution environments, artifacts, and local connection.
> If the existing drawing covers standalone operation only, use that caption and
> retain the integrated arrangement described above as a separate view.

---

## 4. Decisions

The headings below follow the template. D005-style identifiers refer to promoted
repository decisions; the template's D-001-style example IDs are not reused as
new decisions. R10 supplies the latest review resolutions; section 4.9 identifies
which accepted decisions require later code or documentation changes.

### 4.1 Interface Contract Mechanism

**Basis:** D005; Train Model contract shard.  
**Context:** The physics must be callable from a test setup or the integrated
system without depending on another module's internal state.  
**Outcome:** A typed `step` boundary and read-only snapshot separate simulation
from presentation. Local failure/brake actions belong to the module window.
The harness is the integrated single driver.

### 4.2 Shared Boundary Data Types

**Basis:** D005, D008, unit conventions.  
**Context:** A universal shared struct catalog would couple module implementations.  
**Outcome:** Frozen Train Model dataclasses describe its own boundary. Pure harness
edge mappings translate to peer types without changing backend units.
`common/interfaces.py` is stale and is not an intermediate mapping layer.

### 4.3 Contract Verification

**Evidence:** `TrainModel/tests/test_contract.py` checks protocol members,
signatures, output shape, and snapshot behavior. Wire and process tests check
malformed payloads, roster following, and rejection isolation.
**Outcome:** Developers run focused local checks when changing the relevant
behavior. Existing tests are local verification references; this SDD does not
report new execution results.

### 4.4 Stub-First Development

**Basis:** D010.  
**Context:** The Train Model needs external track/controller inputs before the
full system is connected.  
**Outcome:** A separate test UI supplies stand-in producers through the public
boundary. Speed limiting and dwell in that test setup are not physics-core
responsibilities. The current physics implementation is real code; the template's
example `STUB = True` policy is not asserted as a Train Model requirement.

### 4.5 Contracts Package Ownership

**Basis:** D005 and the Train Model shard's named owner.  
**Context:** Boundary ownership must remain clear during integration.  
**Outcome:** Kevin Schillinger owns the Train Model contribution and module-owned
types. Integration mappings belong to the harness. There is no newly introduced
shared contracts package in this design.

### 4.6 External Input Validation

**Basis:** Promoted Train Model validation rules; REQ-NFR-003/004.  
**Context:** Invalid values must not partially advance a physical model or consume
its random sequence.  
**Outcome:** Validate before mutation, reject with a typed error, and return a
named per-train rejection through the process adapter. Preserve the distinction
between adapter rejection isolation and the atomic `step_all` helper.

### 4.7 Knowledge Capture and Decision Logging

**Basis:** Repository `AGENTS.md` and promoted truth entries.  
**Context:** Implementation evidence, pending proposals, and accepted contracts
have different authority.  
**Outcome:** Read facts from the fetched truth branch; proposed normative changes
go through its inbox and human promotion. This SDD records observed differences
without promoting them. For this SDD-only revision, Kevin explicitly deferred
all other documentation and proposal work to the follow-up prompts. Implementation status and test results belong in regular
project documents, not the truth store.

### 4.8 Rejected Tooling - Summary Table

No formal Train Model tooling-rejection record was found in the reviewed sources.
The following are architectural exclusions supported by existing decisions;
they are not newly invented tool evaluations.

| Tool / approach excluded from this design | Recorded reason |
|------------------------------------------|-----------------|
| Shared `common/interfaces.py` catalog | Stale and superseded as the mapping catalog under D008. |
| Direct imports of another module's boundary layouts | D005 assigns translation to the harness so each module owns its types. |
| Permanent test UI control path in the delivered Train Model | D010 makes the test UI removable and the integrated harness the driver. |

### 4.9 Resolved Review Items and Deferred Work

Kevin Schillinger resolved the review questions on October 20, 2026 (R10).
The table distinguishes the intended design from work deferred out of this
SDD-only session. No item below is a request to implement product changes now.

| Item | Resolved design | Deferred work |
|------|-----------------|---------------|
| Numerical integration | Keep `model.py` and its internal segments/substeps. Explain transition handling and midpoint power/work accounting while retaining fixed external dt. | Documentation: propose corrected D006 and align module/physics explanations. No algorithm rewrite. |
| Simultaneous brakes | Both brakes can apply simultaneously; service failure disables service only. The selected physical realization adds the two engaged brake forces. | Backend: remove service suppression, align force and state reporting, and update focused tests. |
| Station restriction on boarding | Track Model sends boarding events only at stations. Train Model enforces rest, doors, counts, and capacity without a station gate. | Documentation: clarify responsibility in the boarding signal and module descriptions. |
| Beacon encoding and between-beacon behavior | Canonical compact ASCII-escaped JSON array `[station_name, platform_side, underground]`, maximum 128 characters for the complete payload. Keep `None` between beacon ticks. | Backend: enforce complete payload length consistently. Documentation: record encoding and retention responsibility. |
| Pickup failure output | Keep commanded speed zero and authority zero. Superseded 2026-10-28: both null. | Documentation: record the settled choice; preserve existing implementation. |
| Door interlock | Train Controller ensures doors remain closed when required. Train Model follows door commands. | Documentation: remove unresolved ownership language; preserve existing Train Model behavior. |
| Vehicle parameters | 480 kW is confirmed. Rolling resistance is the only passive resistance term in scope; grade and brake forces still apply. | Documentation: remove provisional-power and extra-resistance calibration requests. |
| Position reference | Use the front of the train for offset. | Documentation: align interface comments, position signal, physics, and integration text. |
| Integrated clock | Display harness time and independently compare module time against supplied simulation time every 15 harness ticks, accounting for train creation epochs. | Backend: reconcile time and detect drift without resetting elapsed physics time. UI: present current time and selected-train drift diagnostics. |
| Arrival metadata | Remove arrival time from the Train Model window for now; retain station/platform information. | UI: remove the arrival portion of the row. Documentation: remove the requirement for an arrival data source. |
| Legacy documentation | Update outdated release, identity, harness/catalog, diagrams' descriptions, and resolved review items. | Documentation: follow the separate prompt, excluding this SDD. Existing diagrams remain author-owned insertion material. |

The three implementation prompts are provided inline in the accompanying chat:
UI changes, backend changes, and other documentation changes. They are not stored
in the repository.

For the integrated clock check, the supplied simulation timestamp represents the
end of the tick. Establish each train's epoch at its first roster appearance as
`sim_time_s - dt`, and compare `epoch + accepted_model_elapsed_s` with the current
supplied timestamp on harness ticks divisible by 15. Check after accepted steps,
and also check retained elapsed time for rejected trains. A 1 microsecond absolute
tolerance filters floating-point noise. Never realign the comparison epoch on
each tick, since that would hide missed physical steps. Window time follows the
harness independently; a rejected train can therefore show current global time
and a real drift diagnostic simultaneously.

D017 already records the 0.1 s tick as a deviation from the SRS's 1 ms preference.
The SRS's distance-based authority definition and REQ-FUNC-042 wording
"suggested speed" are interpreted through promoted D013 and the track-signal
contract: blocks and downstream commanded speed, respectively.

---

## 5. Appendixes

### A. Requirements Traceability

| Requirement | Train Model design / use case | Evidence / verification reference |
|-------------|------------------------------|-----------------------------------|
| REQ-FUNC-039 | Force balance, mass, motion integration; UC-TM-01. | Physics and integration tests; retained algorithm and deferred D006 correction in section 4.9. |
| REQ-FUNC-040.1-040.6 | Length, height, width, mass, acceleration, and velocity readouts; UC-TM-02. | `state.py`, `MainView.qml`; demonstration of displayed values. |
| REQ-FUNC-041.1/041.2 | Crew and passenger count; UC-TM-02/05. | Passenger, fleet, and mass tests; UI demonstration. |
| REQ-FUNC-042 | Circuit commanded speed and authority pass-through; UC-TM-04. | Contract/integration tests, pickup-failure tests. |
| REQ-FUNC-043 | Exact first-order cabin temperature response; UC-TM-03. | Temperature-response tests. |
| REQ-FUNC-044 | Interior/exterior light commands and feedback; UC-TM-03. | Light-output tests and UI demonstration. |
| REQ-FUNC-045 | Left/right door commands and feedback; UC-TM-03. | Door tests; Train Controller owns the interlock. |
| REQ-FUNC-046 | Beacon input and current-tick pass-through; UC-TM-04. | Beacon/platform-side tests. |
| REQ-FUNC-047 | Passenger latch and emergency response; UC-TM-06. | Brake tests and `test_release_command_clears_a_passenger_pull`. |
| REQ-FUNC-048.1-048.3 | Engine, signal pickup, and brake failures; UC-TM-07. | Failure-effect tests and selected-train UI demonstration. |
| REQ-INTF-001.3 | Dedicated module window; UC-TM-02. | `Main.qml`, `MainView.qml`. |
| REQ-INTF-013/014 | Shared clock contract and PySide6/QML presentation. | Existing process/clock tests; deferred time reconciliation and 15-tick drift work in section 4.9. |
| REQ-NFR-002 | Same dt and input sequence at 1x/10x. | Clock tests; no change in physics dt with wall-clock rate. |
| REQ-NFR-003/004 | Validation before physical mutation; isolated rejection. | Invalid-input, snapshot-invariance, and process tests. |
| REQ-DSN-001/002/003 | Prebuilt executable and local host deployment. | Integrated packaging/delivery verification remains a group activity. |
| REQ-DSN-004/005 | Public boundary, harness mappings, shared clock/logging infrastructure. | Interface, process, and harness mapping inspection. |

The functional rubric separately includes **5.9, Train Controller activates
Service Brake**. This is covered by `service_brake`, the physical brake response,
and `service_brake_active` feedback in UC-TM-01/03 and brake tests, even though the
SRS mapping groups Train Model behavior mainly under REQ-FUNC-039 through 048.

### B. Rubric Coverage

| WP2 Architecture & Design item | Points | Location in this contribution |
|--------------------------------|--------|-------------------------------|
| 1.1 System architecture: route, authority, wayside distribution, timing, vitality | 15 | Context view and Figure TM-1 placeholder. |
| 1.2 Software architecture | 15 | Composition view, responsibility table, Figure TM-2 placeholder. |
| 1.3 Use case description | 10 | Seven UC-TM narratives with actors, conditions, flows, and outcomes; developer utility documented separately. |
| 1.4 Use case diagram | 10 | Figure TM-5 placeholder and actor inventory. |
| 1.5 Class diagrams | 20 | Logical view, boundary dictionaries, Figure TM-3 placeholder. |
| 1.6 Sequence diagrams | 15 | Ordered tick interaction and Figure TM-4 placeholder. |
| 1.7 Document quality | 10 | Revision history, contents, references, consistent names/units, traceability, and resolved review decisions. |
| 1.8 Other diagrams | 0 | No additional diagram required by this rubric row. |
| 1.9 Deployment diagram | 5 | Deployment view and Figure TM-6 placeholder. |
| Total | 100 | Diagram artifacts must be inserted for the corresponding diagram criteria. |

The design review rubric likewise names architecture, software architecture, use
case actors, class, sequence, and deployment diagrams. The WP1 architecture
rubric requests complete input/output dictionaries; section 004-interface
provides the Train Model fields. The functional rubric's Train Model rows 5.0
through 5.95 map to Appendix A, including the explicit service-brake row.

Presentation delivery, observations, scrum artifacts, cost analysis, installation
instructions, and executed test results are separate course deliverables.
This design contribution provides supporting references without claiming those
deliverables are completed.

### C. Diagram Insertion Register

| Placeholder | Existing material to insert / caption check |
|-------------|---------------------------------------------|
| TM-1 Context | Author's system architecture/context diagram; label the Train Model's boundary and external producers/consumers. |
| TM-2 Composition | Author's software architecture view; may share an existing architecture figure if its caption explicitly covers both views. |
| TM-3 Class | Existing Train Model class drawing in the UML project or author's draw.io document. Verify fleet/process and release-command currency. |
| TM-4 Sequence | Existing one-step sequence; identify whether it is the standalone test path or harness path. |
| TM-5 Use case | Existing Train Model use case drawing; preserve visible product actors and exclude the testing role/developer utility operations. |
| TM-6 Deployment | Existing deployment drawing; distinguish the two-process standalone test setup from the integrated process model. |

The repository's `TrainModel/docs/diagrams/train-model.mdj` is an existing editable
source. The author also has draw.io material; no particular export is assumed to
be the final version. No diagram images or replacement drawings were generated
for this document.

### D. Verification References

| Existing test source under `TrainModel/tests/` | Design behavior it exercises |
|----------------------------------------------|-----------------------------|
| `test_contract.py` | Protocol signatures, returned boundary types, and snapshot observation. |
| `test_physics.py`, `test_physics_extended.py` | Forces, load effects, grades, braking, rollback, block changes, temperature, passengers, and failures. |
| `test_integration.py` | Kinematics, energy accounting, stops, invalid input preservation, and absence of a physics speed governor. |
| `test_model_invariants.py` | Physical bounds and invariants over changing inputs. |
| `test_fleet.py` | Independent trains, identity/selection, deterministic seeds, atomic fleet helper, and multi-train stepping. |
| `test_module_process.py` | Wire shape, roster, per-train rejection, and controller passenger-brake release. |
| `test_elapsed_clock.py`, `test_harness_clock.py` | Elapsed-step accounting and standalone clock behavior. |
| `test_link.py`, `test_link_malformed.py`, `test_input_submission.py` | Standalone transport, malformed messages, and staged-input submission. |

These are verification references, not a new execution report or a claim of
complete requirement conformance. Existing tests that encode emergency-over-service
precedence require follow-up updates for simultaneous braking. New clock/beacon
checks belong to the deferred backend work. Existing modified tests and diagram
sources were preserved during this SDD-only revision.

---

*End of Train Model contribution.*
