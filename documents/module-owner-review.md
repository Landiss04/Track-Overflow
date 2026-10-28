# Module owner review

Prepared 2026-10-24 from source at `f6ed1a1` and the linked integration records.
This is the shared review queue for CTC and the other module owners. It records
implementation, observations and requested decisions; it does not establish policy
or authorize changes to owners' rules. Kevin requested these carryovers be written
up for module owner review on 2026-10-24. No owner has been contacted by this document.

Code references below were inspected for the original writeup. Runtime results are the
historical bounded observations in [Phase 6 evidence](review-scenario-evidence-2026-10-22.md)
and the [Phase 6 handover](integration-handover-phase-6.md), except where the fresh
Phase 7 evidence below is explicitly cited. Original source line numbers refer to
`f6ed1a1`; relative test links were refreshed against `d606e05` on 2026-10-25.

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

## Owner diagnostics follow-up, 2026-10-25

Kevin answered **"No updates—continue owner diagnostics"**. Reviewed bounded
observations now extend CTC-1, CTC-2 and INPUT-1 below; no owner policy changed
and all twelve requests remain open. The [independent Phase 7 receipt](integration-handover-phase-7.md#independent-phase-7-verification-receipt)
records the completed verification separately. The [Phase 8 prompt](phase-8-prompt.md)
scopes reusable diagnostic coverage and remaining evidence gaps. Temporary probe
scripts/JSON are scratch artifacts; the essential method and outcomes are retained here.

The reusable coverage follow-up below records Green first transitions, Red seeded
scheduler snapshots and input/retention boundaries at sources `c4b3cce`
(Green/input) and `3319d14` (Red).
These are diagnostic observations, not new owner decisions. The three existing
multi-train acceptance failures remain unchanged; the completed Phase 7 suites
and process reviews were not repeated for this coverage-only change.
All new checks ran on 2026-10-25 with offscreen Qt and bytecode disabled. For the
recorded commands, `PYTHON=/home/kevin/ECE/Trains/.venv/bin/python`; the runbook
retains portable interpreter selection for other checkouts.

| Review | Owner / reviewer |
| --- | --- |
| [CTC-1: Red concurrency](#ctc-1-red-concurrency) | Landis, CTC Office |
| [CTC-2: Green three-train stall](#ctc-2-green-three-train-stall) | Landis and Harry Tye, jointly across CTC admission and SW starter separation |
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

## CTC owner answers, 2026-10-25

Landis's replies to the CTC questions below, relayed by Kevin on 2026-10-25.
Each reply is also recorded under its request. Pending truth proposals in this
branch's inbox carry the normative parts; none is promoted.

| Request | Landis's answer | Done on this branch |
| --- | --- | --- |
| [CTC-1](#ctc-1-red-concurrency) | Reserve by direction, not by train. Several trains may share a stretch they all travel the same way; a train that needs it the other way waits until it is empty. Make the loop 53–66 its own one-way section where a turned train waits until the trains following it have cleared the stretch outbound. Keep yard block 9 inside the reservation until the train retires. Once a train waits to come back, release no more outbound trains. | Implemented in `CTC-Office/ctc/scheduler.py`; proposal `20261025-2128-two-way-zone-direction-reservation.md` |
| [CTC-2](#ctc-2-green-three-train-stall) | A Track Controller problem, not the CTC's. | Routed to Harry Tye; no CTC change |
| [CTC-3](#ctc-3-green-follower-at-7576) | A Track Controller problem, not the CTC's. | Routed to Harry Tye; no CTC change |
| [LAYOUT-1](#layout-1-red-block-9-interpretation) | The Track Model's `layout.py` is the master layout. A CTC reading that differs from it is wrong; where the Track Model's own reading is in question, the question is the Track Model owner's. The CTC does not update track information. | CTC adjacency matches the Track Model; the CTC's yard departure direction did not and is fixed. Proposal `20261025-2130-track-model-layout-is-master.md` |
| [SW-2](#sw-2-green-starter-decisions) | Trains must not be dispatched into head-on deadlocks: a train waits to be released toward the yard until it is safe, or is routed around oncoming trains. | Covered by the CTC-1 rule and proposal |
| [INPUT-1](#input-1-missing-occupancy-counts-as-clear) | CTC closures are set only in maintenance mode, and only the CTC reopens them, in maintenance mode. The Track Controllers have no authority over them. The CTC keeps the list of blocks and switches it controls in maintenance and sends it; a Track Controller checks the list before it sets a switch or closes or opens a block. | Proposal `20261025-2129-maintenance-closure-lock-switches.md`; occupancy completeness stays with Braden and Harry |

## Track Controller owner answers, 2026-10-26

Braden Bosilovich's answers are in [module-owner-review-braden.md](module-owner-review-braden.md)
(branch `feature/TrackCtrl-HW-vital`, `a5bd465`, merged here). Applied on this
branch on 2026-10-27:

| Request | Answer | Done on this branch |
| --- | --- | --- |
| HW-1 | The Red programs are Braden's; a generated vital block runs after every program | Merged; `TrackCtrlHw` 104 tests pass |
| CTC-1, CTC-2 | The CTC Office keeps one empty block between trains (Braden and Harry Tye) | `ctc/routing.py`: authority ends two blocks short of an occupied block. Kevin asked for it ahead of Landis's agreement; Conflict proposal for Landis |
| SW-1 | Take Harry's `development` TrackCtrlSW (generated vital PLC code) | Taken, with one fix approved by Harry (below) |
| INPUT-1 | An expected block that is not reported counts as occupied | Not done: needs the harness to carry every reported block. Proposal written |
| LAYOUT-1, TM-2 | HW follows the Track Model; signals sit at switches | Proposal for TM-2; LAYOUT-1 stays the Track Model owner's |

**SW-1 root cause (2026-10-27).** With Harry's code the Green train stopped for good
in block 64. His generated separation rule was `AUTH_n := NOT (OCC_n-1 OR OCC_n+1)`,
which holds the block a train is about to enter, because that block's neighbour is the
train's own. Each module reads the others' outputs from the tick before, so the
train read speed 0 and authority 0 for one tick on entering every block. The PR #50
Train Controller latches that as a signal pickup failure (Braden's request 9) and
brakes. Adding the missing term, `AUTH_n := NOT (OCC_n AND (OCC_n-1 OR OCC_n+1))`,
made the same run reach Glenbury at tick 377 with no failure. Harry approved the fix.

**Results, 2026-10-27.** On the working tree (Harry's SW with the fix, the CTC gap,
Braden's HW), both 1x process reviews, the end-to-end and system tests and the train
loop pass (55 passed, 481 subtests). A 3,000-s probe of the count-3 Red half had
**three Red trains out at once and all three back in the yard by 1,090 s**, which
meets CTC-1. Both count-3 acceptance tests still fail, now for a new reason: at tick
4,740 G1, holding 5 m/s up Green 93's 2% grade, latches an engine failure. The PR #50
detector flags one whenever the power commanded would give 0.1 m/s² on the flat and
speed has not risen 0.05 m/s in 2 s. That is true of any train holding speed on a
grade steeper than about 1%. This belongs to the Train Controller owners
(`Train-Ctrl_HW/OPEN_ISSUES.md` #23); nothing was changed there.

**Left for owners.** Harry: a not-ready SW wayside transmits nothing, so the Track
Model keeps its crossings' last state (the harness crossing test is marked
expected-failure), and `test_hw_language.py` fails 3 tests against Braden's new
`CTCSW_s`/`CTCREV_s` names. Train Controller: request 9 and the grade false positive.
Kevin: the `development` merge hazard (Braden's request 1), and regenerating the Pi
bundles after this merge (request 7).

## Answers, 2026-10-28

Kevin's answers to the open questions, and Landis's reply on the gap, relayed by
Kevin.

| Question | Answer | Done on this branch |
| --- | --- | --- |
| Passenger brake release (Train Controller #25) | "it is latched until the train controller sends ebreak = false" (Kevin) | The Train Model clears a pull when the controller's emergency brake goes from true to false; the one-shot `passenger_brake_release` is withdrawn. Harness release test passes. Proposals for `signals/passenger-brake-release` and `arbitration/passenger-emergency-brake` |
| Pickup failure (Braden's request 9) | "send null for speed and authority on a signal pickup failure simulating invalid data" (Kevin); then "yes make this change" for the Train Controller to read null | The Train Model sends null for both, the harness passes it on, and the Train Controller flags a pickup failure on a null (`signal_lost`); its 0/0 rule is gone, so a valid stop never trips it. Proposal for `signals/track-signal` |
| Train Controller #25 | "close this issue" (Kevin) | Closed in `Train-Ctrl_HW/OPEN_ISSUES.md` |
| Speed limit to the Train Controller | "Remove the speed limit send"; "The speed limit for me is the cmd speed" (Train Controller owner, relayed by Kevin) | `ControllerOutputs.speed_limit_mps` removed; the Train Model still shows the limit from Track Info. Controller #24 closed. Proposal for `signals/track-info` |
| Gap between trains (CTC-1, CTC-2) | Keep the one-block gap; never give a train authority that would put it next to another train, since the waysides deadlock adjacent trains (Landis; Kevin: "the gap should be kept") | `ctc/routing.py` `keep_gap()`: no authority ends next to a block another train occupies or holds in its authority, on the route or off it. Two trains head on now stop one block apart. Proposal resolving the Conflict in `arbitration/authority-stops-before-obstruction` |

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

The [test](../common/harness/tests/test_review_scenarios.py#L234) runs both counts,
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

**Targeted diagnostic, 2026-10-25:** On `d606e05`, `kevin-framework`, a
read-only scheduler probe reused `review_schedule`, `StubCtcOffice.load_schedule`
and production `AutoDispatcher` for the Red half of the count-2/count-3 schedules
(station 16; 180-s release spacing). Each plan has 102 path entries, station index
7 and yard index 101: outbound 9→…→16, then 17→…→66→52→51→…→9. Reversed
edge pairs connect 9…52; the planner's loop closure adds 53…66. Both counts
therefore produce zone `9` covering 9…66 and span `(0, 101)` for every run.
This is schedule-dependent: the existing default-course zone test expects 16…66.

Five synthetic World snapshots exercised actual hold/release predicates:

| Synthetic offset | R1 / zone `9` | Followers |
| --- | --- | --- |
| +400 s, all departures due, no heads | In yard, at −1, released to index 7; owns zone | R2/R3 HELD by R1 before its head is observed |
| +401 s, head at 16 | Dwelling, at 7; owns zone | HELD by R1 |
| +446 s, dwell expired | TO_YARD, released to 101; owns zone | HELD by R1 |
| +447 s, head at yard entry 9 | TO_YARD, at 101; still owns zone | HELD by R1 |
| +448 s, head absent and not lost | DONE, releases zone | R2 released to 7 and owns zone; R3 waits for R2 |

Probe assertions passed for both counts. From `CTC-Office`, project Python
`-m pytest -q -p no:cacheprovider tests/test_ctc_scheduler.py::ZoneTest` passed
**3 tests in 0.14 s**. The probe used project Python, offscreen Qt and
`PYTHONDONTWRITEBYTECODE=1`; its temporary entry point was
`/tmp/track-overflow-owner-diagnostics-20261025/red-concurrency.py`.
The focused tests were agent-run; the orchestrator reviewed and independently
reran the probe, confirming both zone spans and final R1 DONE / R2 in-yard /
R3 HELD states.
These are deliberately seeded scheduler snapshots, not fresh physics or separation
acceptance. Blocker-owner text is inferred from actual `_holds`/`_clear` predicates,
not a public scheduler hold-reason event. No alternative route was tested as safe.

**Reusable seeded diagnostic, 2026-10-25:** Source `3319d14`, on
`kevin-framework`, adds
[Red schedule/zone snapshots](../common/harness/tests/test_red_owner_diagnostics.py).
Qwen drafted the tests; a sol subagent refined them to observe release and arrival
transitions in one sequence per count. The orchestrator reviewed the actual source
and ran the tests with project Python and offscreen Qt. The check reproduces the
review schedule's two/three Red trains through the existing parser/planner and
actual `AutoDispatcher` actions/progress. Its five synthetic World snapshots use
offsets +400, +401, +446, +447 and +448 s; these are seeded time jumps, not a
physics run or a change to the harness's 0.1-s clock.

```sh
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 "$PYTHON" -m pytest -q \
  -p no:cacheprovider common/harness/tests/test_red_owner_diagnostics.py
```

The direct Red check passed **4 tests in 0.08 s**. Plans retain 102 path entries,
station index 7, yard index 101, and zone 9 covering 9…66 through span `(0, 101)`.
The sequence starts QUEUED, observes R1's release and arrival, carries its actual
orders forward, and locates the final block 9 without overwriting progress. R2
receives its first order only when R1 becomes DONE at +448 s; R3 remains HELD by
R2. This supplies reusable coverage of the historical snapshot table above.

The sol subagent also ran, from `CTC-Office`,
`"$PYTHON" -m pytest -q -p no:cacheprovider tests/test_ctc_scheduler.py::ZoneTest`:
**3 passed in 0.14 s**.
The orchestrator's final combined check of all four new diagnostic files, using
`-m pytest -q -p no:cacheprovider`, passed **14 tests, 1 skipped in 1.51 s**.
That skip is the dedicated opt-in Green capture, independently passed below;
the two input files and Red tests run by default. Scoped Flake8 with
`-j 1 --max-line-length=79` passed for all four files.

**Decision packet:** Landis must decide whether this schedule should reserve zone
9 through yard retirement and supply approved simultaneous 2/3-train behavior.
The reproduced boundary alone does not select a different zone, route or release
rule. Required validation after an approved change: these hold/release snapshots,
the unchanged mixed-count acceptance tests with exclusive authority/separation,
and the Red process/real-Pi route and fault checks with Braden's reviewed programs.
Seeded release of R2 after R1 DONE is not simultaneous-Red acceptance.

**Requested decision:** Confirm the intended Red dispatch/reservation behavior and
how to satisfy simultaneous 2/3 trains while retaining the owner's separation and
arbitration rules. Supply an approved scenario or specific rule change with its
safety rationale, including whether this schedule's zone should include yard 9
and remain held through retirement. Do not weaken the existing test to count
sequential dispatch as
simultaneous operation. Related: [Green progress](#ctc-2-green-three-train-stall)
and [Red routing copies](#hw-1-red-plc-copies-and-real-programs).

**Landis's answer (2026-10-25):** Reserve by direction, not by train; make the
loop 53–66 its own one-way section where a turned train waits for its followers
to clear 9–52 outbound; keep yard block 9 in the reservation until retirement;
once a train waits to come back, release no more outbound trains.

**Implementation, 2026-10-25:** `two_way_zones` no longer folds loops into a
zone, and `AutoDispatcher` reserves each zone by direction (`opposed`): trains
share a zone going the same way, never opposite ways. A train that has turned is
sent to the loop's last block (53 on Red) and waits there (`Progress.wait`);
while it waits no train enters that zone the other way for the first time. On the
review schedule zone 9 covers 9…52 and is held inbound until retirement. On the
default schedule the zones are Red 16…52 and Green 77…85 and 13…28. New
`ZoneTest` cases cover direction sharing, the loop wait and the outbound hold;
`EndToEndTest` now asserts no opposed passes and more than one train out at once.
**Acceptance after the change, 2026-10-25** (`kevin-framework`, project Python,
offscreen Qt, `TRACK_OVERFLOW_MULTI_TRAIN=1`): the CTC suite passed 266 tests and
the rewritten [Red seeded diagnostics](../common/harness/tests/test_red_owner_diagnostics.py)
6. In `test_review_scenarios.py` plus the Green diagnostics, 5 passed, 1 skipped
and 2 failed in 328 s: `test_scheduled_multiple_trains_each_line[3]` and
`test_green_scheduled_multiple_trains[3]`. Count 2 passed. A 3,000-s probe of the
count-3 Red half reached **three Red trains out at once** (it was always one
before). R1 waited at 65 while R2 and R3 came round the loop behind it, and was
released at 664 s. It then got CTC authority to 66 but wayside authority 0. The
Red integration-test PLC
(`TrackCtrlHw/data/plc/red_wayside_3_integration_test.plc`) has
`AUTH_65 := NOT (CLOSED_65 OR (OCC_65 AND (OCC_64 OR OCC_66)))`, so a train with
a follower in the block behind it loses authority, and R1 at 65 with R2 at 64 stop
for good. The CTC's own rules allow a follower one block behind
(`one-train-per-block`, `authority-stops-before-obstruction`). This is the same
adjacent-train pattern as CTC-2's Green endpoint (G2 at 65, G3 at 64). Per
Landis it is a Track Controller question, for Braden (that PLC copy awaits his
review) and Harry. No PLC was changed, and the acceptance test was not weakened.

## CTC-2: Green three-train stall

**Owners:** Landis and Harry Tye, jointly across CTC admission and SW starter separation.

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

The [current test](../common/harness/tests/test_review_scenarios.py#L346) runs counts
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

**Targeted diagnostic, 2026-10-25:** On `d606e05`, `kevin-framework`, an
observation-only subclass of the existing real-core loop ran the unchanged
Green count-3 test to its 24,000-tick / 2,400-s bound. The first trace took
47.145 wall seconds; a second boundary capture took 46.887 s. Its temporary
entry point was `/tmp/track-overflow-owner-diagnostics-20261025/green-stall.py`,
run from the repo root with project Python `-B` and offscreen Qt. G2 was HELD by
G1's zone 1 at tick 12,000, but was TO_YARD by the tick-20,000 sample. That
earlier reservation hold had cleared; it does not explain the endpoint alone.

| Endpoint boundary | Captured value |
| --- | --- |
| Trains / scheduler | G1 done; G2 at 65, G3 at 64; G2 clear=True, owns zones 77 and 1 |
| CTC suggestions | Block 65: 18 m/s, 35 authority blocks; block 66: 18 m/s, 34 blocks |
| GTC-03 input image | `OCC_64=True`, `OCC_65=True`, `OCC_66=False` |
| Generated starter gate | `AUTH_65 := NOT (OCC_65 AND (OCC_64 OR OCC_66))` |
| Raw PLC authority | `AUTH_64=False`, `AUTH_65=False`, `AUTH_66=True` |
| SW outputs / overrides | 65: 0 m/s, 0 blocks; 66: 18 m/s, 34 blocks; no overrides |
| Train Model G2 input | 0 m/s command, 0 authority blocks |

Replaying the compiled starter source with the captured image reproduced the
raw values; the orchestrator independently compiled and replayed that capture.
At this endpoint, the boundary first loses the nonzero CTC grant at
the SW starter AUTH gate, without a reported vital-layer override. This narrows the
observation; it does not establish which queue/admission or separation policy
the owners intend, or prove permanent deadlock. The trace and replay use cores
in process and do not verify process/Pi protocol behavior.

**Arrival/door follow-up:** The same capture has G3's front on block 64 at
43.798 m, speed 0, with its model right door open and Green controller door
command `[False, True]`; current `TrackInfo` is GREEN K-64 with no station name,
while the approach beacon announces GLENBURY/right. Approach-beacon placement is
expected by `TrackModel/track_model/layout.py:545–565` and `model.py:475–489`;
front/current-block reporting is in `TrainModel/train_model/interface.py:198–203`
and `model.py:588,620–622`. This in-process scenario imports shared `train_ctrl`
from `Train-Ctrl_HW`: `train_ctrl/control.py:209–215,453–480` arms a pending
beacon stop, opens at standstill without a station-block check, and keeps doors
open until positive command/authority. Train Controller and Track Model owners
should clarify whether an authority stop on the approach counts as arrival and
how station eligibility is conveyed, coordinating with Landis and Harry; this is
an open interpretation, not a defect verdict or a physical-variant observation.
The opt-in multi-train probe does not assert this zero-authority door case;
the two passing process reviews retain their platform-door checks. This concerns
beacon/arrival signaling, distinct from the aspect issue in [TM-2](#tm-2-light-ahead-b1).

**Reusable transition diagnostic, 2026-10-25:** Source `c4b3cce`, on
`kevin-framework` (Ubuntu 26.04.1; project Python 3.14.4, PySide6 6.11.2), adds
[first-hold/grant coverage](../common/harness/tests/test_green_owner_diagnostics.py).
It reuses `_Loop.step` and the Green half of `review_schedule(3)` unchanged.
The sol subagent implemented and ran it; the orchestrator reviewed the source
and independently ran the command below. Nine selected snapshots are retained
as the `green_owner_diagnostics` JUnit property, with preceding ticks and the
grant's next three ticks. The direct run passed **1 test in 38.04 s**. No endpoint
acceptance requirement was weakened.

```sh
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 \
TRACK_OVERFLOW_GREEN_OWNER_DIAGNOSTICS=1 "$PYTHON" -m pytest -q \
  -p no:cacheprovider -o junit_family=legacy \
  --junitxml=/tmp/phase8-parent-green.xml \
  common/harness/tests/test_green_owner_diagnostics.py
```

`PYTHON` is the project venv interpreter selected in the [runbook](review-runbook.md).
The check has a 24,000-tick / 2,400-s simulation ceiling and stops at tick
19,094 / 1,909.4 s after capturing the grant propagation. It retains separation,
exclusive-authority, dwell, emergency/pickup and fault-event assertions, plus
standstill and zero power when doors are open. It is opt-in independently of
the unchanged multi-train acceptance tests.

| Transition | Observation |
| --- | --- |
| 2,517 → 2,518 | G2 changes from dwelling to HELD; G1 owns zones 1 and 77, and G2's next leg is not clear. |
| 3,867 → 3,868 | First simultaneous stand below 0.01 m/s at G2=65, front 84.983 m, and G3=64, front 43.798 m. G3's preceding speed was 0.013114 m/s. |
| G3 at 3,868 | Current Track Info has no station name; beacon announces GLENBURY/right, scheduled station is 65. The controller emits `[False, True]`; the Train Model still consumes the preceding `[False, False]` and reports closed doors. |
| 19,090 → 19,091 | CTC releases G2 TO_YARD, clear=True, holding zones 1 and 77; its fresh block-65 suggestion becomes 18 m/s and 35 blocks. SW still consumes the preceding zero grant on this tick. |
| 19,092 → 19,094 | SW consumes the positive grant, but OCC64/OCC65 are true and OCC66 false; replayed AUTH65 is false, live block-65 output stays 0/0, and no vital override is reported. Block 66 passes 18 m/s and 34 blocks. G2's consumed Train Model signal remains 0/0. |

**Decision packet:** Landis and Harry must coordinate admission with the starter
separation gate; the earlier CTC reservation hold clears before the later starter
denial. Train Controller/Track Model owners must resolve station eligibility on an
approach stop, including the one-tick door-command handoff. Remaining gaps are
approved behavior and a safe completion scenario, not another endpoint sample.
Required validation after an owner-approved change: repeat this transition probe,
the unchanged count-2/count-3 acceptance and separation checks, and the process
platform-door/dwell review; then validate the relevant real-Pi path. This bounded
in-process result establishes neither permanent deadlock nor process/Pi correctness.

**Requested decision:** Landis and Harry should coordinate the queue/admission
behavior with the starter's separation gate and define how all three trains
should finish their 45-second station dwells. Review the captured boundary before
choosing a policy change; do not attribute the endpoint solely to mutual zone
reservation. Keep this separate from the seeded
[follower case](#ctc-3-green-follower-at-7576); no causal link has been established.

**Landis's answer (2026-10-25):** A Track Controller problem rather than a CTC
one. Harry Tye owns the follow-up. The CTC-1 change also lets same-direction Green
trains share 77…85 and 13…28, which changes the admission this stall was
measured under.

Reply from Harry : This is a bug in the PLC program, not a bug of the Track Controller. You will need to let me know if we need completely functional PLC programs to do this first integratation but this is at least a week away. Also it will be hard to verify complete PLC correctness w/o integration so this is a chicken-egg issue if you require PLCs for integeration. 

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

**Landis's answer (2026-10-25):** Not a CTC issue; a Track Controller one.
Harry Tye owns the listed-block versus points lock follow-up.

Reply from Harry : CTC should not be scheduling trains to follow within 1 block of each other for this specific reason. Head train requires a reverse switch and follower train does not; vital code ensures we don't set the switch for block 76 while a train is on it but b/c the train requires a normal switch, it waits. 

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

Reply form Harry: SW does not call vital.supervise, PLC vital code has been implemented and tested. 

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

**Landis's answer (2026-10-25):** The Track Model's `layout.py` is the master.
If the CTC's layout differs from it, the CTC is wrong; if it matches, the question
belongs to the Track Model owner. The CTC does not change track information.

**Comparison, 2026-10-25:** The CTC reads the same unchanged
`TrackModel/red_line.json` and `green_line.json`. Block adjacency matches the
Track Model's for every Red and Green block, and both retire Red trains at 9.
The CTC differed in one place: it let a train leave the Red yard toward 8, while
the Track Model's `next_block` sends a train out of the yard through switch 9's
yard leg out the fixed side, to 10. The CTC now does the same
(`YARD_EXIT_FROM` in `CTC-Office/ctc/tracking.py`), so the default Red run starts
9→10…16. The switch-9 reading itself (point 9, NORMAL 8, REVERSE yard, fixed
side 10) is the Track Model's assumption in `_read_switches` and remains the
Track Model owner's question.

**Track Model owner's answer (2026-10-26):** Confirmed as the Track Model's reading,
and `layout.py` stays the master: point 9, NORMAL to 8, REVERSE to the yard, fixed
side 10, light on 10. The source JSON stays unchanged. This comes from the owner's
reading, not from a document or decision, so it is not recorded as truth until Kevin
confirms the physical layout.

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
an executed historical test; the fresh targeted probe below now exercises these boundaries.

**Limits:** Complete data from the current harness does not define behavior for
partial/stale input producers or different territory cuts. Kevin's CLOSED approval
in [HW-1](#hw-1-red-plc-copies-and-real-programs) does not establish Braden's review
or settle occupancy completeness.

**Targeted diagnostic, 2026-10-25:** On `d606e05`, `kevin-framework`, a
read-only synthetic probe exercised actual edges, codecs and controller/module
steps. Normal Track Model output emits a Boolean for every loaded block
(`TrackModel/track_model/model.py:501–508`). The edge keeps true members only;
HW and SW scan inputs then use set membership. A missing occupied member in the
probe is partial/malformed producer data, not demonstrated normal Track Model output.

| Boundary case | Observed outcome |
| --- | --- |
| HW Red-2 own 25 / adjacent 76 | Both OCC/CLOSED names exist; adjacent input is read-only |
| HW Red-2 `OCC_80` declaration | Outside namespace; PLC load raises `PlcError` |
| SW GTC-02 own 28 / remote approach 150 | 28 exists; 150 is unavailable on this card and its declaration fails validation |
| Individual upstream member omitted / explicitly false | Both edge variants produce identical positive-membership lists |
| Entire upstream `block_occupancy` omitted | Edge raises `KeyError` |
| Entire wire `occupied_blocks` / `closed_blocks` omitted | Both codecs reject with `WireFormatError` |
| Valid empty OCC/CLOSED lists | Accepted; this does not certify physical completeness |
| Repeated occupied or clear snapshots at later tick times | Bits remain unchanged; no per-field source age or completeness bitmap is available |

A probe-only in-memory HW PLC used
`AUTH_25 := NOT (OCC_25 OR CLOSED_25 OR OCC_76 OR CLOSED_76)` with suggested
authority 3. Across nine ready controller steps, an empty snapshot passed 3;
each own/neighbor occupied/closed member forced 0, repeated neighbor membership
kept 0, and omission in a subsequent valid snapshot restored 3. SW's actual module
likewise replaced own 28 membership on omission; remote 150 never appeared on
GTC-02's card. This exposes membership semantics, not unsafe production movement.
An unknown name in a fixed edge mapping was filtered out; normal live edges learn
names from producer occupancy keys first, so that isolated case proves no normal-path loss.

Focused existing checks used project Python, offscreen Qt,
`PYTHONDONTWRITEBYTECODE=1` and `-m pytest -q -p no:cacheprovider`:
`TrackCtrlHw/tests/test_neighbor_inputs.py` passed **4 in 0.02 s** and, from
`TrackCtrlSW`, `tests/test_boundary.py::Wire` passed **5 in 0.03 s**.
The synthetic assertions also passed; the temporary entry point was
`/tmp/track-overflow-owner-diagnostics-20261025/input-completeness.py`.
The focused tests were agent-run. The orchestrator reviewed and independently
reran the synthetic probe, confirming authority sequence `3,0,0,0,0,0,0,3,3`,
the codec rejection/empty-list distinction and SW's 28/150 namespace boundary.

Static harness inspection separates retention from omission: rejected ticks keep
the producer's last completed outputs and log `TICK_REJECTED`
(`common/harness/core.py:423–445`); late or down modules hold the clock
(`core.py:535–544`). No rejected Track Model tick or live stale-producer sequence
was injected. Repeated synthetic snapshots cannot distinguish a stationary train
from stale physical information, and do not show that startup readiness is bypassed.

**Reusable boundary and retention diagnostics, 2026-10-25:** Source
`c4b3cce`, on the same `kevin-framework` environment above, adds
[input boundary checks](../common/harness/tests/test_input_owner_diagnostics.py)
and [bounded retention injections](../common/harness/tests/test_rejected_track_retention.py).
The earlier paragraph describes the historical static-only gap; the new injection
now observes it through the real Harness and `SystemEdges`. Fake producers reuse
the existing local-socket `_Run`/`_FakeModule` facilities. A documented test-only
adapter uses the runner's Train Model socket as an SW input consumer; it does not
run a physical or production Track Controller on that socket. CTC closures remain
an independent producer's output, separate from Track Model occupancy.

The sol subagent ran the checks; the orchestrator reviewed both files and directly
ran this affected set: **75 passed, 4 passed subtests in 7.72 s**. Local Qt sockets
required sandbox escalation. All ten new diagnostic cases passed within that run.
After tightening the rejection/disconnection event-order waits, the orchestrator
directly reran the retention file alone: **3 passed in 1.35 s**. Scoped Flake8
with `-j 1 --max-line-length=79` passed for the three new Green/input/retention
files. No production source changed between those checks.

```sh
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 "$PYTHON" -m pytest -q \
  -p no:cacheprovider common/harness/tests/test_input_owner_diagnostics.py \
  common/harness/tests/test_rejected_track_retention.py \
  common/harness/tests/test_harness_faults.py \
  common/harness/tests/test_harness_edges.py \
  common/harness/tests/test_hw_wayside_edges.py
```

The input cases reproduce the nine ready HW steps with authority
`3,0,0,0,0,0,0,3,3`, SW 28 versus unavailable 150, whole-field/codec rejection
versus accepted empty lists, repeated membership, and normal complete Track Model
output. The HW probe program exists only in memory; production PLCs are unchanged.
Additional agent-run checks used `"$PYTHON" -m pytest -q -p no:cacheprovider`:
from `TrackCtrlHw`, `tests/test_neighbor_inputs.py` passed **4 in 0.02 s**;
from `TrackCtrlSW`, `tests/test_boundary.py::Wire` passed **5 in 0.03 s**.

| Injection bound | Observed barrier and retained data |
| --- | --- |
| Rejected Track Model tick 3, release other reply, finish tick 4 | Exactly one `TICK_REJECTED`; tick 3 remains incomplete while another module's reply is pending. After that reply, tick 4's real SW edge inputs still contain OCC28 and independently sourced CTC CLOSED28. A new clear occupancy output commits only at tick 4 completion. No late/disconnect event. |
| Missing Track Model reply at tick 3, 0.3-s reply timeout | Last completed occupancy retained; completed ticks remain 1/2, clock held at 3 and Track Model named late. No rejection or disconnect. |
| Track Model disconnects at tick 3 | Last completed occupancy retained; tick 3 completes without the lost reply, and the down-module hold prevents tick 4. No rejection or late event. |

**Decision packet:** Braden and Harry must define completeness/freshness guarantees,
unknown-neighbor representation and cross-wayside namespace requirements, with
Landis for closure/release effects. Remaining gaps include live partial/stale
producers and the approved fail-safe response. Required validation after an owner
decision: both variants' edge/codec/namespace and authority checks, these three
distinct fault cases, relevant live producer sequences and real-board faults.
Synthetic repeated snapshots and retained data do not establish physical freshness,
movement safety, or Pi/USB acceptance; no new fail-safe policy is selected here.

**Requested decision:** Define who guarantees completeness, how unknown/stale
occupancy is represented and detected, and what PLCs should do when a required
neighbor is unavailable. Distinguish unavailable namespace, omitted members,
valid sparse clear sets and retained rejected-tick snapshots. Decide whether SW
needs remote approach inputs such as 150→28; HW adjacency is not automatically
present on SW cards. Review cross-wayside coverage and keep outputs owned by their
wayside. Coordinate any change across both variants, the harness and Landis where
CTC closure/release behavior is affected. No extension or fail-safe policy change
is authorized by these observations.

**Landis's answer (2026-10-25), closures:** CTC closures are set only in
maintenance mode, and only the CTC reopens them, in maintenance mode. The Track
Controllers have no authority over them. The CTC keeps the list of blocks and
switches it controls in maintenance and sends it. Before a Track Controller sets
a switch, or closes or opens a block, it checks that list. This extends the
truth entry `maintenance-closure-lock` (blocks only) to switches. The CTC
currently sends switch commands only while in maintenance mode and drops them
when it ends, so persistence of the switch list is for Landis to confirm. The
occupancy-completeness questions above stay with Braden and Harry.

Reply from Harry : Track model should be providing an updated view of block occupancy per tick in accordance with a physical system imo. The concept of stale block occupancy is purely simulation artifact. If a tick fails I am not sure if Track Controllers can communicate with each other or if they only communciate with CTC, this is an open question. 

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

**Landis's answer (2026-10-25):** The CTC must not dispatch trains into head-on
deadlocks. A train waits to be released toward the yard until that is safe, or is
routed around oncoming trains. The CTC side is implemented with
[CTC-1](#ctc-1-red-concurrency); the starter-input decisions stay with Harry.

Reply from Harry : Not sure if we are allowed to receive the train direction from CTC or if this violates the system at all. If we are able to, then sure. Switches default to normal. 

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

**Track Model owner's answer (2026-10-26):** Sales are time-based, not per tick. The
intended demand is about 12 tickets per simulated minute per station, which is what
the current default gives at the 0.1 s system tick. The per-tick probability will be
derived from `dt` so the rate holds at any tick length. The sales interface to the
CTC is unchanged. Whether each count is a delta or a running total (open in
`signals/ticket-sales`) is a separate decision.

**Implemented 2026-10-27:** `TrackConfig.tickets_per_minute` (default 12) replaces the
per-tick `ticket_probability`; each tick's chance is `min(1, rate × dt / 60)`, 0.02 at
0.1 s as before. A new test checks 11–13 a minute at both 0.1 s and 0.5 s ticks.

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

**Track Model owner's answer (2026-10-26):** B1 is a defect. Each tick the Track Model
will send the light ahead that faces the train's direction of travel, as the
`signal-aspect-ahead` entry describes, not only on the entry tick. Green 63→64 gets
the light guarding 63→64, not the one for the opposite direction. This replaces the
earlier note that a train sees the colour once on entry. The Track Controller owners
are asked to confirm the physical light placement (SW discrepancy C6) before the
code changes.

**Implemented 2026-10-27, at Kevin's direction ahead of Harry's C6 confirmation:**
signals sit at switches, one per switch at its point, named by the switch's ID
(Braden's TM-2 answer). Every tick each train gets the light ahead: the first switch
along its way, with the switches as set, that it comes onto from the point's fixed
side, where the light faces. A train trailing through from a leg does not see that
switch's light. Both Track Controllers already named signals by switch, so only the
Track Model and the harness device map changed; B1 is closed. Note for the Track
Model owner: the LAYOUT-1 answer put Red switch 9's light "on 10" (the old placement);
it now stands at the point, 9.

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

**Track Model owner's answer (2026-10-26):** The Track Model switches the heaters
itself, per D026, with no Track Controller command. The rule is a single threshold: a
section's heater is on when ambient temperature is at or below 0 °C, and off above it,
with no hysteresis. If the ambient temperature is missing or not finite, the heaters
keep their last state. Not yet implemented.

**Implemented 2026-10-27:** `TrackModel._switch_heaters`: on at or below 0 °C ambient
(`HEATER_ON_AT_C`), off above, no hysteresis, last state kept with no ambient. Heater
commands are accepted but not applied. Track Model suite: 316 passed.

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
