# Integration handover — Phase 6

2026-10-22. Work on `claude/quirky-fermi-sickg4`, for Iteration 3 full
system integration on 2026-11-12. This records implementation and measured
evidence, not normative truth. Phase 5 remains the baseline; its handover
records the simulated-Pi limits and the pending owner decisions.

**Status:** the review path is built and passes its manual/scheduled
station scenarios, including simulated Pis. Full acceptance is incomplete:
CTC multi-train questions remain and physical Pis have not been verified.

## 1. Scope and decisions

Kevin authorized reuse of Braden's real Green PLC routing pattern in the
Red integration test copies for every switch: CTC override, occupancy and
closure AUTO/WANT selection otherwise, reported-position lock while points
are occupied, and signals following the selected route. These remain test
copies for Braden's review. No automatic reversal is authorized. The
wayside split and immutable course data stay unchanged.

At least two trains per line must be exercised, without a hardcoded count
limit. Shared Pi plumbing is used for all modules with transport-specific
adapters. Real-Pi measurements precede the speed decision; Windows
packaging remains deferred. Hardware execution waits for module owners to
report a working Pi 5. The Linux build and external-directory simulated-Pi
smoke pass; physical USB and Windows delivery remain unverified.

## 2. Yard validation and owner review

The Track Model's exception to entry-only yard validation now applies only
to Red block 9. A malformed Green-63 yard exit is rejected; Green-57 still
requires its yard-return annotation. The unchanged course files load.

D028 retains Kevin's physical connection at section-C block 9 and the
instruction to preserve the given course data. Its `Unconfirmed
interpretation` distinguishes current reader geometry from Kevin's words;
the source-file edit was an earlier implementation choice. CTC's new
module changelog records `5d51051` and the hardcoded Red `to_yard` at 9 in
`ctc/track_layout.py:120–121`, for Landis's review.

The Red-9 geometry remains an assumption: point 9, NORMAL to 8, REVERSE to
yard, fixed side 10 and light on 10. No track JSON changed.

All seven Red switches now use the Green-style pattern. Kevin approved
"Approve shared read-only neighbor closure inputs" on 2026-10-22. The
existing neighbor occupancy mechanism now shares closures through the
same adjacency helper; line scoping and output ownership are unchanged.
Switch 27 can read `CLOSED_76` and protect/select its reverse route. Speed
caps, crossings and authority rules are preserved. The existing `RedLoop` helper verifies 9 … 16 outbound to
a station stop, then an explicit return request following 17 … 66 → 52 … 9
and one retirement event. The loop checks emergency brake and signal
pickup on every tick. This adds no second launcher and no train reversal.

## 3. Final validation and acceptance limits

All Python commands use `/home/kevin/ECE/Trains/.venv/bin/python` and Qt
checks use `QT_QPA_PLATFORM=offscreen` unless explicitly marked visible.

| Check | Evidence | Who ran it |
| --- | --- | --- |
| Shared neighbor input boundary | `python -m pytest TrackCtrlHw/tests/test_neighbor_inputs.py -q`: 4 passed, 0.02 s | Yard/routing agent |
| Red selection/controller/follower after closure extension | `python -m pytest TrackCtrlHw/tests/test_red_integration.py TrackCtrlHw/tests/test_controller.py common/harness/tests/test_green_follower.py -q`: 51 passed, 2494 subtests, 2.26 s | Yard/routing agent |
| Review, manual and scheduled process scenarios | 3 passed, 24.13 s | Orchestrator |
| Full shared Pi/recovery suite, final | 44 passed, 8.15 s | Orchestrator |
| Track Controller HW full suite, final | 89 passed, 50538 subtests, 33.35 s | Orchestrator |
| Shared fault selector wrapper | 9 passed, 20.88 s | Orchestrator |
| Red outbound and return | `python -m pytest TrackCtrlHw/tests/test_red_routing_loop.py -q`: 1 passed, 26.69 s | Yard/routing agent |
| Track Model focused layout/direction checks | `python -m pytest TrackModel/tests/test_green_direction.py TrackModel/tests/test_layout.py -q`: 59 passed | Yard/routing agent |
| Track Model full suite | 312 passed, 2.41 s, local IPC enabled | Orchestrator |
| Track Controller SW full suite | 213 passed | Orchestrator |
| CTC Office full suite | 261 passed | Orchestrator |
| Train Controller SW / HW suites | 24 / 23 passed | Orchestrator |
| Train Model full suite | 879 passed, 13 skipped; known timing-sensitive test passed | Orchestrator |
| Train Controller `main.py --check` | Zero QML warnings and behavior problems | Orchestrator |
| Complete harness, including round-trip and multi-train opt-ins | 185 passed, 3 failed, 497 subtests, 296.77 s; failures are the three bounded owner questions below | Orchestrator |
| Green round trip / Green two-train schedule | Five round-trip tests and Green two-train acceptance passed within the complete harness run | Orchestrator |
| Final frozen external-directory smoke | 20 s, exit 0; G1/R1 added, both lines ready, HELLO bundle hashes matched, seven module exits 0 and HARNESS_STOPPED; no fault events | Orchestrator |
| Shared utils | 86 passed, 43 subtests | Orchestrator |
| Final scoped flake8 | All 18 changed Python files pass with `-j1 --extend-ignore=N815`; exception covers Qt signal naming | Orchestrator |
| Final Pi source typing | Seven changed Pi source files pass the scoped mypy check | Orchestrator |

