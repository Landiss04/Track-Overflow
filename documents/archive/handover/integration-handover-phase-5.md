# Integration handover: Phase 5 software and simulated Pis

Written 2026-10-21; corrected 2026-10-22 on `claude/quirky-fermi-sickg4`, continuing the Phase 4
handover. Kevin authorized steps 1–9 and 13; no functional Pi was available.
The authoritative session prompt was attached by Kevin; the requested
`documents/phase-5 prompt.md` was absent at discovery. The older
`integration-next-session-prompt.md` is not this session's Phase 5 scope.

## 1. As built and verification boundary

Kevin authorized the software work in the attached Phase 5 session prompt,
with no functional Pis available. Software steps 1–9 and documentation
step 13 are complete against explicit simulated Pis. Real hardware steps
10–12 have not started. R93–R107 preserve the decisions. The two
source merges are `8407baf` (PR #43 source branch, GitHub PR unchanged) and
`2335197` (Braden's WP2 design). `f27ba4e` repairs the Green sample cuts,
adds Red integration test databases/PLCs and aligns the Red yard readers.
`cb8a326`/`d4db358` supply HW mappings, mixed-line routing and deferred replies.

**Red topology and safety.** The three test databases cover 76 blocks exactly
once: Red-1 has 1–24/73–76, Red-2 has 25–45/67–72, and Red-3 has 46–66.
9 and 75 share Red-1. Files say they are integration test copies, not
Braden's, for him to replace or approve. All rows include `next_blocks`.
Kevin superseded K2's data edit on 2026-10-22: "the track is a given data
point and can not be modified". `5d51051` restores `TrackModel/red_line.json`
byte for byte to before `f27ba4e` (SHA-256
`42afbb5505d4cb16e9efb8a3d995409973cd53fdafed4104be997a52c123ca33`).
The integration territory copy preserves the same course rows. The readers
interpret the yard at section-C block 9 and remove the stale yard adjacency
at 75. Assumption for the Track Model owner and Braden: point 9, NORMAL to
8, REVERSE to yard, fixed side 10 and light on 10. A yard release trails
through 9 toward 10. The original `75-yard` text remains unchanged.
HW territory,
Track Model, harness devices and SW topology readers agree. No SW vital
logic changed. Kevin subsequently confirmed the no-vital policy covers SW
too; its existing vital implementation is a deferred owner follow-up.

PR #43 has dual PLC channels and five-bit speed input/output, but no
read-only generated vital PLC block. The Red programs contain speed caps,
separation, closures, switch correspondence/occupied locking, signals and
crossings. Switches remain NORMAL at rest. Crossings 11/47 activate for own
or either-neighbor occupancy. Read-only `OCC_n` inputs extend across declared
neighbors without duplicating output ownership. The full Red occupied set
must reach the mapping; missing set membership has the existing meaning
clear, and a disconnected harness module stops clock advancement. The WP2
planned generated vital block remains for Harry and Braden to confirm;
K3b takes precedence for this implementation.

**Mixed-line run.** In the seven-core in-process scenario, R1 is released at
9 and traverses 9–16, with each module receiving the train one tick apart.
There is no emergency brake or signal-pickup latch, and Green G1 continues
under its SW controller. An onward order is issued immediately after the
Red doors open: first open tick 657, close tick 1107, exactly 45.0 s later.
Red return is not complete: the return request is accepted after the dwell,
R1 continues to 66 and is held by the NORMAL-only route at switch 52.
After 600 simulated seconds it has not retired at 9; no train-left-track,
removal, emergency-brake or pickup-failure event occurs. The return
diagnosis is covered by
`CTC-Office/tests/test_red_return.py`: arriving at 16 from 15, the route
continues 16 → 17 … 66 → 52 … 9. The shorter 16 → 15 … 9 path reverses
at 16, which truth `arbitration/no-automatic-reversal.md` forbids the CTC
Office to do automatically. CTC two-way zones cover the outbound/return
conflict; they do not command a reversal or align a switch. At 52 the
return leg from 66 requires REVERSE; outbound toward 53 requires NORMAL.
A correct return therefore needs Braden's real switch-routing programs,
or a separate dispatcher-controlled reversal decision. Kevin said "wait
for real" for the Red PLCs, so the test programs remain unchanged and
this return remains open.

**Pi link implementation and verification boundary.** `common/hw_link/`
contains a Qt-free Pi agent, strict newline framing and HELLO/ACTION/ACK/VIEW,
remote adapters, event-driven QSerialPort, explicit local QProcess agents
and Linux pty transports. The host's reply is deferred until the Pi answers.
USB discovery uses the assigned serial plus VID/PID, with HELLO module/version
validation and no production fallback. Agents run no clock. The current
recovery code and tests exercise reply caching, durable journal reconstruction,
loads, pending STEP replay, reconnect logging and gain replay policy.

The durable journal stores full accepted requests and replies per session;
the session cache/history grows with the run. Cold restart reconstructs the
core from that history, so replay cost grows too. The earlier in-process
core timings below
exclude disk synchronization, serial transit and replay. The October 22
process measurements include the existing durable journals and fsync.
A real Pi power-loss
and long-session journal test remains part of later hardware acceptance.
The relay implements the running-loss/paused-loss gain replay policy. Kevin
subsequently approved authoritative CLOCK_STATE metadata on the harness-to-HW
host channel (R107). Commit `9325523` implements that explicit protocol/core exception. The
orchestrator independently reran 34 focused clock/protocol/link/channel
checks with 22 subtests and the full Pi suite: 31 passed at `baed0cd`.
CLOCK_STATE has a strict schema and a pause notification never runs STEP.
Gain replay uses the current armed train roster, including rapid retirement/
ID reuse: running-loss replay is distinct from paused-loss non-application.

**Simulated cost groundwork (K9).** One 1,107-tick mixed run measured module
step plus wire encoding/compact JSON round-trip, without serial or windows:

| Module | Mean / p95 / maximum (ms) | Mean / maximum output bytes per tick |
| --- | --- | --- |
| Track Controller HW | 1.3453 / 1.3828 / 1.5307 | 12,410.48 / 12,428 |
| Train Controller HW | 0.02863 / 0.03258 / 0.04961 | 219.80 / 241 |

The two maximum outputs total 12,669 bytes/tick, about 1.27 MB/s at 100
ticks/second, before inputs, framing, VIEW traffic, journaling and recovery.
This sizes the workload; it establishes no actual USB latency or Pi 10x
feasibility result. G-CLK-6 remains open for the USB and Windows measurements.

## 2. Original October 21 software verification

 The HW baseline after merges
was 73 passed/48,074 subtests and one known missing-`next_blocks` failure;
after the repair it is 80 passed/50,506 subtests. The orchestrator independently
reran that full HW suite and 14 mapping/mixed-loop/deferred-reply tests.
The delegated post-default harness+utils run reports 252 passed, 5 skipped
and 540 subtests in 99.69 s (harness 166 passed/5 skipped; utils 86 passed).
The broad module suites report CTC Office 259/284 subtests; Track Controller SW 213/16;
Track Model 309; Train Controller 23/18; Train Model 879 passed/13 skipped.
The Train Controller `main.py --check` exits zero, with zero QML warnings and
zero behaviour problems. The post-default opt-in Green round trip passes all five checks in 40.56 s.
The final independent slices below include the real-process Pi acceptance.

**Host/default acceptance.** The seven-real-process tests report
three passing scenarios: clean run, injected disconnect and injected reboot.
They assert Green/Red routes, seven zero exits and empty stderr. Journal
evidence records each STEP once, the repeated pending tick is served from
cache, and the harness logs REPLY_LATE followed by LATE_REPLY_RECEIVED.
The orchestrator independently checked these acceptance slices; overlapping
checks are not summed into a new suite total:

| Independent rerun | Result |
| --- | --- |
| Final default-tree faults, launcher arguments and all-seven-process clean/drop/reboot | 27 passed, 7 subtests, 33.42 s; strict empty stderr |
| Full Pi protocol/transport/recovery/window suite | 31 passed, 7.76 s |
| CLOCK_STATE schema, initial/change state, link and Pi channel | 34 passed, 22 subtests, 4.06 s |
| Full Track Controller HW | 80 passed, 50,506 subtests, 4.61 s |
| Mixed route, mappings and deferred replies | 14 passed, 4.62 s |


Kevin approved the concrete CLOCK_STATE exception to the otherwise unchanged
harness protocol/core. It supplies authoritative initial/change clock metadata
to HW hosts; the relay latches it at loss before late-reply timeout pauses the
clock. K11 and the production-default patch are now authorized. CLOCK_STATE is
implemented in `9325523`, and the final gain-cache/armed-roster behavior
is verified in `baed0cd`, including rapid train ID reuse. Both HW variants
are now real modules by default. `--test-pi process` or `--test-pi pty`
explicitly selects development agents; `--stubs-only` remains seven stubs.
Production hosts wait for their USB identities with no fallback. The final
post-default broad regression and Green round trip pass as recorded above.

**Static checks at the original October 21 checkpoint.** The original
claim that all 15 Pi Python files passed mypy was incorrect: the October
22 independent check found five errors (transport at 71/194/199, relay at
28, host at 104), including a real dict-versus-Mapping callback mismatch.
The correction and current verification are recorded below. The original
nine-file harness type check had one preexisting
`common/harness/app.py:106` Qt application argument mismatch; the other
eight checked files are clean. That unrelated UI-facing annotation was not
changed, and this is not a claim that all repository type checks are green.

**Proposals and deferred work.** Commit `17beefc` files five new full proposals
for K2, K5, K6, K7 and K11. Two further full proposals record the confirmed both-variant K3b policy
and approved CLOCK_STATE exception. This branch's inbox has 27 proposals,
plus four
owner-source proposals brought in under PR #43's original branch directory.
All await human promotion. On October 22, Kevin authorized amendments to
D028, D031 and the both-variant PLC-only proposal (`4b9536b`). D031 and
PLC-only provenance now quote his "yes" of 2026-10-22. The two D019 proposals
remain in explicit conflict, with Harry Tye as resolution owner and Braden
responsible for the HW interpretation; Braden's proposal is untouched.
D028 records the immutable course data decision without turning switch-leg
assumptions into normative facts. No proposal was deleted. Pi owner
setup is documented in `documents/pi-owner-setup.md`, untested on hardware.
Steps 10 (USB measurements), 11 (owner Pi provisioning) and 12 (packaging/
Windows builder/separate installs) have not started.


## 3. Kevin's decisions of 2026-10-21

Kevin authorized steps 1–9 and 13 in the attached session prompt. K4 includes
Braden's answers relayed by Kevin. Quotes preserve their wording. These
implementation rulings do not promote proposals to `truth`.

| # | Source | Kevin's words | Effect |
| --- | --- | --- | --- |
| R93 | K1: Go and order | Steps 1–9 and 13 now; "no hardware is functional yet so that cant be tested" | Build against simulated Pis; steps 10–12 remain out of scope. |
| R94 | K2: Red yard (Phase 3 Q5) | "block 9 physically connects to the yard via a switch … note that block 9 is in section c" | Kevin confirmed on 2026-10-22: "the track is a given data point and can not be modified". Kevin established the physical yard connection at section-C block 9. Readers interpret the stale adjacency while preserving the given bytes; that interpretation and detailed switch legs remain owner assumptions. The earlier source-file edit was an implementation choice, not Kevin's instruction. |
| R95 | K3: PR #43 | "merge into this branch not devlopment leave the pr unmerged" | Merge the source into this branch with a merge commit. Do not merge/close/comment on the GitHub PR. |
| R96 | K3b: Vital layer | "the vital layer has been removed. everything is done by the plc code." | The no-vital policy covers both HW and SW, explicitly confirmed by Kevin: "yes", 2026-10-22. All safety belongs in PLC programs. Existing SW vital implementation is left unchanged under the original implementation scope, and is an owner follow-up. |
| R97 | K4: Red databases/programs, Braden relayed by Kevin | "use test only copies"; "it should be divided in any way that work, maybe 3 waysides. That's fine to keep 9 and 75 in the same wayside."; switches "yes"; crossings "Yes"; "Check the wp2/ branch that braden made. Many updates are found there as well." | Use about three integration test waysides, all 76 blocks once, 9/75 together. NORMAL starters, crossings 11/47 active for own/either-neighbor occupancy; take safety/speed-cap design from WP2. |
| R98 | K4b: WP2 design | The wp2/ branch has "many updates" | Merge `origin/wp2/TrackCtrl-HW-design` (f590f41) separately. Follow Braden's core-on-Pi/host-window split unless a ruling conflicts. Dual channels and five-bit speed exist in PR #43; the generated read-only vital PLC block does not. K3b puts safety in test programs; Harry confirms the planned vital block. |
| R99 | K5: Pis and USB identity | "Pi 5 set up by module owners. assign the both usb ident strigns" | Assign manufacturer/product/serial/VID:PID per module; owners provision the Pis. Write setup instructions without hardware execution. |
| R100 | K6: Pi-link additions | "accept" | Host-to-Pi HELLO (protocol/module/version/hash/session), ACTION/ACK before the next STEP, VIEW at most every 100–200 ms; harness protocol unchanged. |
| R101 | K7: Unplug or reboot recovery | "approved" | Hold the reply; reconnect by identity, redo HELLO, replay loads, re-send pending STEP, log stages. Pi caches `(id,tick)` and never advances that STEP twice. |
| R102 | K8: Pi missing at launch | "the whole clock should wait this will never happen" | No fallback. Missing Pi holds the clock; simulated agents require explicit development/test selection. |
| R103 | K9: Pi capacity at 10x | "agreed test when implemented" | Hardware USB/10x measurement is step 10 later. Record simulated output bytes/core time as groundwork only. |
| R104 | K10: Windows builder/separate installs | "kick this down the road" | Deferred; no Windows builder, separate-installer or packaging claim. |
| R105 | K11: Gains after reboot | "they should never loose connection mid run but add logic to check if connections are lost while the clock as running and if they are lost while the clock is running then the gains should be resent" | Re-send engineer gains only after a loss while running; no automatic gain application after a paused loss (D024). Log both. Kevin later explicitly approved the CLOCK_STATE exception (R107); implementation and integrated recovery checks follow that approval. |
| R106 | K12: Window Python | "any ui changes require permission" | No additional QML or Python-behind-window changes without permission. Use adapters through existing controller/fleet constructor parameters. K3 authorizes the existing owner-authored UI changes in the merge itself. |
| R107 | K11 clock metadata follow-up | Kevin explicitly approved the prepared CLOCK_STATE exception: "yes", 2026-10-22. | Add authoritative initial/change clock metadata on the harness-to-HW-host channels. Latch the state at Pi loss before timeout pause; verify running-loss gain replay and paused-loss non-application. |

## 4. Open questions and owner review

| Item | Owner | State / next action |
| --- | --- | --- |
| Red-9 NORMAL leg and leftover `75-yard` text | Track Model owner, Braden | Physical connection to section C block 9 is settled. Point 9/NORMAL to 8/REVERSE yard/fixed side 10/light on 10 is an explicit implementation assumption; the course file and original switch text are preserved. |
| Red test copies | Braden | Replace or approve the three exact-cut databases and PLCs. |
| WP2 generated vital block and variant PLC differences | Braden, Harry Tye | Dual channel exists; generated vital PLC does not. HW K3b puts safety in test programs. |
| SW implementation of confirmed K3b policy | SW owner, Harry Tye | Policy scope is confirmed for both variants. Existing SW vital implementation remains under the original session scope; remove/migrate it in a separate owner follow-up. |
| Cross-wayside occupancy | Braden, Harry Tye | Read-only neighbor OCC is exposed; missing occupied membership still means clear. Review the extension and full-line mapping assumptions. |
| Red return and turnback | Braden, Track Model owner, Landis | Return from 16 follows 17 … 66 → 52 … 9 and needs REVERSE at 52; outgoing 52 → 53 needs NORMAL. Short 16 → 15 return is an automatic reversal forbidden by truth. Wait for Braden's real programs or an explicit dispatcher reversal decision. |
| K11 host clock-state path | Integration | CLOCK_STATE exception explicitly approved (R107), implemented in `9325523`; full Pi suite (31) and focused clock/channel checks (34) pass. Running/paused replay policy and rapid train ID reuse are covered. |
| USB/power/10x/journal persistence | Module owners, Kevin | Actual Pi tests have not started. Final simulated 10x reaches 9.69x headless / 9.42x offscreen window; reliable 10x remains open. Journals grow through a session and cold replay cost grows with history. |
| Earlier owner questions | Respective owners | All open questions in the earlier integration summary remain unless explicitly resolved here, including ticket rate, light-ahead B1, heaters and Green starter/follower decisions. |

## 5. Commit checkpoints

| Commit | Change |
| --- | --- |
| `8407baf` | Merge PR #43 source (30 changed paths, +1,690/−840). GitHub PR remains unmerged. |
| `2335197` | Merge WP2 design (32 paths, +2,150). |
| `cb8a326` | HW boundary mappings, mixed-line routing, deferred replies and Red loop. |
| `f27ba4e` | Green repair, Red test databases/PLC, four reader agreement and neighbor occupancy (18 paths, +2,412/−62). |
| `17beefc` | Five new full-entry truth proposals (5 paths, +141). |
| `d4db358` | Typed mapping result and core API documentation. |
| `daaa3e7` | Pi agent, transports, host relay and remote adapters; focused protocol/recovery/window tests. |
| `78c470c` | Compound window action ordering ahead of STEP and raw-tty reconnect verification. |
| `9325523` | Approved CLOCK_STATE metadata and initial/change notification to HW hosts. |
| `8d15a69`, `c39a070` | Pi handshake/session and callback lifecycle hardening; seven-process system coverage. |
| `baed0cd` | Gain replay/cache follows current armed roster, including rapid retired-ID reuse. |
| `05369a5` | Stop fault-test fake-peer timers before socket teardown; no product or assertion relaxation. |
| `5d51051` | Preserve course Red bytes; align all yard readers and CTC metadata; test switch-dependent return without reversal or PLC routing. |
| `4b9536b` | Owner changelogs and the three authorized proposal corrections. |
| `6797a3a` | Explicit Pi measurement transport, startup discovery events, typed callbacks and approved constructor injection. |
| `02c2d7a` | Clean Phase 5 test formatting. |
| `c9498e4` | Bound periodic Pi VIEW traffic to the approved 200 ms cadence. |
| `1013fb2` | Wrap the approved state-factory expression to satisfy production flake8. |
| `f465c99` | Both HW variants real by default; explicit process/pty test agents; unchanged stubs-only mode. |

## 6. October 22 correction and revalidation

Kevin approved the exact `TrackCtrlHw/ui/app.py` constructor change:
"Approve this exact constructor change". `6797a3a` adds the optional
keyword-only `state_factory: Callable[[], TrackControllerState] | None`
and constructs the existing state with `RemoteTrackController` in place
of the local core. The window's state is established before QML binding;
the host no longer swaps it after construction. No QML changed. Kevin's
SW-vital-layer answer was "Keep it open for separate follow-up".

`measure --system --test-pi process|pty` explicitly passes the chosen test
transport to both HW modules; omission keeps waiting for real Pis (K8).
System measurements load the Red test starters. Startup events name each
HW module and sought K5 identity, immediately and every five seconds,
including zero/multiple matching ports. The harness forwards these events
before READY while retaining its readiness barrier.

**Current static checks.** The orchestrator independently reran mypy
with `--explicit-package-bases --disallow-untyped-defs
--follow-imports=silent --ignore-missing-imports` on these 16 production
files: `common/hw_link/*.py`, harness `core.py`, `supervisor.py`,
`measure.py`, `track_devices.py`, and utils `module_link.py`, `harness_protocol.py`: success.
This is an explicit production-file scope. Checking the whole hw_link
directory including tests with the same no-untyped-defs rule reports
61 missing-annotation errors; test typing is not claimed clean.
The existing harness `app.py` mismatch is outside the changed-file check.

Production flake8 and the four Phase 5 harness test files pass `flake8 -j1`
with `--extend-ignore=N815` for Qt signal names in the orchestrator's rerun; `02c2d7a` cleans test E501/E402/N802 formatting
without changing assertions. The Red reader/data agent separately checked
all its changed Python files with `flake8 -j1`: clean.

**Current regression evidence.** The orchestrator independently reran all
Pi-link tests, the new startup diagnostics, and the three real-process
G1/R1 clean/disconnect/reboot scenarios: **44 passed in 34.64 s**.
The module agent ran the full suites separately, in sequence:

| Module | Result |
| --- | --- |
| Track Controller HW | 80 passed, 50,506 subtests, 4.15 s |
| Track Controller SW | 213 passed, 16 subtests, 10.49 s |
| Track Model | 310 passed, 2.48 s |
| CTC Office | 261 passed, 284 subtests, 21.76 s |

The orchestrator also independently reran the remaining broad suites:

| Area | Result |
| --- | --- |
| Harness + utils | 260 passed, 5 skipped, 540 subtests, 96.01 s |
| Train Controller SW | 24 passed, 0.05 s |
| Train Controller HW | 23 passed, 18 subtests, 0.16 s |
| Train Model | 879 passed, 13 skipped, 40.06 s |
| Opt-in Green round trip | 5 passed, 37.04 s |

The supported `Train-Ctrl_HW/main.py --check` reports zero QML warnings
and zero behaviour problems. The SW `TrainController/main.py` does not
support this self-check flag.

The HW suite's first sandbox attempt had five socket-startup failures
(`Operation not permitted`), then passed in full with local IPC available.
The orchestrator independently confirmed the pre-`f27ba4e` source hash and
reran focused Red agreement/retirement/route checks (HW six tests with
2,432 subtests, Track Model 20, CTC two). No automatic reversal or
test-program Red switch routing was added.

**End-to-end profile.** Instrumented process runs reached only 4.62–5.04x,
with 19.37–21.12 ms mean round trip and 200–201 slipped ticks in about
five seconds. Profiling itself materially changes the workload: the
earlier unprofiled headless measurement reached 10.00x; the final
200 ms VIEW-cadence run below did not reproduce that result. These inclusive per-call
timings come from the same instrumented host/agent run (Track host
`process-1767570.pstats`, Track agent `process-1767610.pstats`, Train agent
`process-1767602.pstats` in `/tmp/recoveryprofile/`). They locate work; they
are not additive critical-path latencies:

| Process / operation | Profiled mean per call |
| --- | --- |
| Track HW agent STEP (254 calls) | 8.101 ms |
| Track HW agent VIEW (55 calls) | 3.758 ms |
| Track HW journal record, including fsync | 0.18385 ms |
| Track HW fsync syscall alone | 0.001924 ms |
| Track HW JSON encode / decode | 0.29475 / 0.33089 ms |
| Track HW pipe write | 0.016652 ms |
| Train HW agent STEP | 0.05447 ms |
| Train HW journal record, including fsync | 0.08703 ms |
| Train HW fsync syscall alone | 0.001610 ms |
| Train HW JSON encode / decode | 0.04057 / 0.05909 ms |
| Host VIEW handling (same instrumented agent run) | 19.980 ms |
| Host remote snapshot unpack / state refresh (included in VIEW) | 11.053 / 5.961 ms |

The Track HW output remains roughly 12 KB per tick. Blocking pipe reads
include idle wait for work and cannot be called transport latency. The
deferred reply remains required to wait for the simulated agent's result.
Journal synchronization is a small measured component on this filesystem;
K7 full-request/reply journaling, fsync and replay guarantees remain intact.
`c9498e4` reduces periodic VIEW traffic from 100 ms to 200 ms, within K6's
approved 100–200 ms range. STEP replies and ACTION acknowledgments keep
their ordering and cadence; a boundary regression checks the VIEW period.
The snapshot unpack/refresh cost motivates this change without altering
the window's refresh implementation or reducing durability.
These results establish neither real USB buffering cost nor Pi performance.

**Final process measurement, 200 ms VIEW cadence.** Four sequential runs,
15 real seconds each, using `--system --test-pi process`, project Python,
and `QT_QPA_PLATFORM=offscreen`. "Headless" means the harness frontend is
hidden; `--system` still constructs module windows in both modes. "Window"
also constructs the harness window offscreen. This is not a visual
inspection or a visible-desktop responsiveness check.
The default measurement dispatches G1; the separate full-system acceptance
scenarios exercise G1 and R1 together.

| Front end | Requested | Completed / due | Achieved | Mean / median / p95 / p99 / max round trip (ms) | Startup | Harness CPU |
| --- | --- | --- | --- | --- | --- | --- |
| Headless | 1x | 151 / 150 | 1.01x | 20.74 / 19.45 / 31.69 / 35.27 / 38.21 | 0.57 s | 6% |
| Window, offscreen | 1x | 150 / 150 | 1.00x | 20.54 / 19.25 / 28.23 / 35.76 / 41.12 | 0.51 s | 9% |
| Headless | 10x | 1,455 / 1,502 | 9.69x | 10.00 / 8.41 / 21.83 / 29.02 / 62.28 | 0.49 s | 27% |
| Window, offscreen | 10x | 1,414 / 1,502 | 9.42x | 10.27 / 8.57 / 23.20 / 30.26 / 73.09 | 0.51 s | 29% |

Every final run reports zero explicit dropped-backlog (slip) events and
zero late replies. The headless 10x run completed 47 fewer ticks than due;
the offscreen window run completed 88 fewer. Those unfinished ticks are
not reported as dropped-backlog events. Zero slip events therefore does
not imply all due ticks completed. Both final 10x runs fail the
measurement's 99% completion criterion. Before the cadence change, a
separate unprofiled 100 ms run reached 10.00x headless (8.32 ms mean) and
9.70x with windows (9.24 ms mean). These samples show variability, not a
proven end-to-end speed improvement from the cadence change. VIEW traffic
is reduced; the remaining variation is unresolved.

Phase 4 measured 10.00x with 5.1–5.8 ms mean round trip; the final Phase 5
10x means are 10.00–10.27 ms. Phase 5 adds both HW host/agent paths and
durable journals, so these are different workloads. Reliable simulated
10x remains open. Work stops here with K7 intact: Kevin can accept the
observed rate for simulated demonstrations, authorize a separate focused
optimization/review of snapshot unpack and refresh, or wait for the real
Pi/USB measurements before selecting a performance target. No durability
relaxation is proposed or silently applied.

## 7. Handoff

The initial 20 current-branch proposals and seven new proposals remain pending,
plus four PR #43 owner proposals under that source branch's inbox directory.
Only humans promote or delete them. No PR was opened or changed. The branch
never changed, and no worktree was created.

Two preexisting untracked files belong to earlier work and are preserved:
`common/harness/tests/adversarial_probe.py` and
`documents/central-harness-adversarial-2026-10-20.md`. They are outside this
session's commits. A clean session-owned diff must not be achieved by deleting
or staging them.

Run with the project virtual environment and `QT_QPA_PLATFORM=offscreen` when
headless. Host process/socket tests require local IPC permissions; sandbox
socket failures are not product regression evidence. This session checked
Python 3.14.4, PySide6 6.11.2 and PyInstaller 6.22.2 against the truth minima
on `kevin-framework`, Ubuntu 26.04.1 LTS, at 17:59 EDT on 2026-10-21.

October 22 correction work used the same toolchain on `kevin-framework`,
Ubuntu 26.04.1 LTS; system time was checked at 01:00 EDT on 2026-10-22.

## Phase 6 follow-up

The [Phase 6 handover](integration-handover-phase-6.md) records Kevin's
subsequent authorization to reuse Green routing in all Red test switches,
the approved shared read-only neighbor closure inputs, the completed Red
return, fresh visible-window measurements and Linux build smoke. It also
records the three failing CTC multi-train acceptance probes. Phase 5's
historical wait for real Red programs is superseded for these test copies;
Braden's review and physical-Pi validation remain open.
