# Phase 7 integration handover

Prepared 2026-10-24. This phase makes functional review explicitly 1x and
consolidates shared Pi HELLO matching. The single
[module owner review queue](module-owner-review.md) retains the CTC and other owner
questions; this handover does not resolve them or establish new policy.

## Revision and environment

Work began at `022608a` on `claude/quirky-fermi-sickg4`, a descendant of `f6ed1a1`.
The review host is `kevin-framework`, running Ubuntu 26.04.1, Python 3.14.4,
PySide6 6.11.2 and PyInstaller 6.22.2. The functional-review host is provisional,
as Kevin requested. Source commit `92e500b` contains the five Python changes
described below, on the same baseline. All times in this record are EDT (UTC−04:00).

Historical [Phase 6](integration-handover-phase-6.md) and
[scenario evidence](review-scenario-evidence-2026-10-22.md) results retain their
original revisions, hosts and bounds. They are not Phase 7 measurements.

## Implementation and approved scope

`common/hw_link/protocol.py` now owns `matches_hello`, used by both the relay and
bringup probe to compare HELLO operation, hardware module, protocol version,
session, agent version and bundle hash. Existing decoding still checks framing
and field types. The helper receives expected values explicitly and adds no
manifest, transport or provisioning dependency.

Relay admission still requires a truthy boot identifier; its boot comparison,
reboot recovery and gain policy remain in the relay. Bringup still accepts an
otherwise valid HELLO without a boot identifier. Both callers retain their exact
existing mismatch diagnostics. New tests cover matching replies, every identity
mismatch and missing identity field, relay boot rejection, and bringup's actual
receive/decode path with optional boot.

The process-review tests use the existing seven-module harness and two explicit
simulated Pi processes. Functional review is fixed at 1x with a 240-second wall
bound per manual/scheduled case. It retains `TIME_SLIPPED` among the fault
assertions, stopped trains with Green right-only and Red both-side platform doors,
continuous 45-second dwells, commanded/active emergency-brake checks and seven
clean module exits. Ten-times speed is measured separately.
The [runbook](review-runbook.md) and [HW changelog](../TrackCtrlHw/CHANGELOG.md)
carry the approved documentation follow-ups.

Kevin approved neighbor `CLOSED_n` inputs before implementation. He explicitly
stated that the approval was his, not Braden's acceptance. Braden remains the
required reviewer. No owner has been contacted by this work.

This phase does not authorize UI changes, including Python behind windows;
scheduler, vital-layer, starter, PLC or interpretation policy changes; new
transport/provisioning paths; or 10x optimization before real-Pi measurements.
`TrackModel/*_line.json`, preserved user files and existing inbox proposals remain
outside the edit scope. Truth facts were read from fetched `origin/truth`; no
proposal is treated as truth. The functional-review-speed proposal remains pending
human promotion, alongside the existing proposals.

## Recovery and evidence provenance

A power cut interrupted the first complete-harness run and removed the pre-cut
`/tmp/phase7-*` logs. The exact cut minute is unknown; work resumed and the
repository was rechecked at **10:55 EDT on 2026-10-24**. The interrupted run has
no complete result. Pre-cut shared-link and utils counts were observed by the
orchestrator, but the fresh post-cut results below are the primary evidence.

Qwen drafted runbook/changelog text and recovery labels; the sol agent corrected
wording and the orchestrator reviewed the actual diff rather than relying on a
worker success status.

## Fresh verification

Post-cut checks used `/home/kevin/ECE/Trains/.venv/bin/python`,
`QT_QPA_PLATFORM=offscreen`, and the Phase 7 source now committed as `92e500b`.
The module-validation agent ran suites sequentially in isolated processes, with
local IPC enabled, from **10:57:07 to 10:59:46 EDT**. The retrievable log is
`/tmp/phase7-postcut-module-validation.txt`; its recorded wall durations include
process startup. These are agent-run results reviewed by the orchestrator.

| Command (from repo root unless noted) | Result | Wall time |
| --- | --- | --- |
| `python -m pytest -q CTC-Office/tests` | 261 passed, 284 subtests | 20.88 s |
| `python -m pytest -q TrackCtrlHw/tests` | 89 passed, 50,538 subtests | 27.65 s |
| `python -m pytest -q TrackCtrlSW/tests` | 213 passed, 16 subtests | 9.63 s |
| `cd TrackModel` then `python -m pytest -q tests` | 312 passed | 2.43 s |
| `python -m pytest -q TrainController/tests` | 24 passed | 0.17 s |
| `python -m pytest -q Train-Ctrl_HW/tests` | 23 passed, 18 subtests | 0.29 s |
| `cd Train-Ctrl_HW` then `python main.py --check` | Exit 0; zero QML warnings and behaviour problems | 29.42 s |
| `cd TrainModel` then `python -m pytest -q tests` | 879 passed, 13 existing skips | 39.20 s |
| `python -m pytest -q common/hw_link/tests` | 71 passed | 8.08 s |
| `python -m pytest -q utils/tests` | 86 passed, 43 subtests | 20.99 s |

