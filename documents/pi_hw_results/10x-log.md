# 10x speed log

All numbers below are **x86 sandbox, 4 cores, Linux, pty instead of USB**, not a Pi. They show the
direction of a change, not Pi timings. Pi rows stay `pending` until measured on the board.

Command (one agent, 60 s, 6000 STEPs paced at 10 ms, captured Red workload with the three Red
territories and PLC programs loaded for Track):

    python3 bench_agent.py <repo> <train|track> 60 <label>

RTT = host send to full OUTPUTS reply. Slipped = RTT above 10 ms. `core` = `core_step_s` from the agent.

| # | Change | Board | RTT mean / p95 / p99 / max ms | core mean / p95 / p99 / max ms | Slipped | Where |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | baseline `e3077ae` | train | 0.803 / 1.017 / 1.594 / 5.49 | 0.239 / 0.302 / 0.379 / 3.55 | 0 | sandbox |
| 0 | baseline `e3077ae` | track | 3.955 / 5.466 / 6.289 / 31.40 | 2.784 / 4.071 / 4.373 / 17.20 | 15 | sandbox |
| 1 | no per-step fleet deepcopy | train | 0.641 / 0.816 / 1.201 / 9.24 | 0.078 / 0.102 / 0.152 / 3.11 | 0 | sandbox |

Item 1, core only (`TrainCore.step`, no link), mean / p99 ms, old then new: 1 train 0.096 / 0.173 then
0.019 / 0.042; 6 trains 0.468 / 0.934 then 0.091 / 0.188; 12 trains 0.903 / 1.537 then 0.162 / 0.256.

Rows below continue the table above (same command and columns).

| # | Change | Board | RTT mean / p95 / p99 / max ms | core mean / p95 / p99 / max ms | Slipped | Where |
| --- | --- | --- | --- | --- | --- | --- |
| 2 | journal handle kept open (run 1, noisy: one 16 ms core spike) | train | 0.619 / 0.767 / 1.219 / 21.62 | 0.080 / 0.099 / 0.121 / 15.93 | 4 | sandbox |
| 2 | same, repeat 1 | train | 0.593 / 0.797 / 1.107 / 4.62 | 0.078 / 0.098 / 0.133 / 3.08 | 0 | sandbox |
| 2 | same, repeat 2 | train | 0.625 / 0.820 / 1.175 / 4.45 | 0.081 / 0.105 / 0.148 / 3.06 | 0 | sandbox |
| 2 | journal handle kept open (vs baseline row 0) | track | 3.632 / 4.991 / 5.607 / 30.17 | 2.582 / 3.783 / 4.122 / 25.17 | 13 | sandbox |

Item 2 moves the mean by about 0.03 ms on the sandbox, inside run-to-run noise; its real saving is an
open/close per tick on the Pi's SD-card filesystem, which only a Pi run can show.

Item 3 adds a column: RTT of the ten checkpoint steps (every 600th step) per 60 s run, ms.

| # | Change | Board | RTT mean / p95 / p99 / max ms | core mean / p95 / p99 / max ms | Slipped | Checkpoint-step RTT ms (range) | Where |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | before item 3 (journal handle open) | train | 0.649 / 0.815 / 1.499 / 20.58 | n/a | 2 | 2.65 - 10.84 | sandbox |
| 2 | before item 3 (journal handle open) | track | 4.015 / 5.491 / 6.522 / 44.39 | n/a | 17 | 20.26 - 34.47 | sandbox |
| 3 | checkpoint fsync, rename and journal swap on a worker | train | 0.652 / 0.881 / 1.220 / 5.32 | 0.083 / 0.106 / 0.146 / 2.54 | 0 | 0.92 - 1.32 | sandbox |
| 3 | same | track | 4.140 / 5.700 / 7.220 / 18.85 | 2.954 / 4.221 / 4.699 / 10.33 | 18 | 12.20 - 18.85 | sandbox |

Item 3 leaves the pickle on the step's thread. Pickling the Track core with the three Red territories and
PLC programs is 457 KB and 7-15 ms on the sandbox (`pickle.dumps` alone), so Track's checkpoint step is still
about 3x a normal step. The sandbox's fsync is about 2 ms (overlay filesystem), so the Pi's SD-card fsyncs,
which this change moves off the reply path, are not visible here.

| 4 | `Nice=-10`, `PYTHONOPTIMIZE=1`, `performance` governor at agent start (no CPU pinning); `install.sh` starts the agent again if it was running | both | pending | pending | pending | Pi only | not measurable on the sandbox |

Item 4 is verified here only by `systemd-analyze verify` on the rendered unit and by `sh -n` plus a stubbed-`systemctl`
run of the install logic. The unit sets the `performance` governor with `ExecStartPre=-+` (root, tolerates no cpufreq) and does not
pin cores. `install.sh` records whether the agent was
active and starts it at the end; a literal `try-restart` would do nothing, because the script stops the agent first.

## TrackCore profile (before any change; sandbox, three Red territories and PLC programs loaded)

`cProfile`, 1500 STEPs: `TrackCore.step` 14.4 s under the profiler, of which `wayside.scan` 13.6 s
(`_run_program` 12.2 s; `scan_a` + `scan_b` + `_run_postfix` + the per-token lambdas in `plc.py`).
That is 95% of the step in the PLC interpreter. `view()` is 1.3 ms mean (2.5 max), encoding its VIEW
0.34 ms, 41 KB. Not changed: `plc.py` has an owner and its two scans are redundant channels.

## Pi A/B test: core pinning (procedure; results under A1g and the 600 s A/B/A below)

Run on each Pi with the same bundle, 10x, the same workload, 600 s each, record the table columns above
from `measure --system` and `core_step_s` from the Pi. Without a rebuild, using a systemd drop-in:

    # B: pinned
    sudo mkdir -p /etc/systemd/system/track-overflow-agent.service.d
    printf '[Service]\nCPUAffinity=2 3\n' | sudo tee /etc/systemd/system/track-overflow-agent.service.d/pin.conf
    sudo systemctl daemon-reload && sudo systemctl restart track-overflow-agent.service
    # A: unpinned (default)
    sudo rm /etc/systemd/system/track-overflow-agent.service.d/pin.conf
    sudo systemctl daemon-reload && sudo systemctl restart track-overflow-agent.service