The final harness command enables both slow scenario groups:

```
QT_QPA_PLATFORM=offscreen TRACK_OVERFLOW_ROUND_TRIP=1 TRACK_OVERFLOW_MULTI_TRAIN=1 /home/kevin/ECE/Trains/.venv/bin/python -m pytest -q common/harness/tests
```

Its only failures were the mixed two-train, mixed three-train and
Green-only three-train scheduled acceptance probes. The successful review
station scenarios and Green two-train scenario do not erase those failures.
[Scenario evidence](review-scenario-evidence-2026-10-22.md) records the bounds
and observations. In mixed runs, maximum simultaneous Red count remained
one; the real CTC scheduler reserves the shared Red 9 … 66 route zone.

Green-only three-train validation reached three active trains, but at the
2,400 simulated-second bound G1 had retired while G2 remained at 65 and
G3 at 64. Static inspection found that `_release` reserves both upcoming
zones 77 … 100 and 1 … 28 before the departure from 65. This is an observed
stall and CTC owner question, not proof of permanent deadlock. No preceding
separation, exclusive-authority, emergency-brake or pickup-failure assertion
failed in those bounded probes. Owner arbitration and scheduler rules were
left unchanged.

The frozen smoke establishes startup, hash agreement, release events and
clean exits from outside the checkout. It does not independently establish
frozen station stops or multi-train acceptance. Physical Pi testing remains
pending.

## 4. Measurement conditions

The present host is `kevin-framework`, Linux, with an Intel Core Ultra 5
325 and eight online cores (one thread per core), maximum reported clock
4.5 GHz. The user-supplied Phase 5 fix-check figures in the Phase 6
prompt describe a four-core cloud run reaching about 3.6–4.3x when 10x was
requested, with about 2 s startup, versus the earlier framework result of
9.69x with about 0.5 s startup. The final framework samples reached
9.16x headless and 8.36x with Wayland windows, with 0.50–0.61 s startup. These are not paired benchmarks:
host/CPU, process startup, scheduling, workload, profiling and display
circumstances differ, so their separate contributions cannot be quantified.
They establish no Pi performance inference. The Phase 0 four-core 2.8 GHz
Xeon/stub table is a separate historical measurement; it does not identify
the cloud fix-check machine.

The final runs on 2026-10-22 at 12:24:45–12:26 EDT used committed
`5223f1f`, including routing/closure commit `16a64b8`. CPU pressure before
them was `some avg10=0.00`, `avg60=0.00`, `avg300=0.00`; the local audit
had finished and no deliberately concurrent heavy job was run. These
conditions do not establish a fully isolated benchmark. Desktop variables
were `DISPLAY=:2` and `WAYLAND_DISPLAY=wayland-0`. The Wayland runs
launched the harness and module windows on that desktop. No screenshot or
visual inspection verified their appearance or responsiveness.

The orchestrator ran four sequential 15 s samples. Commands (each speed
is a separate invocation):

```
QT_QPA_PLATFORM=offscreen /home/kevin/ECE/Trains/.venv/bin/python -m common.harness.measure --system --test-pi process --seconds 15 --speed 1
QT_QPA_PLATFORM=offscreen /home/kevin/ECE/Trains/.venv/bin/python -m common.harness.measure --system --test-pi process --seconds 15 --speed 10
QT_QPA_PLATFORM=wayland /home/kevin/ECE/Trains/.venv/bin/python -m common.harness.measure --system --test-pi process --window --seconds 15 --speed 1
QT_QPA_PLATFORM=wayland /home/kevin/ECE/Trains/.venv/bin/python -m common.harness.measure --system --test-pi process --window --seconds 15 --speed 10
```