The pytest suites total **1,958 passed, 13 existing skips and 50,899 passed
subtests**. The timing-sensitive Train Model UI test
`test_ui_sync.py::test_input_list_scrolls_in_place_and_outputs_are_trimmed` ran
and passed in the complete suite, without a retry or additional skip.

The orchestrator then independently reran the complete shared-link suite on `92e500b`: **71 passed in 7.92 s**, recorded in `/tmp/phase7-parent-hw-link.log`.
The orchestrator also reran the scoped Flake8 command with pep8-naming/N815 exception and the three-file mypy command below; both passed after the separate measurements completed.

The independent post-cut source audit also passed:

- The 27 new HELLO cases passed in 0.06 s, including each identity mismatch,
  missing identity fields, relay boot admission and bringup's receive/decode path.
- Scoped Flake8 used `-j 1 --max-line-length=79 --extend-ignore=N815` on the
  three HELLO production files, new HELLO test and review-scenario test.
  `pep8-naming==0.15.1` was reinstalled only in `/tmp/phase7-lint-deps`, enabled
  through `PYTHONPATH`. Without the exception, only existing relay signals
  `viewChanged` and `diagnosticEvent` produce N815 warnings in these files.
  Broader `common/hw_link` lint retains twelve existing N802 fake-Qt method
  warnings in `test_bringup.py` and `test_transports_recovery.py`.
- Mypy passed for `protocol.py`, `relay.py` and `bringup.py` using
  `--explicit-package-bases --disallow-untyped-defs --follow-imports=silent
  --ignore-missing-imports`.
- `review_schedule` and both mixed/Green opt-in multi-train test functions are
  AST-identical to baseline `022608a`. Relay reboot/recovery/gain policy and
  exact caller mismatch diagnostics are preserved.
- All four runbook shell blocks pass `sh -n`. Interpreter selection checks cover
  the project venv, sibling venv, supplied interpreter and missing-venv failure.
  Dwell-observer boundary checks accept closure exactly 450 ticks after opening,
  reject closure at 449 ticks, and credit only 44.9 s at the last open sample.

### Process reviews and separate performance measurements

The orchestrator started the complete harness run on `92e500b` at 11:00 EDT:

```sh
QT_QPA_PLATFORM=offscreen TRACK_OVERFLOW_ROUND_TRIP=1 \
  TRACK_OVERFLOW_MULTI_TRAIN=1 "$PYTHON" -m pytest -q --durations=12 \
  --basetemp=/tmp/phase7-final-harness common/harness/tests
```

The direct orchestrator run completed with **185 passed, 3 failed and 497 passed
subtests in 456.45 s** (`/tmp/phase7-harness.log`). The three failures are the
unchanged owner probes below; the suite does not have a clean acceptance result.
Both manual and scheduled seven-process reviews passed at 1x in 111.39 s and
111.34 s respectively, each within its 240-s wall bound. Their assertions verified
continuous station dwells, correct platform doors, no fault events including
`TIME_SLIPPED`, no commanded/active emergency braking and seven clean module exits.
Direct event-CSV inspection confirmed manual/scheduled endpoints at ticks
1108/1107: each had two `TRAIN_ADDED` records, seven `MODULE_EXITED` records with
`exit code 0`, only `CLOCK_RESUMED 1x` for clock changes, no `SPEED_CHANGED`, and
no event from the unchanged `FAULTS` set. Green-only two-train and existing
round-trip tests also passed.

| Unchanged opt-in owner probe | Fresh endpoint / failed requirement |
| --- | --- |
| Mixed two trains per line | All four completed dwells; maximum simultaneous Green/Red count was 2/1, failing the required 2/2. The loop can finish before its 900-s simulation bound. |
| Mixed three trains per line | At the 900-s simulation bound, G1/G2/R1/R2 completed; maximum counts were 3/1. Endpoint: G1=111, G2=65, G3=64, R2=48. |
| Green-only three trains | At the 2,400-s simulation bound, G1/G2 completed with three simultaneously active. G1 retired; endpoint G2=65, G3=64. |

