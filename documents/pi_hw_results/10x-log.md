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

## Pi A/B test: core pinning (not run; needs the Pi)

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
