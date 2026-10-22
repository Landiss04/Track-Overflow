# Integration handover: Phase 5 software and simulated Pis

Written 2026-10-21 on `claude/quirky-fermi-sickg4`, continuing the Phase 4
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
The yard now joins section-C block 9 and no longer joins 75. Original
`75-yard` text is retained; point 9/NORMAL toward 10/REVERSE yard remains
an explicit assumption for the Track Model owner and Braden. HW territory,
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
removal, emergency-brake or pickup-failure event occurs. Automatic Red
turnback has not been demonstrated. Changing the first-version switch
policy would require another decision.

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
core from that history, so replay cost grows too. Simulated step timings
exclude disk synchronization, serial transit and replay. A real Pi power-loss
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

## 2. Final software verification

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

**Static checks.** Production flake8 passes. The Pi package's 15 checked
Python files pass mypy. The nine-file harness type check has one preexisting
`common/harness/app.py:106` Qt application argument mismatch; the other
eight checked files are clean. That unrelated UI-facing annotation was not
changed, and this is not a claim that all repository type checks are green.

**Proposals and deferred work.** Commit `17beefc` files five new full proposals
for K2, K5, K6, K7 and K11. Two further full proposals record the confirmed both-variant K3b policy
and approved CLOCK_STATE exception. This branch's inbox has 27 proposals,
plus four
owner-source proposals brought in under PR #43's original branch directory.
All await human promotion; no existing proposal was edited or deleted. Pi owner
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
| R94 | K2: Red yard (Phase 3 Q5) | "block 9 physically connects to the yard via a switch … note that block 9 is in section c" | Move yard adjacency from 75 to section-C block 9. Point 9, NORMAL toward 10 and REVERSE yard is explicitly an assumption for the Track Model owner and Braden. Preserve the leftover `75-yard` text for them to resolve. |
| R95 | K3: PR #43 | "merge into this branch not devlopment leave the pr unmerged" | Merge the source into this branch with a merge commit. Do not merge/close/comment on the GitHub PR. |
| R96 | K3b: Vital layer | "the vital layer has been removed. everything is done by the plc code." | The no-vital policy covers both HW and SW, explicitly confirmed by Kevin later in this session. All safety belongs in PLC programs. Existing SW vital implementation is left unchanged under the original implementation scope, and is an owner follow-up. |
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
| R107 | K11 clock metadata follow-up | Kevin explicitly approved the prepared CLOCK_STATE exception in his later reply of 2026-10-21. | Add authoritative initial/change clock metadata on the harness-to-HW-host channels. Latch the state at Pi loss before timeout pause; verify running-loss gain replay and paused-loss non-application. |

## 4. Open questions and owner review

| Item | Owner | State / next action |
| --- | --- | --- |
| Red-9 NORMAL leg and leftover `75-yard` text | Track Model owner, Braden | Physical connection to section C block 9 is settled. NORMAL toward 10/REVERSE yard is an explicit assumption; source text is preserved. |
| Red test copies | Braden | Replace or approve the three exact-cut databases and PLCs. |
| WP2 generated vital block and variant PLC differences | Braden, Harry Tye | Dual channel exists; generated vital PLC does not. HW K3b puts safety in test programs. |
| SW implementation of confirmed K3b policy | SW owner, Harry Tye | Policy scope is confirmed for both variants. Existing SW vital implementation remains under the original session scope; remove/migrate it in a separate owner follow-up. |
| Cross-wayside occupancy | Braden, Harry Tye | Read-only neighbor OCC is exposed; missing occupied membership still means clear. Review the extension and full-line mapping assumptions. |
| Red return and turnback | Braden, Track Model owner, Landis | NORMAL-only starter reaches 16 but return is held at 66 by switch 52; no turnback demonstrated. |
| K11 host clock-state path | Integration | CLOCK_STATE exception explicitly approved (R107), implemented in `9325523`; full Pi suite (31) and focused clock/channel checks (34) pass. Running/paused replay policy and rapid train ID reuse are covered. |
| USB/power/10x/journal persistence | Module owners, Kevin | Actual Pi tests have not started. Journals grow through a session and cold replay cost grows with history. |
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
| `f465c99` | Both HW variants real by default; explicit process/pty test agents; unchanged stubs-only mode. |

## 6. Handoff

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