No earlier separation, exclusive-authority, emergency-brake or pickup assertion
failed in those probes. Their final fault-event assertion follows the failed
endpoint assertion and was not reached. They run real cores in one process and do
not verify process/Pi protocol correctness. The owner requests remain [CTC-1 and
CTC-2](module-owner-review.md#ctc-1-red-concurrency); no scheduler policy was changed.

Separate direct headless measurements use the same one-train system wiring,
two simulated Pi processes and zero filler bytes:

```sh
"$PYTHON" -m common.harness.measure --system --test-pi process --seconds 15 --speed 1
"$PYTHON" -m common.harness.measure --system --test-pi process --seconds 15 --speed 10
```

| Quantity | 1x | 10x |
| --- | --- | --- |
| Startup / measured wall time | 0.46 / 15.01 s | 0.52 / 15.02 s |
| Completed / due ticks | 150 / 150 | 1,500 / 1,502 |
| Achieved simulation speed | 1.00x | 9.99x |
| Dropped backlog (`ticks slipped`) | 0 | 0 |
| Late replies | 0 | 0 |
| RTT mean / median / p95 / p99 / max | 7.87 / 7.17 / 13.03 / 17.23 / 18.50 ms | 6.12 / 5.30 / 13.50 / 19.51 / 38.47 ms |
| Harness CPU, one core | 2% | 19% |

Both commands exited 0; logs are `/tmp/phase7-measure-1x.log` and
`/tmp/phase7-measure-10x.log`. Both samples meet the existing 99%-completion,
zero-drop, zero-late criterion. At 10x, two due ticks remained unfinished when the
sample ended; that is separate from the reported zero abandoned backlog, and the
report does not identify their exact in-flight state. No other test workload was
deliberately run during these samples; ordinary app/background activity was not
isolated. These are short samples of this host and workload, not a reliable-10x
guarantee or physical-Pi performance evidence. The speed decision remains open
until real-Pi measurements.

## Limits and remaining work

Simulated Pi processes and raw ptys do not verify physical USB power, cold boot,
port identity, unplug/reboot durability or real-board performance. Physical Pi
checks wait for working boards and owners' measurements. Windows packaging remains
deferred; this phase does not claim Windows acceptance or a fresh frozen build.

In-process opt-in probes cannot establish process-protocol correctness. A bounded
multi-train stall does not prove permanent deadlock. Owner-question failures remain
visible and must not be weakened into passing acceptance tests. The known Train
Model UI flake passed in this run; that observation does not establish that its
timing sensitivity is resolved.

The twelve requests and Kevin's answers remain in
[module-owner-review.md](module-owner-review.md). Human action is still required
for proposal collisions: consolidate D033; withdraw D034's Phase 6 scope plan while
retaining authoritative Green; preserve both distinct D035 policies and renumber
one. The branch inbox retains 35 pending proposals, with four separately
attributed to PR #43. Agents did not modify, delete, rename, renumber or promote
existing proposals. All twelve owner requests and these human proposal actions
remain open.

## Independent Phase 7 verification receipt

The follow-up check at `d606e05` on `kevin-framework` on 2026-10-24 reproduced
**1,958 passed, 13 existing skips and 50,899 passed subtests** across module,
utils and shared-link suites. The orchestrator directly ran the 71 shared-link
tests and spot-checked both completed process-review event CSVs; the check-only
verification subagent ran the remaining suites. The known timing-sensitive Train
Model UI test ran and passed; its timing sensitivity is not thereby resolved.

The full harness with both opt-in families produced **185 passed, 3 failed and
497 passed subtests in 461.59 s**. Manual and scheduled 1x process reviews passed
in **111.45 s** and **111.32 s**, within their 240-second bounds. The three
preserved failures remain the mixed-count 2/3 concurrency/completion probes and
Green-count 3 completion probe described in the shared owner-review queue.
HW `main.py --check` exited 0 with zero QML warnings and behaviour problems.
Scoped Flake8 passed with the existing N815 exception; three-file mypy passed.

The commit/rule audit found no implementation-scope violations: no UI, protected
course JSON, owner policy, preserved user file or inbox proposal changed. Two
minor stale links were found in `module-owner-review.md` (then lines 90/137):
test anchors 183/295 rather than 234/346. The documentation follow-up corrected
those anchors on 2026-10-25; no code changed.

Recovery on 2026-10-25 found the same branch/HEAD, remote alignment and five
preserved untracked files, with no tracked changes. Toolchain minima still pass.
The prior `/tmp/phase7verify-*` logs and event CSVs are no longer available; the
recovery check did not rerun tests. These counts describe the completed October 24
verification, not a new October 25 run. No Qwen diagnostic output was recovered.
See [module owner review](module-owner-review.md) for the current owner requests.