Before B, `grep -i -E 'dwc2|usb|xhci' /proc/interrupts` shows which core takes the USB interrupts; pin away from it.
Also record `cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor` (expect `performance`) and `vcgencmd get_throttled`.
Decide on p99 and max RTT and slipped ticks, not the mean. Run `sync` before any unplug.

## Phase 3: host side (code only; the confirming run is pending on the target)

None of these rows has a before/after number: they need the target (Snapdragon X2 Plus, six cores, Windows) and a
600 s stress run with the screen unlocked and every window exposed.

| # | Change | What it does | Placeholders and gaps |
| --- | --- | --- | --- |
| 5 | `utils/render_check.py`, called in the harness before it starts the modules | Prints `Rendering: ...` always; on software rendering prints a `WARNING` to stderr and sets `TRACK_OVERFLOW_LOW_FRAME_RATE=1` for the modules | Catches `QT_QUICK_BACKEND=software`, `LIBGL_ALWAYS_SOFTWARE`, Qt's Software API and an OpenGL renderer named llvmpipe, softpipe, swrast, SwiftShader, Basic Render or WARP. **Does not catch WARP behind Direct3D 11** (Qt gives no adapter name there); it says so in the `Rendering:` line. Run once on the target with `QSG_INFO=1` and send the adapter line, then the match can be written |
| 6 | Train Model `view_interval_s` 0.05 s -> 0.25 s when flagged | Redraws 4 a second instead of 20 | 0.25 s is a placeholder, not tuned. It is the only redraw cap that exists; the other windows draw as their data changes and have none |
| 7 | `utils/process_cores.py`: harness on cores 0..n-3, each of the two Pi link processes on the last two (last one with 4-5 cores, nothing under 4) | On six cores: system 0-3, links 4-5. `TRACK_OVERFLOW_NO_PIN=1` for the A/B run | Windows path (`SetProcessAffinityMask`) is tested only against a stub here; Linux path is tested for real. Children inherit the harness's mask on both |

## Train Pi, real hardware (Raspberry Pi 5 "ivz11", USB CDC-ACM, Windows host)

Recorded Red train workload (`train-red-600s.jsonl`, 60,001 requests, engineer gains 400000/8000), one request
outstanding, `bringup --recording ... --hz 100`. Bundle from `719b4ec`/`3b94ac1`, agent hash `d322d086...`, `performance`
governor, `Nice=-10`, `PYTHONOPTIMIZE=1`, no CPU pinning, `get_throttled` 0x0. USB gadget interrupts (`dwc2_hsotg`) all on core 0.
Rate = samples / elapsed_s. RTT is host send to reply, in ms. Slipped ticks are not recorded by `bringup`: not available.

| Run | Rate | Late sends | RTT mean / p95 / p99 / max | Pi core step mean / p95 / p99 / max |
| --- | --- | --- | --- | --- |
| A1 unpinned | 65.5 Hz | 56,758 (95%) | 1.12 / 2.09 / 3.03 / 146.1 | 0.065 / 0.097 / 0.122 / 0.433 |
| A1b unpinned | 83.1 Hz | 26,516 (44%) | 1.45 / 1.63 / 16.6 / 2620.6 | 0.061 / 0.089 / 0.116 / 0.238 |
| A1c unpinned | 64.6 Hz | 57,529 (96%) | 1.37 / 2.10 / 17.7 / 292.9 | 0.063 / 0.094 / 0.120 / 0.442 |
| Echo agent, 1 KiB, 60,000 requests (no core, no journal) | 92.5 Hz | 20,996 (35%) | 0.77 / 1.32 / 1.91 / 132.4 | n/a |

- None reached 100 Hz, so none is a 10x run. The host's rate varied from 65 to 92 Hz between runs. A1, A1b and A1c all ran **without** `keep_full_speed` in `bringup`: the host checkout was still on the older files (a fetch moved the branch pointer but not the working tree), so that fix is untested until A1d.
- The Pi core never exceeded 0.44 ms. The tail (p99 17 ms in A1b and A1c, not in A1 or the echo) is outside the core.
- The Pi's SD card, idle, 6000 append+fsync at 100 Hz: p50 9.1, p99 37.0, max 117.6 ms, none over 500 ms (the agent's disk backpressure starts at 50 unsynced records, about 0.5 s). `dmesg` and `agent.log` showed no USB, SD or agent errors during the runs.
- Not yet run: B (pinned, `CPUAffinity=2 3`), A2. Held until the tail's source is known.

## Item 8: slow-step log on the Pi (diagnostic)

`SLOW_STEP tick=N total_ms=.. core_ms=.. disk_wait_ms=.. ckpt_pickle_ms=..` and `SLOW_VIEW` / `SLOW_ACK` are written to
`/var/lib/track-overflow/agent.log` for a reply that takes over 10 ms from the agent having the request to its last byte
written. Nothing is logged under 10 ms. If the host sees a fat tail and this log stays empty, the delay is before the agent
reads (USB, Windows). Cost, in-process on the sandbox, `_replies` per step, mean us over 20,000 steps, three alternating runs:
new 116.1 / 117.5 / 119.1, previous commit 114.2 / 112.5 / 115.5 (about 3.5 us, medians within 1 us). Sandbox pty run, track, 60 s:
16 slow lines, for example `SLOW_STEP tick=351 total_ms=13.9 core_ms=6.8 disk_wait_ms=0.0 ckpt_pickle_ms=0.0`.

### A1d: first run with `keep_full_speed` on the host and the slow-step log on the Pi (Train Pi, unpinned)

| Run | Rate | Late sends | RTT mean / p95 / p99 / max | Pi core step mean / p95 / p99 / max |
| --- | --- | --- | --- | --- |
| A1d | 91.7 Hz (90.6-92.8 every minute) | 18,451 (31%) | 1.21 / 2.01 / 17.8 / 298.3 | 0.059 / 0.083 / 0.112 / 0.271 |

