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