Xcb could not start because its cursor dependency was unavailable; visible
runs therefore used the existing Wayland desktop. They dispatch the measurement's
standard one-train workload, not the multi-train acceptance scenario.
No performance optimization was made for these samples.

| Front end | Requested | Completed / due | Achieved | Mean / median / p95 / p99 / max (ms) | Startup | Harness CPU | Dropped backlog / late replies |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Headless, offscreen modules | 1x | 151 / 150 | 1.01x | 20.38 / 18.13 / 30.72 / 35.69 / 37.98 | 0.58 s | 6% | 0 / 0 |
| Headless, offscreen modules | 10x | 1376 / 1502 | 9.16x | 10.56 / 9.06 / 23.10 / 31.19 / 90.15 | 0.50 s | 27% | 100 / 0 |
| Wayland window launch | 1x | 151 / 150 | 1.01x | 22.34 / 21.89 / 33.32 / 35.49 / 37.74 | 0.60 s | 8% | 0 / 0 |
| Wayland window launch | 10x | 1260 / 1507 | 8.36x | 11.53 / 10.32 / 24.41 / 30.01 / 65.98 | 0.61 s | 29% | 200 / 0 |

Both 1x runs pass the measurement's 99% completion criterion; both final
10x runs fail it. Headless 10x ends 126 ticks below due, with 100 explicit
dropped-backlog ticks; Wayland 10x ends 247 below due, with 200 explicit
drops. The remaining deficits of 26 and 47 are unfinished due ticks, not
additional reported drops; they do not identify an exact in-flight state.
No run reported a late reply. Reliable simulated 10x remains open. No
performance optimization or profiling was authorized or performed in
Phase 6, and the speed decision still waits for real-Pi measurements.

The initial 11:10 EDT checkpoint reached rounded 10.00x in headless and
Wayland runs, but preceded the final all-seven-switch/neighbor-closure
implementation. A local audit was also running then. Those initial samples
are historical and do not establish final-revision performance. The final
rerun does not causally isolate source changes, CPU state, scheduling or
general variability. Phase 4's 5.1–5.8 ms means, Phase 5's final
10.00–10.27 ms means, and the current 10x means of 10.56/11.53 ms are
separate workloads/samples; none establishes real-Pi performance.

The old Phase 5 table had zero explicit dropped-backlog events, but its
10x runs ended 47 and 88 ticks below due. Those unfinished ticks were not
reported as dropped-backlog events. Current results must distinguish
completed/due ticks, dropped backlog and late replies.

The Green follower snapshot reproduces the open owner issue: with a head
on 77 bound for 101 and switch 76 already reverse, a follower at 75 has
one block of authority and a zero-authority preload at 76. At 76 it has
zero authority. Once the head clears to 101, occupancy on listed block 76
holds the switch reverse for all five observed ticks. This is a seeded
boundary observation, not a physical multi-train-loop claim. The regression
reuses `_Line` from the SW starter tests; CTC/SW owner rules are unchanged.

## 5. Open questions and remaining work

| Question or requirement | Owner / next evidence |
| --- | --- |
| Shared neighbor closure inputs | Approved by Kevin; implemented and verified by final HW suite and frozen bundle refresh |
| Red test programs and exact Red-9 leg geometry | Braden, Track Model owner: review copies and reader assumptions |
| SW vital-layer implementation of confirmed PLC-only policy | Harry Tye, SW owner: separate follow-up remains open |
| Occupied block missing from PLC input set counts as clear | Braden, Harry: input-completeness and cross-wayside contract review |
| Green 75/76 follower while a train stands at 77 for 101 | Harry, Landis: record scenario and review owner behavior; do not change their rules |
| Green three-train completion | Landis/CTC: observed stall at 65/64 through 2400 simulated seconds; reservation/progress review, without a permanent-deadlock claim |
| CTC Red concurrency / scheduling | Kevin: "Note this as an open question for ctc"; current Red route zone constrains simultaneous dispatch; do not change scheduler rules |
| Ticket sales rate, light-ahead B1, heaters, Green starter decisions | Existing module owners; unresolved questions carry forward |
| Real 10x performance, USB buffering and journal persistence | Real Pi 5 provisioning and measurements; speed decision waits for them |
| Windows packaging | Deferred by Kevin |
| Truth promotion | 34 branch proposals plus 4 from PR #43 await human review; agents do not promote |