- `keep_full_speed` stabilised the host's rate at about 91 Hz (A1, A1b, A1c had 65, 83, 65). It does not reach 100 Hz.
- The tail did not go away: p99 17.8 ms; every minute's worst reply was 36-298 ms.
- Pi log: 1,529 `SLOW_STEP` lines for 60,001 steps (2.5%), 10-29 ms each, three of 120-152 ms near the end. In every line shown,
  `core_ms` 0.1, `disk_wait_ms` 0.0, `ckpt_pickle_ms` 0.0: not the core, not disk backpressure, not the checkpoint pickle.
- The slow steps recur every 19-21 steps, about the VIEW period (0.2 s = 19 steps at 91 Hz), so they follow the VIEW cycle.
- Next: `decode_ms`, `journal_ms` (includes the disk wait) and `tty_ms` (the reply's write to the device) are added to the line,
  to separate the agent's own work, the journal write, and the USB write. A 180 s recording is enough to see it.

### A1e and the cause of the tail

A1e (3-minute replay, `5b60b2a`, Train Pi, unpinned): 18,001 samples, 90.5-90.9 Hz each minute, late sends 7,275,
RTT mean / p95 / p99 / max 1.22 / 1.68 / 18.0 / 45.1 ms, Pi core step max 0.40 ms.
Pi log: 1,862 slow lines in total; in every line shown `journal_ms` is within 0.2 ms of `total_ms` (for example `total_ms=21.6 journal_ms=21.4`),
with `decode_ms`, `tty_ms`, `core_ms`, `disk_wait_ms` and `ckpt_pickle_ms` all 0.0-0.1. The delay was the journal `write()`.

Pi test, 3000 appends of 480 B at 100 Hz to a file in the home directory (SD card), alone and beside an fsync thread:

| Case | write p50 | p99 | max | Over 10 ms |
| --- | --- | --- | --- | --- |
| no fsync | 0.01 ms | 0.0 ms | 10.1 ms | 1 |
| fsync back to back (as the agent did) | 0.02 ms | 18.3 ms | 27.3 ms | 68 (2.3%) |
| fsync with a 50 ms gap | 0.01 ms | 2.4 ms | 35.3 ms | 9 (0.3%) |

A write beside a running fsync of the same file stalls for the fsync's duration. At 10x any write of 10 ms or more is a slipped tick.

## Item 9: journal write off the reply path

A step now puts its record on an in-memory queue and replies; one `journal` thread writes the queue and fsyncs it. The checkpoint swap
clears the queue (what it held is in the checkpoint or in the carried records of the new journal), so nothing is written twice or dropped.

- **Changed durability:** a record is no longer in the OS cache when its reply goes out. If the agent process dies right after a reply, the
  records accepted since the journal thread last wrote (those queued during its current write and fsync, about 1-4 at 10 ms, up to
  `MAX_UNSYNCED` = 50 if the card stalls) are lost, as a power cut loses unsynced records today. The host keeps every request until a reply
  names it durable and resends it after a recovery, and no reply claims a record that is not fsynced.
- **Per step, in-process on the sandbox** (`_replies`, mean us over 20,000 steps, three alternating runs): B 97.4 / 101.0 / 95.3,
  previous commit 115.5 / 116.9 / 115.9.
- **Sandbox pty run:** `journal_ms=0.0` in every slow line. The sandbox's fsync is about 2 ms, so the stall itself is not reproduced here;
  the Pi run decides.
- **Tests:** two new tests fail on the previous agent ("a reply waited for the journal file"); five existing tests changed because their rule
  changed (a record is on disk only after `wait_durable()`; a power cut also drops what is still queued). 25 repeats of the journal tests
  and 6 of the whole suite passed.

### A1f: journal write off the reply path (Train Pi, `c4d8ac3`, 3-minute replay, unpinned)

| Run | Rate | Late sends | RTT mean / p95 / p99 / max | Pi core step mean / max | Pi steps over 10 ms |
| --- | --- | --- | --- | --- | --- |
| A1e before the queue (`5b60b2a`) | 91 Hz | 7,275 | 1.22 / 1.68 / 18.0 / 45.1 | 0.059 / 0.396 | about 330 of 18,001 (1.8%) |
| A1f with the queue (`c4d8ac3`) | 92 Hz | 7,139 | 0.91 / 1.66 / 2.54 / 187.7 | 0.059 / 0.233 | 1 |

The one slow step: `SLOW_STEP tick=10230 total_ms=185.2 disk_wait_ms=184.9`, the same moment as the host's 187.7 ms maximum. The agent had
`MAX_UNSYNCED` = 50 records waiting for the SD card (0.55 s at 91 Hz) and the card's fsync was stalled for about 0.7 s, so the reply
waited. `MAX_UNSYNCED` is now 300 (3 s at 100 steps a second): a stall under that costs no reply any time. The price is a recovery that replays
up to 300 steps (about 30 ms for the Train core, about 1 s for the Track core at 3 ms a step). Not yet run on the Pi.

### A1g: `MAX_UNSYNCED` = 300 (Train Pi, `b061614`, agent hash a1f4fa6d, 3-minute replay, unpinned)

18,001 steps at 92.8 Hz. RTT mean 0.88 / p95 1.81 / p99 2.89 / max 7.56 ms. Pi core step max 0.39 ms. No `SLOW_STEP` in the Pi log.

### 600 s A/B/A, core pinning (Train Pi, `b061614`, Red workload, 60,001 steps, `--hz 100`)

| Run | Rate | Late sends | RTT mean / p95 / p99 / max (ms) | Pi core step mean / max (ms) | Pi `SLOW_STEP` |
| --- | --- | --- | --- | --- | --- |
| A, unpinned | 92.0 Hz | 23,887 | 0.912 / 1.696 / 2.579 / 13.14 | 0.059 / 0.229 | 0 |
| B, `CPUAffinity=2 3` | 92.4 Hz | 21,864 | 0.869 / 1.695 / 2.566 / 8.99 | 0.057 / 0.398 | 0 |
| A2, unpinned (drift check) | 92.4 Hz | 22,124 | 0.872 / 1.635 / 2.721 / 12.71 | 0.060 / 0.271 | 0 |

- Command: `python -m common.hw_link.bringup --module train-controller-hw --recording ..\train-red-600s.jsonl --hz 100 --timeout 700 --output <file>`.
- Pinning makes no difference we can measure: p99 is 2.58 / 2.57 / 2.72 ms. The two unpinned runs differ from each other as much as from B.
  Decision: no pinning, `performance` governor only.
- Max round trip was over 10 ms in A (13.1) and A2 (12.7), not in B (9.0). The Pi logged no slow step in any run, so those spikes are on the host or
  the link, one in about 60,000 steps. The summary holds only the maximum, so the number of steps over 10 ms is not known.
- The host paced at about 92 Hz, not 100, in all three. Late sends are the host timer, not the Pi.
- The user reports the PC probably slept between runs 2 and 3. Nothing in the run-3 numbers shows it.
- Not shown: Track Pi, windows open, `measure --system`.

`bringup` now also writes `rtt_over_10ms`: the number of round trips over 10 ms, next to the maximum. It is a host-side change only, so the Pi bundle
and agent hash are unchanged. The 600 s runs above predate it, so their counts are unknown.

## Phase 0 system rows: `measure --system --test-pi process --seconds 15` (Windows host, local agents, no Pi in the loop, `d217df0`)

| Speed | Front end | Ticks | Round trip mean / median / p95 / p99 / max (ms) | Slipped | Late replies | Harness CPU |
| --- | --- | --- | --- | --- | --- | --- |
| 1x | headless | 152 of 151 | 10.21 / 8.80 / 12.90 / 13.56 / 143.69 | 0 | 0 | 4% |
| 10x | headless | 1,501 of 1,501 | 8.09 / 7.47 / 13.16 / 18.05 / 51.55 | 0 | 0 | 36% |
| 1x | window | 151 of 150 | 9.89 / 8.98 / 13.74 / 15.32 / 25.98 | 0 | 0 | 10% |
| 10x | window | 1,503 of 1,502 | 8.07 / 7.39 / 13.21 / 18.31 / 61.35 | 0 | 0 | 42% |

- Speed achieved is 1.00x/1.01x and 10.00x. "Slipped" counts only ticks that were dropped after the run fell too far behind (`dropped_ticks`);
  a single late tick that is caught up is not counted.
- At 10x the budget is 10 ms and p95 is about 13 ms, so more than 5% of ticks take longer than their slot and are only caught up afterwards.
  The mean is under budget, which is why the speed still holds.
- The handover's 10x headless numbers were mean 4.35-4.76, p99 16.9-19.9, max 36-95 on a different machine. Here the mean is higher
  (8.1) and the p99 is the same.
- Window and headless are close at 10x. The window costs a few percent of one core, not the round trip.
- Not measured: a real Pi in the loop (needs the Track Pi), 600 s.

### Which module sets the 10x round trip (sandbox, `--test-pi process`, headless, 15 s; script `bench/per_module.py`, scratchpad only)

Reply time from tick start, per module (ms); "last" is the share of ticks where that module's reply completed the tick.

| Module | mean | p50 | p95 | p99 | max | last |
| --- | --- | --- | --- | --- | --- | --- |
| track-controller-hw | 6.07 | 5.12 | 9.92 | 14.96 | 67.79 | 91% |
| track-controller-sw | 3.67 | 3.37 | 5.60 | 6.99 | 13.59 | 2% |
| ctc-office | 2.67 | 1.86 | 5.20 | 18.85 | 28.17 | 5% |
| train-controller-hw | 2.46 | 1.80 | 5.35 | 7.09 | 11.59 | 0% |
| track-model | 2.13 | 1.93 | 3.64 | 5.19 | 15.96 | 1% |
| train-controller-sw | 1.97 | 1.74 | 3.73 | 5.66 | 8.00 | 0% |
| train-model | 1.89 | 1.77 | 3.36 | 4.74 | 7.13 | 0% |

Round trip in that run: mean 6.66, p95 13.73, p99 19.31, max 67.88 ms. The Windows run on the target had mean 8.09, p95 13.16, p99 18.05, so the sandbox is a fair stand-in for the shape, not the values.
The Track hardware core is last in 91% of ticks. Its mean is the 3 ms PLC step plus the checkpoint pickle (7-15 ms every checkpoint) plus the link. The ctc-office p99 (18.9 ms) is a separate tail.

### Track checkpoint: static versus dynamic (sandbox, in process, three Red waysides and programs, 1,200 steps; script `bench/ckpt_split.py`, scratchpad only)

| What is pickled | Bytes | Pickle time (median of 30) |
| --- | --- | --- |
| Whole core (what a checkpoint holds today) | 458,922 | 6.05 ms |
| Everything except the compiled PLC programs | 33,443 | 0.66 ms |
| The compiled programs alone (`_vital` and `_program` of each wayside) | 425,417 | 5.24 ms |
| The program source text alone | 85,139 | not timed |

- 93% of the checkpoint is the compiled programs. `Program` is a frozen dataclass ("Scanning never changes it"), so it is static after load.
- `_vital` (254 KB) is built from the territory by `vital_source(territory)`, so it can be rebuilt after a restart without being saved.
- Leaving the compiled programs out cuts the pickle from about 6 ms to about 0.7 ms in the sandbox. Not measured on the Pi.
- Not checked: whether a restored core can recompile its programs from source and the territory with the same result. That has to be tested before any change.

## Item 10: lean Track checkpoint (agent side only)

- **Change:** `TrackCore.__getstate__`/`__setstate__` in `common/hw_link/cores.py`. A checkpoint keeps each wayside's program *source* and leaves out the
  compiled `_vital` and `_program`; a restore compiles them again (`compile_program(vital_source(territory))` and `compile_program(source)`).
  The live core is not touched (shallow copies). Nothing in `track_ctrl_hw` changed. The wire protocol is unchanged. The checkpoint file's content
  changed, which is also why the agent hash changed: a Pi running the old agent starts fresh from its old journal (`JOURNAL_STALE`), as before.
- **Measured (sandbox, three Red waysides, 600 steps in):** core pickle 458,922 -> 66,435 bytes (the checkpoint file also holds the reply cache, about 101 KB, so it is about 183 KB; see the 600 s Track run); pickle on the step thread 6.05 -> 0.97 ms.
  Restore (agent start only) 34-43 ms; the first step after a restore 7.1-7.6 ms (the program caches warm up).
- **Equivalence:** the rebuilt `Program` objects compare equal to the originals for all three waysides; 1,200 steps after a restore give the same
  output as the core that was never checkpointed, and the same view except the scan's wall-clock `last_duration_s`.
- **Tests:** `common/hw_link/tests/test_track_checkpoint_split.py` (6): size and no compiled classes in the pickle (fails on the previous code), live core
  untouched, restored core steps like the original for 280 steps, no program loaded, an older whole-core checkpoint still restores, and an agent
  restart from a checkpoint after real load actions. `common/hw_link`: 229 passed.
- **Not yet measured on the Pi:** the Track Pi has never been run on hardware.

### Lean Track checkpoint build on the Train Pi (`563b63f`, agent hash 0a7cf856, 600 s replay, unpinned, `--hz 100`)

60,001 steps in 648.2 s (92.6 Hz), Red workload. RTT mean 0.825 / p95 1.48 / p99 2.55 / **max 5.21 ms**, `rtt_over_10ms` = **0**. Pi core step mean 0.059 / max 0.39 ms.
Worst round trip per minute 3.4-4.8 ms. No `SLOW_STEP` in the Pi log (last line is still the A1f `tick=10230`).
This is the first 600 s run with no round trip over 10 ms (A, A2 had maxima of 13.1 and 12.7 ms). One run, so the spikes are not proven gone.
The Train agent has no Track core, so the lean checkpoint itself is not exercised by this run; it is the rebuilt bundle on the Train Pi. The Track Pi is still untested.

### Harness suite on this branch
`common/harness/tests`: 7 failed, 277 passed, 10 skipped. The same 7 fail on `main` (`git archive main` run of the three files): `test_green_follower_waits_on_75_then_runs`,
`test_the_ctc_office_takes_the_track_models_sales`, and five `test_red_owner_diagnostics` cases. Not caused by this branch; not investigated.

## Track Pi on hardware: first runs (Raspberry Pi 5 "ivz11" as the Track board, `df4c491`, agent hash 0a7cf856)

The Track Pi had not run before. The board had been the Train Pi; its Train journal was moved aside (`session.train.json`, `agent.train.log`) because the Track agent refuses a journal from another module (`journal module mismatch`).
`/boot/firmware/config.txt` had `dtoverlay=dwc2,dr_mode=peripheralZ` under `[all]` (a stray `Z`); changed to `peripheral` and the Pi rebooted once, with the user's go-ahead. The gadget came up high-speed, `throttled=0x0`, no under-voltage lines in `dmesg`.

### What the first Track replays did
`bringup --recording track-red-180s.jsonl --hz 100` (plain probe, the probe stopped on the first damaged line): aborted with `line checksum does not match` at samples 19, 76 and 97. Not timing results; no rows logged.
The same abort came from the 20 KiB link echo (Windows host, one agent): after 35, 274, 9 and 80 samples. 1 KiB and 10 KiB passed 1000/1000.

**Two of the echo runs were invalid**: the service agent and the foreground echo agent were both running on `/dev/ttyGS0`, so each read part of the stream. Always `pgrep -af "common.hw_link.agent"` before a link test: it must list exactly one agent. Everything below uses single-agent runs.

### Where the loss is
- The Pi logged no damaged request in the valid runs (`SKIPPED_LINE` count 0 after the agent's start); the damaged lines are replies, Pi to host.
- The Pi's `os.write` loop handles partial writes, and is unchanged from `e3077ae`. `protocol.py` and `transport.py` have no diff against `e3077ae`. `LineBuffer` passed a fuzz of 300 random chunkings (9,000 lines).
- Bare checks that skip Qt (`linkcheck.py`, raw Win32 `ReadFile`) and the bare `QSerialPort` (`qtcheck.py`, events and blocking), 20 KiB, 1000 samples: all passed, with and without `SetupComm`. The plain probe's 20 KiB echo then passed 1000/1000 twice. The earlier failures did not reproduce on a rerun; the cause of that period is not found.
- `bringup_trace.py` (the probe with the checksum call wrapped, nothing else changed) on the replay: failed after 1,885 completed samples (20.3 s, the 1,986th reply line), and the damaged line was a **VIEW** of 38,715 bytes.
- Raw 40 KiB echo: one failure at sample 91 and **the damaged line was exactly 512 bytes short** (40,759 against 41,271; `x` run 40,448 of 40,960), which is one whole high-speed USB bulk packet. The next 3,000 lines (40, 40 and 30 KiB runs) passed. About one lost packet in about 3,100 lines of 30-40 KiB (about 110 MB), measured only in that one stretch.

### What a VIEW is, and its size
Every 0.2 s (`VIEW_INTERVAL_S`) the agent sends the host a snapshot of the Track controller's display state (all waysides). Sizes by op in a local replay of the Red recording (1,500 steps, framed lines):

| Reply | Lines | Median | Max |
| --- | --- | --- | --- |
| `OUTPUTS` (step reply) | 1,494 | 12,546 B | 12,560 B |
| `ACK` | 6 | 18,004 B | 24,453 B |
| `VIEW` | 26 | 41,069 B | 41,089 B |

About 200 KB/s of VIEWs against about 1.15 MB/s of step replies at 92 Hz. Every damaged line seen with a trace was a VIEW; the failures at 19, 76 and 97 samples fit the VIEW timing but those lines were not captured.
The host relay (`relay.py`) already skips a damaged VIEW and resends anything else; the probe did neither.

### Change: the probe acts as the relay does (host side only; the Pi bundles' agent hash is unchanged)
`bringup` now, by default, (1) skips a damaged line that starts like a VIEW, (2) resends the in-flight request on any other damaged line, (3) resends after `--resend-ms` (default 1000, the relay's wait) with no reply, (4) ignores a late duplicate of an answered request, and (5) times a round trip from the first send, so a lost line is not hidden by the resend. `--strict` keeps the old stop-on-first-damaged-line, which link tests need.
The result JSON gains `lines_lost`, `views_lost`, `resends`, `duplicate_replies`, `strict`; `PI_SKIPPED_LINE` and `PI_RESENT` go to stderr.
Tests (`test_bringup.py`, 5 new): a clean run reports zeros; a damaged VIEW is skipped and not resent; a damaged reply is resent once; a reply that never arrives is resent after the wait and its round trip is at least half the wait (Qt's coarse timers fire a little early); `--strict` stops. They fail on the previous `bringup.py`. `common/hw_link`: 234 passed, plus the 2 known `test_bundle_is_offline_stdlib_and_shell_parses` cases that need physical Pis.

### Not done
- The 180 s and 600 s Track replays have not completed on hardware with this change; no Track timing row yet.
- No fix for the packet loss itself. Options not taken, each a wire change that needs a decision: raise `VIEW_INTERVAL_S`, send VIEWs only while a UI is open, send changes only.

### First complete Track replay on hardware (`5d19539`, agent hash 0a7cf856, 180 s Red recording, `--hz 100`, unpinned, tolerant probe)

18,006 of 18,006 requests in 195.1 s (92.3 Hz, the host pacing limit; 6,645 late sends), `error` null.

| | Value |
| --- | --- |
| RTT mean / p95 / p99 / max | 7.09 / 8.02 / 8.80 / 16.24 ms |
| Round trips over 10 ms | 44 of 18,006 (0.24%) |
| Pi core step mean / p95 / p99 / max | 4.96 / 5.19 / 5.40 / 13.63 ms |
| Request / reply bytes | 30,729,538 / 263,971,732 |
| `lines_lost` / `views_lost` | 22 / 22 |
| `resends` / `duplicate_replies` | 0 / 0 |

- Every lost line was a VIEW (display-only; the next one follows 0.2 s later). No step reply was damaged, so nothing was resent.
- Lost VIEWs per minute: 7, 8, 5, 2 (the last 15 s counted with the fourth). About 975 VIEWs were sent (195 s at one per 0.2 s, derived), so about 2% were lost.
- Step replies are about 226 MB of the 264 MB. Losses spread by bytes would have damaged about 120 of them; none was. So the loss is not simply proportional to bytes. VIEWs differ from step replies in two ways at once, and this run cannot tell them apart: size (about 41 KB against 12.5 KB), and being written straight after a step reply (about 54 KB back to back). The earlier one-line-at-a-time 40 KiB echo lost about 1 line in 3,100.
- The core step is about 5 of the 7 ms mean round trip. The Train Pi's 600 s run (core step 0.06 ms) had p99 2.55 ms, max 5.21 ms; the two are not comparable, the work is different.
- Pi agent log: 6 `SLOW_STEP`/`SKIPPED_LINE` lines in total, 5 before this run. The new line is the cold-cache `SLOW_STEP tick=1` (14.1 ms total, 13.6 ms core) that each replay logs, which is also this run's core-step maximum (13.63 ms).
- One run, one boot. The lean checkpoint is exercised only if a checkpoint was taken during the run (it is taken every `CHECKPOINT_TICKS`); no checkpoint line was inspected here; the 600 s run below does.
- Not done: 600 s run, repeat of the 180 s run, any change to how VIEWs are sent.

### 600 s Track replay on hardware (`5d19539`, agent hash 0a7cf856, 600 s Red recording, `--hz 100`, unpinned, tolerant probe)

60,006 of 60,006 requests in 654.7 s (91.65 Hz, the host pacing limit; 25,058 late sends), `error` null.

| | 600 s | 180 s |
| --- | --- | --- |
| RTT mean / p95 / p99 / max | 7.45 / 8.40 / 9.34 / 16.23 ms | 7.09 / 8.02 / 8.80 / 16.24 ms |
| Round trips over 10 ms | 261 of 60,006 (0.43%) | 44 of 18,006 (0.24%) |
| Pi core step mean / p95 / p99 / max | 5.29 / 5.55 / 5.77 / 9.55 ms | 4.96 / 5.19 / 5.40 / 13.63 ms |
| Request / reply bytes | 102,378,062 / 879,380,911 | 30,729,538 / 263,971,732 |
| `lines_lost` / `views_lost` | 105 / 105 | 22 / 22 |
| `resends` / `duplicate_replies` | 0 / 0 | 0 / 0 |

- The core step is about 5.3 of the 7.45 ms mean round trip (71%); the PLC step in `plc.py` (not touched) is where the time is. The link and the rest add about 2 ms.
- p99 is under the 10 ms budget with under 1 ms of margin; 0.4% of round trips are over it.
- All lost lines are VIEWs, about 3.2% of the roughly 3,270 sent (derived, one per 0.2 s). No step reply was damaged in either run.
- The two core-step maxima are the cold first step of each replay (`SLOW_STEP tick=1`: 13.7 ms in the 180 s run, 9.6 ms in this one). The 16.2 ms maximum round trip is the same in both runs and appears in the first minute of both; it is **not** the cold first step (this run's first step was only 9.6 ms of core time). Not explained; the Pi log's `SLOW_ACK` lines of 11-23 ms at the start of a replay are a candidate.
- **The 261 round trips over 10 ms are not explained.** Pi side (`/var/lib/track-overflow/agent.log`, which holds seven replays, about 78,000 steps): 7 `SLOW_STEP` lines (threshold 10 ms), six of them the cold first step of each replay (12.5, 14.1, 13.3, 13.1, 14.1, 10.1 ms) and one at tick 1337 (11.1 ms total, 5.4 ms core, no disk, checkpoint or tty time). So the Pi's own handling of a request is almost never over 10 ms. The Pi's timer starts when it has read a request, so time spent before that read is not in it. A VIEW's decode on the host is about 0.4 ms (sandbox), too small to explain it. Not checked: `SLOW_VIEW`/`SLOW_ACK` lines in the Pi log, host timer jitter, link time.
- **Lean checkpoint on hardware:** 133 `CHECKPOINT` lines in the log = 30 (180 s run) + 100 (this run) + 3 (the aborted 1,885-sample run). The file `session.json.ckpt100` is **183,072 bytes**, and `session.json` is 182 bytes. No `SLOW_STEP` line carries a checkpoint time (`ckpt_pickle_ms` is 0.0 on all seven). Sandbox, same recording: checkpoint file 182,854 bytes at the first checkpoint (step 600) and 183,064-183,079 bytes at checkpoints 2-20, so it does not grow. The file is `(core, reply cache)`: the core alone pickles to 66.6 KB (the lean figure above), the cache adds 101.0 KB (7 entries), pickle time 1.3 ms. The earlier "459 KB -> 66 KB" is the core only; against the previous code the file would be about 560 KB.
- Not done: any change to how VIEWs are sent; the 10x and window runs; `measure --system` against real Pis; the original-versus-now comparison.

### The rest of the Pi agent log, and what a VIEW costs the Pi (after the 600 s run)

- Every replay starts the same way in `agent.log`: `SLOW_HELLO` (14-22 ms), four or five `SLOW_ACK` lines (the load actions, 10.7-23.6 ms; the first replays were slowest), then the cold `SLOW_STEP tick=1`. There is **no `SLOW_VIEW` line**, and no `SLOW_HELLO`/`SLOW_ACK` mid-run. The only mid-run slow line in about 78,000 steps is tick 1337 (11.1 ms, core 5.4 ms, nothing in disk, checkpoint or tty).
- The 16.2 ms maximum round trip in both runs matches the slowest startup ACK of those two replays (14.3 ms on the Pi in both) plus about 1.9 ms of link time. By number-matching, not by trace.
- Cost of one VIEW on the Pi (sandbox, Red recording): `core.view()` 1.42 ms, encode 0.39 ms, CRC 0.02 ms, about 1.8 ms, then a 41 KB write. It is done after the step reply and before the next read, so it is outside the Pi's per-step timer, which only logs a VIEW over 10 ms. Host-side decode of a VIEW is 0.38 ms (sandbox).
- With the step at about 5.3 ms, that leaves little spare room in a 10 ms period, so a request that arrives while the Pi is still on the VIEW has to wait. This is a hypothesis; the numbers are only consistent with it.

### Change: `bringup --trace-csv FILE` (host side only; off by default; no wire or Pi change)
One row per answered request: `sample, sent_at_s, op, rtt_ms, core_ms, send_late_ms, views_before_send, views_after_send, resent`. `views_after_send` counts VIEWs (damaged ones too) that arrived between sending the request and its reply, which is the case where the Pi was probably still busy with the previous VIEW. `send_late_ms` is how late the host sent it against its own schedule. `tracestats.py` (scratchpad only, not in the repo) groups the round trips over 10 ms by those columns.
Tests (3 new): shape and one row per sample; a request sent again is flagged and timed from its first send; no file without the option. `common/hw_link`: 237 passed, plus the 2 known `test_bundle_is_offline_stdlib_and_shell_parses` cases that need physical Pis.
Known sandbox quirk, present on `e3077ae` as well and not looked into: `bringup --transport process` with the Red Track recording does not finish here, even with `--timeout 8`. The Train module's process and pty tests pass; the serial path used on the hardware does not go through it.

## Track Pi: the core step is slower in each later replay of one agent process (180 s Red replays, `743fc80`, agent hash 0a7cf856, unpinned)

Same recording, same host, same setup each time; the replays run one after another in one agent process, and a fresh process starts at the first row. Core step mean (Pi side, ms), then the p99 and round trips over 10 ms:

| Run set | Replay 1 | Replay 2 | Replay 3 |
| --- | --- | --- | --- |
| first set (180 s, then 600 s, then 180 s with trace; after a service start) | 4.96 | 5.29 (600 s run) | 5.59 |
| `r1`-`r3` (after `systemctl restart`) | 4.68 (p99 5.06, 91 over) | 5.26 (5.76, 195) | 5.54 (6.01, 202) |
| `d1`-`d3` (after `systemctl restart`; default allocator again) | 4.66 (5.12, 130) | 5.22 (5.85, 176) | 5.59 (6.22, 90) |
| `m1`-`m3`, `PYTHONMALLOC=malloc` | 5.38 (5.77, 246) | 5.90 (6.39, 520) | 6.06 (6.55, 528) |
| fresh process, single run (`b`) | 4.65 (4.99, 71) | | |

- Round-trip p99 (ms): 9.05 / 10.17 / 10.19 (`r`), 9.37 / 9.92 / 9.52 (`d`), 10.43 / 11.41 / 11.32 (`m`). The over-10 count is not monotonic (`d`: 130, 176, 90), so it is a noisy measure; the core step is not.
- Core compute per replay (18,000 step replies times the mean): 83.9, 94.0, 100.6 s for `d1`-`d3`.
- **Each replay is flat from its first tenth to its last** (core step per tenth of the run, `r1`: 4.65-4.69; `r2`: 5.24-5.27; `r3`: 5.52-5.57). The level is set when a replay starts, and does not creep during it.
- The step sizes shrink (+0.58 then +0.28; +0.52 then +0.16 with `malloc`), which may mean it levels off; only three replays per process were run, so this is not known.

### Ruled out
- **Memory growth and threads:** the agent's memory goes 28.1 to 33.4 MB over the first two replays and stays at 33,392 kB through the whole third, which is still the slowest; two threads throughout.
- **Heat and power:** the Pi peaked at 59.8 C; `get_throttled` read 0x0 after the first set (the high bits record events since boot) and the clock was 2.4 GHz. Not re-read after the later sets.
- **Python's small-object allocator:** `PYTHONMALLOC=malloc` is 0.5-0.7 ms slower at every replay and climbs by about the same; the setting was removed again (the `d` runs match the default pattern). This does not rule out memory layout in general.
- **Thread placement:** `ps -L` every 10 s during `d1`-`d3`: the main thread (about 53% of one core) moves among all four cores in every replay, with no pattern; the journal thread is the same thread in every session and used about 7 s of CPU in 9 minutes. The dwc2 USB interrupt (33) is handled only on CPU 0 (2,021,535 interrupts between the two snapshots, about 3,500 per second if they bracket just the three replays); IRQ affinity allows 0-3.
- **State that accumulates in the agent** (local, in process, same recording, four sessions in one `PiLinkServer`): the pickled core is 66,642 bytes after every session, the reply cache stays at 7, gc objects 123,488 / 123,406 / 124,124 / 124,487, and no type grew by more than 50 in a fifth pass. The PLC code (`plc.py`) is an interpreter with no module state; the only cache in the Track code is `lru_cache(maxsize=16)` on `vital_source`.
- **Garbage collection** (local): about 0.002 ms per step; one gen2 collection of 42 ms in the fourth pass; none that large seen in the Pi data.
- The sandbox does not reproduce the climb: core step 2.82, 2.97, 2.96, 2.96 ms over four passes (a +5% step, then flat), so the effect is bigger on the Pi (+12%, +20%).

### Not known, not tried
The cause. Untested ideas: heap layout after a session has been dropped (not allocator-specific); freeing the previous session's core before the next is built (`_start` builds the new core while the old is still referenced); keeping the agent off CPU 0, where all USB interrupts land (an earlier pinning A/B was on the Train Pi, whose core is much lighter); a function-level profile on the Pi of replay 1 against replay 3.
Practical effect: restart the agent (`sudo systemctl restart track-overflow-agent.service`) before a run that is to be compared with others. Without that, the second and later replays have a round-trip p99 near the 10 ms budget.

### Where the later-replay slowdown is (py-spy on the service, then an in-process benchmark on the Pi)

**Profile of the running agent** (`py-spy record -r 100 --nonblocking`, three replays of the first 4,000 lines of the Red recording, 3,994 steps each, fresh process; core step on the host lines 4.72 / 5.32 / 5.63 ms). Sampled time per step: 5.19 / 5.52 / 6.13 ms (+0.94). About 0.8 ms of the +0.94 is inside `Wayside._run_program` (inclusive 3.83 -> 4.63 ms). Self time, replay 1 -> 3:

| Function | ms per step, 1 -> 3 | Change |
| --- | --- | --- |
| `_walker.<locals>.<lambda>` (plc.py, channel A closures) | 0.719 -> 1.139 | +0.421 (+59%) |
| `Program.scan_a` | 0.533 -> 0.749 | +0.215 |
| `_run_postfix` (channel B) | 1.292 -> 1.427 | +0.135 (1.470 in replay 2) |
| `Program.scan_b` | 0.591 -> 0.689 | +0.098 |
| `JSONEncoder.iterencode` | 0.228 -> 0.303 | +0.075 |
| `Wayside._run_program` own lines, `Wayside.scan`, `overrides`, `main` | flat or falling | |

**In-process benchmark on the Pi** (`plcbench.py`, scratchpad only: new HELLO session per pass, real `PiLinkServer` and Track core, no USB, no service; Python 3.13.5; `PYTHONOPTIMIZE=1`; the same 4,000 lines; ms per step). The climb reproduces without the service, USB, the journal thread or the tty:

| Session | Core | Channel A | Channel B | Rest |
| --- | --- | --- | --- | --- |
| 1 | 4.241 | 1.218 | 1.726 | 1.298 |
| 2 | 4.791 | 1.501 | 1.973 | 1.316 |
| 3 | 5.117 | 1.718 | 2.073 | 1.326 |
| 4 | 5.401 | 1.932 | 2.127 | 1.342 |

A second baseline run gave 4.234 / 4.794 / 5.126 / 5.434 (deterministic). Channels A and B are 1.11 of the 1.16 ms climb; channel A keeps rising (about +0.2 ms per session), channel B levels off near 2.2.
- `--variant collect` (`gc.collect()` before each session): 4.188 / 4.808 / 5.139 / 5.327. No change; leftover garbage is not the cause.
- `--variant flat` (channel A as one generated expression per statement, patched in this process only): core 3.839 / 4.155 / 4.431 / 4.481 (level 0.40 ms lower in session 1, 0.92 ms lower in session 4); channel A 0.876 / 0.919 / 1.018 / 1.025 (climb +0.149 against +0.714); channel B still 1.742 -> 2.180 (+0.44); rest +0.055. **Equivalence:** `--verify` compared 23,964 channel A scans on the Pi and 23,964 in the sandbox, and 0 differed in both.
- Same code in my sandbox (x86, Python 3.13.18): 2.58 / 2.75 / 2.58 ms, no climb. The Pi runs Python 3.13.5; whether the version matters is not tested.

**What this says.** The slowdown starts at each new session and then holds for the whole run, appears in a bare process, grows with every new session, and resets in a fresh process. Channel A's closure tree is the biggest part of it (79% of A's growth disappears with the flat form), but channel B has no closures and still grows, so the closures amplify a more general effect. My leading explanation, not proven: each session creates a new set of small objects in a heap that earlier sessions fragmented, and the Pi's small caches make scattered objects expensive. It is not Python's small-object allocator, and not garbage, heat, thread placement or accumulated state.

**Options, none done:** restart the agent before a run; flat channel A for the owner of `plc.py` (vital logic with two deliberately different channels, so a review change, not made here; measured saving about 0.4 ms at session 1 and about 0.9 ms by session 4); start each session in a fresh process (removes the effect, changes how the agent starts a session and needs the host link to survive the restart).
