# 10x Pi speed: final report

Date 2026-11-14. Branch `10x-pi-speed`, local only, nothing pushed, 33 files and about 2,800 lines changed since `e3077ae` (including this report). Source for every number is `10x-log.md` in this folder.

## What this shows, in four lines

- **Train Pi:** fixed on hardware. Round-trip p99 went from 18 ms to 2.5 ms on a 600 s replay with 0 round trips over 10 ms and 0 slow steps (cause: the journal write blocked behind an SD-card `fsync`).
- **Track Pi:** first ever hardware runs this session. A 600 s replay completes with round-trip p99 of 9.3 ms against a 10 ms slot (0.43% over), and the core step alone is 4.7-5.6 ms. It is the slowest module in the system, and its margin is thin.
- **10x with real Pis in the loop has not been measured.** The 100 Hz hardware replays are the 10x rate, but only one Pi at a time and only through `bringup`, never through the harness.
- **Three open problems on the Track Pi:** each new session in one agent process runs the core 12-27% slower (cause not found), up to about 3% of VIEW lines in a run are damaged on the USB link (cause not found, display-only), and 0.2-1.2% of round trips go over 10 ms for reasons only partly explained.

## Hardware results

Raspberry Pi 5 "ivz11", USB CDC-ACM, Windows host. Replays at `--hz 100` (the 10x rate); the host paces at about 92 Hz, so none ran at a true 100 Hz.

**Train Pi** (recorded Red workload). Round trip in ms.

| Build and run | mean / p95 / p99 / max | Over 10 ms | Pi slow steps |
| --- | --- | --- | --- |
| `5b60b2a`, before the journal queue, 3 min (A1e) | 1.22 / 1.68 / 18.0 / 45.1 | about 330 of 18,001 steps (1.8%, Pi side) | about 330 |
| `c4d8ac3`, journal write off the reply path, 3 min (A1f) | 0.91 / 1.66 / 2.54 / 187.7 | 1 step (an SD-card stall of 0.7 s) | 1 |
| `b061614`, `MAX_UNSYNCED` 300, 3 min (A1g) | 0.88 / 1.81 / 2.89 / 7.56 | none | 0 |
| `b061614`, 600 s, unpinned / pinned / unpinned | p99 2.58 / 2.57 / 2.72; max 13.1 / 9.0 / 12.7 | not counted then | 0 |
| `563b63f`, lean build, 600 s | 0.83 / 1.48 / 2.55 / 5.21 | 0 of 60,001 | 0 |

The original release `e3077ae` was never run on the Pi, so there is no true before and after for the whole branch; the earliest hardware row already carried items 1-8.

**Track Pi** (Red workload, tolerant `bringup`, agent hash 0a7cf856). Round trip and Pi core step in ms.

| Run | RTT mean / p95 / p99 / max | Over 10 ms | Core mean / p99 / max | VIEWs lost |
| --- | --- | --- | --- | --- |
| 180 s, first replay after a service start | 7.09 / 8.02 / 8.80 / 16.24 | 44 of 18,006 | 4.96 / 5.40 / 13.63 | 22 |
| 600 s, second replay in that process | 7.45 / 8.40 / 9.34 / 16.23 | 261 of 60,006 | 5.29 / 5.77 / 9.55 | 105 |
| 180 s, third replay in that process | 7.41 / 8.56 / 10.19 / 17.48 | 215 of 18,006 | 5.59 / 6.09 / 11.27 | 4 |
| 180 s, fresh process | 6.60 / 7.54 / 8.83 / 17.20 | 71 of 18,006 | 4.65 / 4.99 / 12.50 | 16 |

No step reply was ever damaged or resent in these runs; only VIEWs. The core step is about 70% of the round trip. At the 10x rate the Track Pi's p99 sits at or just under the 10 ms slot.

**System rows, no Pi in the loop** (`measure --system --test-pi process`, Windows host): 1x and 10x, headless and windowed, 0 slipped ticks in all four; at 10x the round-trip p95 is about 13 ms against the 10 ms budget (mean 8.1 ms). In a sandbox run the Track hardware core is the last module to reply in 91% of ticks.

## What was changed

Numbers follow the log's own numbering (items 1-10, phases 0-3). **The README whose section 5 the handoff refers to is not in this repository, so I could not map these to its wording or confirm there are no other items.** Please compare against it.

| # | Change | Status |
| --- | --- | --- |
| 1 | `TrainCore.step` rolls the roster back instead of deep-copying the fleet | Done, tested; Pi core step 0.06 ms |
| 2 | Journal handle kept open, one write per tick | Done, tested |
| 3 | Checkpoint `fsync`, rename and journal swap on a worker thread | Done, tested |
| 4 | `Nice=-10`, `PYTHONOPTIMIZE=1`, `performance` governor; no pinning; `install.sh` restarts a running agent | Done; pinning A/B on the Train Pi (600 s) and the Track Pi (180 s x 3) showed no usable difference |
| 5 | `render_check`: warns and lowers frame caps on software rendering | Code and tests; **no run on the target machine** |
| 6 | Train Model redraw 4 a second instead of 20 when flagged | Code and tests; 0.25 s is a placeholder |
| 7 | `process_cores`: harness and Pi link processes on separate cores | Code and tests; Windows path tested only against a stub |
| 8 | Slow-step log on the Pi (`SLOW_STEP`, `SLOW_VIEW`, `SLOW_ACK`) | Done; found the journal stall |
| 9 | Journal write off the reply path; `MAX_UNSYNCED` 300 | Done; Pi p99 18.0 to 2.5 ms. Durability changes: up to 300 steps of a Track recovery may be replayed (about 1.5 s at the Pi's measured 5 ms per step; the log earlier said 1 s using the sandbox's 3 ms) |
| 10 | Lean Track checkpoint (compiled PLC programs rebuilt on restore) | Done; on hardware the file is 183 KB flat over 133 checkpoints, core 66.6 KB plus reply cache 101 KB, no slow step at a checkpoint |
| - | `bringup`: p99, progress line, `connected` line, `rtt_over_10ms`, power-throttling opt-out | Done |
| - | `bringup` tolerant mode (default) and `--strict`; `--trace-csv` | Done this session; 8 new tests |
| - | Green-train replay test on the HW Train core | Done |
| - | Phase 2 proposal (docs), Pi setup how-to updates (this session) | Done |