Only humans promote or delete inbox proposals. D033 proposes the authorized
Red test routing policy; D034 proposes the Phase 6 readiness scope; D035
proposes the approved shared neighbor closure policy. These
are proposals, not accepted truth. No PR has been opened.

## 6. Shared tooling and duplication avoided

The review process scenarios reuse the existing system specification and
acceptance runner. The Red round trip reuses `RedLoop`; the Green follower
snapshot reuses the SW `_Line` helper. Red PLCs reuse Braden's Green
AUTO/WANT/LOCK pattern. Neighbor occupancy and closure names/images share
one adjacency helper rather than separate neighborhood logic.

[Pi owner setup](pi-owner-setup.md) and
[bring-up checks](pi-bringup-checks.md) cover the shared production
`common.hw_link` agent, transport, provisioner, bundle manifest, echo/replay
probe and fault selector. The selector runs the existing acceptance tests;
it does not implement a second fault harness. Agent hashes are verified
at HELLO. Offline bundles include the shared protocol/core source and
checksums; hardware USB identity and service installation remain owner
steps. The same `common.harness.measure` entry point measures simulated
and hardware runs.

The Pi agent reported twelve software-only echo combinations: both modules,
process/pty, 1/10/20 KiB, each 100 payload-checked transactions at requested
100 Hz. Four recorded-workload replays each contained 658 Red STEP requests,
plus existing loads/gains ACTIONs. All identities matched and none was
rejected. Their diagnostic timings and recording provenance are tabulated
in the bring-up checks; these samples were not isolated benchmarks and do
not establish real USB performance. No physical Pi was verified.

The Linux build uses [`utils/build_linux.sh`](../utils/build_linux.sh), the
shared launcher and the source manifest. The final post-closure build ran
from an external `/tmp` directory for 20 seconds with simulated Pi
processes and exited 0. Its event log records both lines ready, G1/R1 added,
matching HELLO bundle hashes, all seven module exits at code 0 and
`HARNESS_STOPPED`, without fault events. That smoke has the narrower scope
stated in section 3; source station tests provide the station-stop evidence.

## 7. Commits

| Commit | Scope |
| --- | --- |
| `7af402a` | Red yard validation guard, Green rejection regressions, owner changelogs and D028/D033/D034 proposals |
| `ede5c89` | Shared Pi transport, provisioning, bundle hashes and bring-up tools |
| `16a64b8` | All Red switch routing, shared neighbor closures, D035, follower observation and Red return tests |
| `5223f1f` | Approved CLI passthrough, review scenarios, Linux build recipe and scenario evidence |
| `25cc37a` | Phase 6 evidence, performance limits and CTC review questions |
| `d8b175a` | Merge the finalized remote Phase 6 prompt and four pending proposals, preserving both histories |

The orchestrator inspected `git show --stat` for every commit above and
independently ran the final checks attributed to it in section 3. The
Pi-only echo/replay timings are explicitly the Pi agent's report. No agent
changed branches or opened a pull request.

## 8. Remote reconciliation

Kevin authorized inspection and reconciliation of the remote branch.
Normal merge `d8b175a` preserves its two commits, `caf72da` (final Phase 6
prompt) and `8300977` (four proposals), alongside the five local commits
listed above. There were no conflicts or source, UI or test changes.
Validated runtime behavior therefore remains unchanged: the complete
harness result is 185 passed and three owner-question failures; final
requested-10x measurements remain 9.16x headless / 8.36x with Wayland
window launches. No additional runtime checks were required for this
prompt/proposal-only reconciliation. The orchestrator verified the runtime
and test diff from `25cc37a` is empty and the expected bundle hash still
matches the final frozen manifest:
`31fee16e8225461b3cab92baaf77bb059ad766cd7290ac88de97b077441893c0`.

The inbox now contains 34 proposals on this branch plus four from PR #43.
Short decision IDs overlap and require human review before promotion:

| Short ID | Remote canonical key | Local canonical key | Review needed |
| --- | --- | --- | --- |
| D033 | `D033-red-test-plc-switch-routing` | `D033-red-integration-plc-routing` | Overlapping Red routing policies; reconcile their scope and content |
| D034 | `D034-authoritative-green-plc-programs` | `D034-phase6-integration-scope` | Different entries reuse the same short ID |
| D035 | `D035-pi-paths-share-one-implementation` | `D035-shared-neighbor-closures` | Different entries reuse the same short ID |

All canonical filenames are distinct. No proposal was edited, renamed,
deleted or promoted during reconciliation. Human review must resolve the
short-ID ambiguity before promotion; no prefix is treated as an already
accepted decision.
