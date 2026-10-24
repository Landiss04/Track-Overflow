# Module owner review

Prepared 2026-10-24 from source at `f6ed1a1` and the linked integration records.
This is the shared review queue for CTC and the other module owners. It records
implementation, observations and requested decisions; it does not establish policy
or authorize changes to owners' rules. Kevin requested these carryovers be written
up for module owner review on 2026-10-24. No owner has been contacted by this document.

Code references below were inspected for the original writeup. Runtime results are the
historical bounded observations in [Phase 6 evidence](review-scenario-evidence-2026-10-22.md)
and the [Phase 6 handover](integration-handover-phase-6.md), except where the fresh
Phase 7 evidence below is explicitly cited. Source line numbers refer to `f6ed1a1`.

## Phase 7 verification follow-up

The [Phase 7 handover](integration-handover-phase-7.md#fresh-verification) records
post-cut verification of source now committed as `92e500b` on `kevin-framework`:
1,958 tests passed, 13 existing skips and 50,899 passed subtests across the module,
shared-Pi-link and utils suites. The shared-link suite passed all 71 tests;
HELLO matching is shared between relay and bringup, with relay boot/recovery policy
and bringup's optional boot preserved. The [process review evidence](integration-handover-phase-7.md#process-reviews-and-separate-performance-measurements)
is recorded separately from those module results. These checks do not resolve
[physical Pi readiness](#pi-1-physical-pi-prerequisites) or any owner policy request.
Both 1x process reviews passed; the fresh mixed-count 2/3 and Green-count 3
failures remain CTC-1/CTC-2 below. Separate short 1x/10x host measurements do not
resolve the real-Pi speed question. All twelve owner requests and pending proposal
actions remain open; Kevin's answers below are unchanged.

| Review | Owner / reviewer |
| --- | --- |
| [CTC-1: Red concurrency](#ctc-1-red-concurrency) | Landis, CTC Office |
| [CTC-2: Green three-train stall](#ctc-2-green-three-train-stall) | Landis, with Harry Tye for the wayside boundary |
| [CTC-3: Green follower at 75/76](#ctc-3-green-follower-at-7576) | Landis and Harry Tye |
| [SW-1: PLC-only safety follow-up](#sw-1-plc-only-safety-follow-up) | Harry Tye; Braden for HW alignment |
| [HW-1: Red PLC copies and real programs](#hw-1-red-plc-copies-and-real-programs) | Braden |
| [LAYOUT-1: Red block 9 interpretation](#layout-1-red-block-9-interpretation) | Track Model owner, Braden and Landis |
| [INPUT-1: Missing occupancy counts as clear](#input-1-missing-occupancy-counts-as-clear) | Braden and Harry Tye |
| [SW-2: Green starter decisions](#sw-2-green-starter-decisions) | Harry Tye and Landis |
| [TM-1: Ticket rate](#tm-1-ticket-rate) | Track Model owner |
| [TM-2: Light ahead, B1](#tm-2-light-ahead-b1) | Track Model owner; Track Controller owners for placement agreement |
| [TM-3: Automatic heaters](#tm-3-automatic-heaters) | Track Model owner |
| [PI-1: Physical Pi prerequisites](#pi-1-physical-pi-prerequisites) | Both HW module owners; Kevin for performance choice |

The cited records identify Landis, Harry and Braden. They do not establish a named
Track Model owner or Train Controller HW owner for these requests; Kevin must route
those reviews to the responsible people.

## Kevin’s answers and proposal review

Kevin supplied these answers on 2026-10-24. They record authorization and pending
human review; the twelve owner requests below remain open where stated.

| Topic | Exact answer and scope |
| --- | --- |
| Functional review speed | "yes option a is better": run functional review at 1x, retain `TIME_SLIPPED` as a fault, and measure 10x separately. Optimization and the speed decision still wait for real-Pi measurements. |
| Review machine | "for now the review will happen on this machine": the session-start system check verified `kevin-framework`. |
| Cleanup | "approved": fold duplicate HELLO validation into one helper, explicitly name Braden as requested reviewer in the HW changelog, and make the review runbook Python path portable. Requested reviewer attribution does not mean Braden accepted the change. |
| Exact owner issues | "give a wriet up of the exact issues found" and "write them up for module owner review". |
| Consolidation | "put the ctc and other module owner review things in the same place": this document holds both sets of requests. |
| Proposal collisions | "ues": consolidate the duplicate Red-routing D033 entries; withdraw the D034 Phase 6 scope proposal because it records a plan, retaining authoritative-Green-programs D034; retain both distinct D035 decisions and renumber one. These are instructions for human resolution. |

The [session handover](session-handover-2026-10-22.md) recorded 34 pre-existing
proposals in this branch's inbox plus four from PR #43. The new
[functional-review-speed proposal](../truth/_inbox/claude/quirky-fermi-sickg4/20261024-1023-review-functional-speed.md)
brings the branch directory to 35 proposal files, as counted on 2026-10-24; the four
PR #43 files remain separately attributed. That new entry is a pending proposal,
not promoted truth. The collision resolution and all proposal promotion remain
pending human action. Agents do not delete, rename or promote existing proposals.

## CTC-1: Red concurrency

**Owner:** Landis, CTC Office.

**Evidence and current behavior:** [Zone construction](../CTC-Office/ctc/scheduler.py#L177),
[zone ownership](../CTC-Office/ctc/scheduler.py#L378) and
[leg release](../CTC-Office/ctc/scheduler.py#L401) reserve two-way stretches for
scheduled runs. The historical inspection found Red 9…66 in one zone for station
destinations 16, 21, 25, 35, 45, 48 and 60. In the 900 simulated-second mixed
acceptance runs, maximum simultaneous Red count was one for both the two-train and
three-train schedules. Later Red trains can progress sequentially; that does not
satisfy Kevin's simultaneous 2/3-train requirement.

**Reproduce:** From the repository root, use the project Python environment:

```sh
QT_QPA_PLATFORM=offscreen TRACK_OVERFLOW_MULTI_TRAIN=1 python -m pytest -q \
  common/harness/tests/test_review_scenarios.py::test_scheduled_multiple_trains_each_line
```

The [test](../common/harness/tests/test_review_scenarios.py#L183) runs both counts,
uses Green destination 65 and Red 16, and stops after 9,000 ticks (900 simulated
seconds). The [historical results](review-scenario-evidence-2026-10-22.md#bounded-tests)
record maximum Green/Red counts of 2/1 and 3/1.

**Limits:** Seven real cores run in one process with prior-tick edges. The probe
checks separation, exclusive authority, dwell and controller fault latches; it does
not exercise subprocess/Pi protocol faults. No earlier separation, authority,
emergency-brake or pickup assertion failed in those recorded runs. Completion and
simultaneous Red acceptance still failed. Changing among the inspected destinations
alone does not establish a route outside the shared zone.

**Fresh Phase 7 observation:** On `92e500b`, the [complete harness run](integration-handover-phase-7.md#process-reviews-and-separate-performance-measurements)
retained both mixed-probe failures. Count 2 completed all four dwells but reached
maximum Green/Red concurrency 2/1. Count 3 reached its 900-s simulation bound with
G1/G2/R1/R2 completed, maximum counts 3/1, and endpoint G1=111, G2=65, G3=64,
R2=48. No earlier separation, exclusive-authority, emergency or pickup assertion
failed; the final fault-event assertion was not reached after the endpoint failure.
These remain in-process owner probes, separate from the passing 1x process reviews.

**Requested decision:** Confirm the intended Red dispatch/reservation behavior and
how to satisfy simultaneous 2/3 trains while retaining the owner's separation and
arbitration rules. Supply an approved scenario or specific rule change with its
safety rationale. Do not weaken the existing test to count sequential dispatch as
simultaneous operation. Related: [Green progress](#ctc-2-green-three-train-stall)
and [Red routing copies](#hw-1-red-plc-copies-and-real-programs).

## CTC-2: Green three-train stall

**Owner:** Landis; Harry Tye for any wayside contribution.

**Evidence and current behavior:** The historical Green-only two-train run completed
both dwells. Three trains became active, but at 1,200 simulated seconds G1 was at
133 returning to the yard, G2 at 65 after its dwell and G3 at 64. At the longer
2,400-second bound G1 had retired; G2 remained at 65 and G3 at 64. The
[handover](integration-handover-phase-6.md#3-final-validation-and-acceptance-limits)
reports static inspection that departure from 65 reserves upcoming zones 77…100 and
1…28. The current [_clear/_release logic](../CTC-Office/ctc/scheduler.py#L388)
checks every zone entered before the leg target and holds the run if another owns one.

**Reproduce:**

```sh
QT_QPA_PLATFORM=offscreen TRACK_OVERFLOW_MULTI_TRAIN=1 python -m pytest -q \
  common/harness/tests/test_review_scenarios.py::test_green_scheduled_multiple_trains
```

The [current test](../common/harness/tests/test_review_scenarios.py#L295) runs counts
2 and 3 independently from Red, with a 24,000-tick (2,400-second) bound.

**Limits:** This is a bounded stall, not proof of permanent deadlock. Historical
endpoint evidence does not capture the exact scheduler progress or authority hold
reason at the bound; static reservation inspection alone does not establish the
cause. The in-process limitation in [CTC-1](#ctc-1-red-concurrency) also applies.

**Fresh Phase 7 observation:** On `92e500b`, Green-only count 2 passed. Count 3
again reached the 2,400-s simulation bound with G1/G2 completed, G1 retired,
G2=65 and G3=64; maximum active count was three. See the [fresh harness evidence](integration-handover-phase-7.md#process-reviews-and-separate-performance-measurements).
No earlier separation, exclusive-authority, emergency or pickup assertion failed;
the final fault-event assertion was not reached. This repeats the bounded result
without establishing its cause or permanent deadlock.

**Requested decision:** Review the reservation span and departure/progress rules.
Obtain the scheduled-run progress, authority hold reason and zone owners at the
65/64 hold before choosing a change. Define how all three should finish their
45-second station dwells. Keep this separate from the seeded
[follower case](#ctc-3-green-follower-at-7576); no causal link has been established.

## CTC-3: Green follower at 75/76

**Owners:** Landis and Harry Tye.

**Evidence and current behavior:** The [seeded observation](../common/harness/tests/test_green_follower.py#L25)
places HEAD at 77 bound for 101 and FOLLOWER at 75 or 76, with switch 76 reported
REVERSE. At 75 the follower receives one block of authority and a zero-authority
preload at 76; at 76 it receives zero authority. The switch remains REVERSE.
The helper then seeds occupancy at 76 and 101; switch 76 stays REVERSE for all five
ticks. The [SW vital lock](../TrackCtrlSW/track_ctrl/vital.py#L217) holds the switch
when its listed block 76 is occupied, although its points are at 77.

**Reproduce:**

```sh
QT_QPA_PLATFORM=offscreen python -m pytest -q common/harness/tests/test_green_follower.py
```

**Limits:** These are owner-boundary snapshots using the existing SW `_Line` helper,
not a continuous physics loop. The transition to the head on 101 is seeded, not
observed travel. Five held ticks do not prove a permanent wait. See the historical
[Phase 6 follower description](integration-handover-phase-6.md#4-measurement-conditions).

**Requested decision:** Agree the intended follower admission/authority and listed
block versus points lock behavior, including how the follower can progress once
the head clears. Do not move/remove the lock or change CTC rules as an incidental
integration fix. Related: [SW safety scope](#sw-1-plc-only-safety-follow-up),
[starter decisions](#sw-2-green-starter-decisions).

## SW-1: PLC-only safety follow-up

**Owner:** Harry Tye; Braden for HW alignment.

**Evidence and current behavior:** Kevin's both-variant K3b policy is recorded in
[Phase 5](integration-handover-phase-5.md#4-open-questions-and-owner-review)
and [Phase 6 scope](phase-6-prompt.md#questions-to-put-to-kevin-and-owners-as-they-come-up-dont-decide).
The separate SW implementation follow-up remains open: SW still scans the PLC and
calls [vital.supervise](../TrackCtrlSW/track_ctrl/controller.py#L353), including
[listed-block switch locking](../TrackCtrlSW/track_ctrl/vital.py#L217).
The historical records also leave the planned generated vital PLC block and the
conflicting D019 proposals for Harry and Braden to resolve.

**Reproduce / inspect:** Trace `Controller.run_program` from its scan result into
`vital.supervise`; compare the enforced restrictions with the PLC safety policy and
HW programs. This is a static implementation discrepancy, with no fresh runtime
result in this writeup.

**Limits:** Policy approval is not evidence that SW migration/removal has occurred.
Deleting supervision without an agreed replacement would affect more than the
[follower lock](#ctc-3-green-follower-at-7576).

**Requested decision:** Harry should define and own the removal/migration scope,
required PLC protections and validation, resolving the variant-policy conflict with
Braden. Record that owner decision before implementing the follow-up.

## HW-1: Red PLC copies and real programs

**Owner / requested reviewer:** Braden. Kevin approved the integration work.

**Evidence and current behavior:** The three
[Red integration PLCs](../TrackCtrlHw/data/plc/red_wayside_1_integration_test.plc),
[Red-2](../TrackCtrlHw/data/plc/red_wayside_2_integration_test.plc) and
[Red-3](../TrackCtrlHw/data/plc/red_wayside_3_integration_test.plc#L1) explicitly remain
test copies. They reuse the Green AUTO/WANT/LOCK pattern for switches 9, 15, 27,
32, 38, 43 and 52. For example, [switch 52](../TrackCtrlHw/data/plc/red_wayside_3_integration_test.plc#L13)
selects reverse for occupancy at 66 and locks on 52. The split remains Red-1
1–24/73–76, Red-2 25–45/67–72 and Red-3 46–66. The authoritative source for the
reused pattern is this branch's three `green_wayside_*.plc` programs in
`TrackCtrlHw/data/plc/`, as specified in [Phase 6](phase-6-prompt.md#kevins-answers-of-2026-10-22).

**Reproduce:** Inspect all three copies and run the existing
`TrackCtrlHw/tests/test_red_integration.py` and `TrackCtrlHw/tests/test_red_routing_loop.py`
with project Python and offscreen Qt. Historical evidence records an outbound
9…16 trip followed by explicit return 17…66→52…9 and one retirement. It does not
establish simultaneous Red trains; see [CTC-1](#ctc-1-red-concurrency).

**Limits and approval:** Kevin confirmed on 2026-10-24 that he approved neighbor
`CLOSED_n` inputs before implementation: "yes". Asked whether Braden accepted the
change, Kevin answered "he didnt i did. ensure it is documented". This is Kevin's
explicit approval, not Braden's acceptance. The
[HW changelog](../TrackCtrlHw/CHANGELOG.md#2026-10-22--green-style-red-integration-routing)
contains the implementation record; Braden's owner review is still requested.

**Requested decision:** Braden should approve or replace the Red test programs,
review the reused Green routing pattern and input extension, and supply his real
Red programs if different. Kevin's authorization to reuse his pattern supersedes
the old blanket instruction to wait for real Red programs. Review
[missing inputs](#input-1-missing-occupancy-counts-as-clear) and
[block 9](#layout-1-red-block-9-interpretation) with the programs.

## LAYOUT-1: Red block 9 interpretation

**Owners / reviewers:** Track Model owner, Braden and Landis.

**Evidence and current behavior:** Kevin established the physical yard connection
at section-C block 9 and required preserving the course data. The reader geometry
remains an implementation assumption: point 9, NORMAL to 8, REVERSE to yard,
fixed side 10 and light on 10. See the [CTC changelog](../CTC-Office/CHANGELOG.md),
[CTC hardcoded Red to_yard](../CTC-Office/ctc/track_layout.py#L120),
[HW yard interpretation](../TrackCtrlHw/track_ctrl_hw/territory.py#L193) and
[Track Model interpretation](../TrackModel/track_model/layout.py#L433).

**Reproduce / inspect:** Compare the three readers' block-9 switches, yard
adjacency and CTC retirement target using unchanged `TrackModel/red_line.json`.
The historical Red return probe in [HW-1](#hw-1-red-plc-copies-and-real-programs)
exercises this reading.

**Limits:** Reader agreement and a passing historical return do not confirm that
Kevin intended every switch leg. The old source-file edit was an implementation
choice; immutable course data is not permission to encode the geometry as truth.

**Requested decision:** Confirm or correct each of the point, two legs, fixed side,
light placement and CTC return target. Retain the source data unchanged.

## INPUT-1: Missing occupancy counts as clear

**Owners:** Braden and Harry Tye.

**Evidence and current behavior:** HW exposes own and adjacent read-only OCC/CLOSED
names through [one adjacency helper](../TrackCtrlHw/track_ctrl_hw/wayside.py#L88).
Its [scan image](../TrackCtrlHw/track_ctrl_hw/wayside.py#L405) uses membership in
full-line occupied/closed sets, so absent occupancy membership is false. SW's
[scan image](../TrackCtrlSW/track_ctrl/controller.py#L320) also defaults absent
occupancy keys to false. The [HW safety note](../TrackCtrlHw/CHANGELOG.md#2026-10-22--red-yard-and-integration-inputs)
warns that an omitted occupied block can consequently be read as clear.

**Reproduce / inspect:** At the HW boundary, compare a scan with a neighboring
occupied block included in `track_model.occupied_blocks` against the same scan
with that block omitted; inspect the associated `OCC_n` bit. SW can be inspected
with a missing owned occupancy key. This is a targeted reproduction recipe, not
a test executed for this writeup.

**Limits:** Complete data from the current harness does not define behavior for
partial/stale input producers or different territory cuts. Kevin's CLOSED approval
in [HW-1](#hw-1-red-plc-copies-and-real-programs) does not establish Braden's review
or settle occupancy completeness.

**Requested decision:** Define who guarantees completeness, how unknown/stale
occupancy is represented and detected, and what PLCs should do when a required
neighbor is unavailable. Review cross-wayside coverage and keep outputs owned by
their wayside. Coordinate any change across both variants and the harness.

## SW-2: Green starter decisions

**Owners:** Harry Tye and Landis.

**Evidence and current behavior:** [SW discrepancy E7](../TrackCtrlSW/INTEGRATION_DISCREPANCIES.md#e-new-with-the-boundary-and-startup)
records the integration switch rule, `SUG_n`/`REV_s` inputs, switch 28's reverse
rest position, unseen cross-wayside approaches and listed-block/points locking.
The [current generator](../TrackCtrlSW/track_ctrl/controller.py#L625) uses preloaded
suggestions and occupancy to detect approaches, holds occupied points or conflicting
approaches, and stands for an approach it cannot see. Green's historical one-train
round trip passes; it does not settle these owner decisions.

**Reproduce / inspect:** Review `TrackCtrlSW/tests/test_starter_switches.py` with the
generated Green programs and current territory cut. Exercise alternate cuts where
a switch's approach is outside its wayside. Reuse [CTC-3](#ctc-3-green-follower-at-7576)
for the 75/76 case rather than creating a second follower writeup.

**Limits:** E7 contains historical engine-detector and Red-normal-only statements;
the later [Phase 4](integration-handover-phase-4.md) and
[Phase 6](integration-handover-phase-6.md) handovers supersede those integration
status descriptions. E7's owner-review questions remain; this document does not
reopen the completed Green round-trip repair.

**Requested decision:** Accept or revise the extra starter inputs, rest positions,
points/listed-block lock policy and cross-wayside approach handling. Landis should
confirm the CTC two-way-zone protection assumed at this boundary. Coordinate with
[SW-1](#sw-1-plc-only-safety-follow-up) and [INPUT-1](#input-1-missing-occupancy-counts-as-clear).

## TM-1: Ticket rate

**Owner:** Track Model owner.

**Evidence and current behavior:** [Q-P4-7](integration-handover-phase-4.md#4-open-questions)
was kept open at Kevin's request. [TrackConfig](../TrackModel/track_model/interface.py#L137)
defaults `ticket_probability` to 0.02; [_sell_tickets](../TrackModel/track_model/model.py#L437)
rolls once per station per tick, independent of `dt`. At the 0.1-second system tick
this implies an expected 12 tickets per simulated minute per station.

**Reproduce / inspect:** Inspect the default and one roll per tick; use a seeded
long run to estimate the rate. No statistical sampling was done for this writeup.

**Limits:** Twelve is an expectation, not an exact observed count. Correct per-station
sale delivery to CTC does not resolve the sales-generation rate.

**Requested decision:** Confirm the intended demand rate and whether it should be
per tick or time based. Keep the existing sales interface separate from that choice.

## TM-2: Light ahead, B1

**Owner:** Track Model owner; Track Controller owners for placement agreement.

**Evidence and current behavior:** [B1](../TrackModel/BUGS.md#b1) documents that
[_signal_seen](../TrackModel/track_model/model.py#L493) only sends the entered
block's light on the entry tick. It returns `None` on subsequent ticks and does
not select the next light facing the train. Green 63→64 receives block 64's light,
which guards the opposite-direction 64→63 movement.

**Reproduce:** Follow B1's system scenario: enter Green 64 from 63, then change the
light while remaining in 64 and inspect the Train Controller feed.

**Limits:** The harness forwards the Track Model output. A retained last aspect in
the Train Controller does not prove the aspect is current or faces the train. No
fresh visual or runtime reproduction was performed here.

**Requested decision / owner work:** Resolve B1's per-tick, direction-aware light
ahead behavior and confirm physical signal placement with the Track Controller
owners (also SW discrepancy C6). Use the existing B1 issue for implementation detail.

## TM-3: Automatic heaters

**Owner:** Track Model owner.

**Evidence and current behavior:** Authoritative `origin/truth` entry
`truth/decisions/D026-track-model-switches-heaters.md` assigns automatic switching
to the Track Model and leaves its switching rule open. Current
[_heater_on](../TrackModel/track_model/model.py#L319) requires `_heater_cmd` true;
[initialization](../TrackModel/track_model/model.py#L618) sets it false. The harness
sends no heater commands, as recorded in
[design G-SIG-18](system-integration-design.md#62-signals-and-edges).

**Reproduce / inspect:** In the integrated path, lower ambient temperature without
sending heater commands and inspect section heater states. The command gate remains
required in current source; no temperature threshold is implemented by that method.

**Limits:** D026 settles the responsible module, not thresholds, hysteresis or
failure behavior. No new temperature experiment was run for this document.

**Requested decision:** Specify the automatic switching rule and failure behavior,
then implement it in the Track Model. Do not add a Track Controller heater command
to bypass that owner decision.

## PI-1: Physical Pi prerequisites

**Owners:** Track Controller HW owner (Braden) and Train Controller HW owner;
Kevin for the speed decision after hardware measurements.

**Evidence and current behavior:** [Owner setup](pi-owner-setup.md) describes the
shared bundle, per-module USB identities and service installation.
[Bring-up checks](pi-bringup-checks.md) separate software simulations from hardware
acceptance. The historical Phase 6 run verified process/pty behavior and a frozen
Linux startup smoke; neither verifies a real board, USB power stability, cold-boot
timing or unplug/reboot durability.

**Reproduce / next evidence:** Owners provision a working Pi 5 from the shared
recipe, verify identity and matching HELLO bundle hash, then run the existing echo,
recorded-workload, full-system and real-board fault commands/checklist. Return the
board/OS/source revision, hashes, timing tables, logs and journals. See
[real-board checklist](pi-bringup-checks.md#real-board-fault-checklist-pending).

**Limits:** Physical results remain absent from the cited records. Real-board fault
checks are currently a checklist; simulated scripts do not establish hardware
completion. Windows packaging remains deferred. Kevin's 2026-10-24 review choice
is 1x on "this machine" (verified `kevin-framework`), keeping `TIME_SLIPPED` a fault
and measuring 10x separately; that does not waive physical measurements.

**Requested decision / owner action:** Report working boards and provide those
measurements before choosing optimization or a 10x tradeoff. Kevin's standing
instruction is "wait for pi measurements". Confirm the Train Controller HW review
contact and physical readiness before scheduling the hardware run.