Also on the branch: `bench/per_module.py`, a 24-line measuring wrapper committed by an earlier log commit although the log calls it scratchpad-only (say if it should go).

## Not done

- Run with every window open (600 s, unlocked screen) and the GPU/WARP check, including the `QSG_INFO=1` adapter line. Needs the target machine.
- `measure --system` against real Pis, one or both.
- Original-versus-now on the Pi (the `e3077ae` bundle).
- A Track-side change to the PLC step: `plc.py` has an owner; a tested proposal is in `plc-channel-a-flat-proposal.md`.
- Any train on Green or Red on the HW Pi: `common/harness/edges.py` still routes Red only.
- Causes of: the per-session slowdown, the damaged VIEW lines, and most of the round trips over 10 ms.
- No decision on how VIEWs are sent (rate, only-when-open, or changes only).

Test state: `common/hw_link` 237 passed, plus two `test_bundle_is_offline_stdlib_and_shell_parses` cases that need physical Pis. `common/harness/tests`: 7 failures on this branch and on `main` alike, not investigated. `TrackCtrlHw/tests` 116 passed.

## Findings that were not expected

1. **Track core slower in each new session of one agent process.** Core step mean 4.7, 5.2, 5.6 ms in replays 1-3 (reproduced three times, and 4.24, 4.79, 5.12, 5.40 ms in a bare in-process benchmark on the Pi with no USB or service). Flat within a replay, resets when the agent restarts, not seen on the Train core, not seen in an x86 sandbox. Not garbage, heat, throttling, memory growth, threads, thread placement, accumulated state, Python's small-object allocator. Concentrated in the PLC interpreter (channel A closures +59%, channel B +23%). Leading explanation, unproven: objects built per session land in a fragmented heap and a small-cache CPU pays for them. **Workaround: restart the agent before a run you will compare.**
2. **VIEW lines are damaged on the link, and only VIEWs.** A VIEW is a 41 KB display snapshot sent every 0.2 s after a step reply (step replies are 12.5 KB). In a raw capture of a 40 KiB echo line (not a VIEW) the damaged line was exactly one 512-byte USB packet short. VIEWs lost per full replay: 22, 105, 4, 16 and 12 in the first five, then 0 in each of the next eleven. The host relay already skips a damaged VIEW and resends anything else; `bringup` did not, and aborted. It now does what the relay does.
3. **Two agents on `/dev/ttyGS0`** (the service and a hand-started echo agent) split the bytes and made a whole set of link tests invalid. `pgrep -af "common.hw_link.agent"` before a link test.
4. **`config.txt` had `dr_mode=peripheralZ`.** Fixed to `peripheral` with your go-ahead, one reboot; the gadget worked before and after.
5. **A Pi that last ran the other module crash-loops** with `journal module mismatch`; the Train journal was moved aside to `session.train.json` and `agent.train.log`.
6. **The Track core step is 4.7-5.6 ms on the Pi, not the 3 ms I had from the sandbox.**
7. **The host's pacing tops out near 92 Hz**, so no run was a true 100 Hz.

Corrections to my own earlier statements, now fixed in the log: the "66 KB checkpoint" was the core alone (the file is 183 KB); the 16.2 ms maximum round trip is the slowest startup ACK (14.3 ms on the Pi plus link), not the cold first step; the heat and throttling idea is withdrawn.

## Left on the Pi and the host (for cleanup)

- Pi, to check: `/etc/systemd/system/track-overflow-agent.service.d/malloc.conf` was removed (the later runs match the default behavior), but I did not see `ls` of that folder on the Pi.
- Pi: `~/.local/bin/py-spy` (installed with `--break-system-packages`), `~/Downloads/plcbench.py`, `track-red-4k.jsonl`, `~/spytop.py`, and `/tmp/spy-r*.txt`, `/tmp/agentwatch.txt`, `/tmp/threads.txt`, `/tmp/track-echo.*`.
- Pi: this board now runs the **Track** agent (journal and log of the Train agent kept as `session.train.json` and `agent.train.log`). Install the Train bundle and move those back to use it as the Train Pi again.
- Host, `..\trains_pi\`: recordings, `linkcheck.py`, `qtcheck.py`, `bringup_trace.py`, `tracestats.py`, and result files for each run.

## Decisions for you

1. Adopt the restart-before-comparing rule (written into the Pi how-to, section 9) and, if wanted, a fresh process per session in the agent (not designed or built).
2. Send `plc-channel-a-flat-proposal.md` to the owner of `plc.py`.
3. Whether to change how VIEWs are sent, now that losses are known to be display-only.
4. Drop `bench/per_module.py` from the branch?
