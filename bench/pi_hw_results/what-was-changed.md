# What was changed on this branch, and what the module owners need to decide

**Status:** a description of the branch against `main` (`e3077ae`, Release 1.0), written from the commits. The numbers come from `10x-log.md` (every run, with the commit it ran on). Nothing here is a decision of the truth store, and no change to `truth/` is proposed.

## 1. In one table

The goal was a 10x simulation clock (a 10 ms slot per tick) with a real Raspberry Pi in the loop. Stress schedule `utils/schedule_stress.json`, 600 s, Windows host, headless harness:

| Setup | Speed | Notes |
| --- | --- | --- |
| All simulated, no Pi | 10.00x (two runs) | the host and harness can do 10x |
| Track Pi real, at the start of this work | 8.45x | Track Controller reply mean 10.2 ms, above the slot |
| Track Pi real, after the PLC change | 9.94x, 9.49x, **9.99x** | 9.49x run was disturbed by host clipboard stalls; Track reply mean 8.6-8.9 ms |
| Train Pi real | 7.60x, then **10.00x** | 10.00x with the current code and a clean host (the 7.60x run predates the CTC and PLC changes and had a noisier host); the Train Pi itself is not the limit |
| Both Pis real | not measured | estimated 7 to 8.5x at that time; only one board exists |

On the link alone (replay of the recorded Red workload), the Train Pi's round-trip p99 went from 18 ms to 2.5 ms with no round trip over 10 ms, because the journal write no longer blocks a reply behind an SD-card `fsync`.

## 2. What was changed

### Pi agent and cores (`common/hw_link/`)

| Commit | Change |
| --- | --- |
| `34cd60a`, `60d87e0`, `6d49406` | The agent keeps the journal handle open, queues journal records and writes them on a journal thread; at most 300 unsynced records before a reply waits for the disk. A reply no longer waits for `fsync`. **Durability trade-off:** after a crash, up to 300 steps of a Track recovery may be replayed (about 1.5 s of simulated time at the Pi's measured step). |
| `eb59160` | Checkpoint `fsync`, rename and journal swap run on a worker thread. |
| `2604414` | The Track core's checkpoint leaves out the compiled PLC programs and rebuilds them on restore (checkpoint file 183 KB, flat over 133 checkpoints on hardware). |
| `d7ba26e` | `TrainCore.step` rolls back the roster instead of deep-copying the fleet (Pi step about 0.06 ms); regression test for the all-or-nothing STEP. |
| `60e8210`, `20c894b` | The agent logs any reply over 10 ms with where the time went (`SLOW_STEP`, `SLOW_VIEW`, `SLOW_ACK`). |
| `0769b05`, `88b3cc5` | Agent unit: `Nice=-10`, `PYTHONOPTIMIZE=1`, performance governor (no CPU pinning: it showed no usable difference); `install.sh` restarts a running agent. |
| `a381a76` | A test that the Train HW core runs Green trains like the software controller. |

The wire protocol is unchanged. The agent hash (it covers the core files) is `0a7cf856` before the PLC change and `8d1c457a` from it on; the host and the Pi bundle must match.

### Host link tools (`common/hw_link/bringup.py`, `common/harness/measure.py`, `bench/`)

- `bringup`: reports p99 and round trips over 10 ms, prints the board and port, a progress line, opts out of Windows power throttling, and by default **acts as the host relay does** on a damaged line (skips a damaged display line, resends any other; counts `lines_lost`, `views_lost`, `resends`). `--strict` stops at the first damaged line. `--trace-csv` writes one row per answered request.
- `measure --system` (and `bench/per_module.py`): choose each hardware Pi's mode (`--track-controller-pi`, `--train-controller-pi`: `physical` or `process`), `--dispatch`, `--schedule`, per-tick CSV, and the report names the workload and Pi modes. The engineer's gains go to both Train Controllers. `bench/estimate_both.py` combines two one-Pi runs; `bench/tickstats.py` summarises one run; `bench/pi_test_menu.cmd` runs the standard tests from a numbered menu.
- Launcher and harness: `3929c46` pins the harness off the last cores and each Pi link process onto them (`TRACK_OVERFLOW_NO_PIN=1` turns it off); `bf21405` warns at startup when Qt Quick renders in software (and sets `TRACK_OVERFLOW_LOW_FRAME_RATE` for the modules it starts).

### Documentation (`bench/pi_hw_results/`)

`guide-track-controller-pi.md`, `guide-train-controller-pi.md` (step by step), `pi_setup_how_to.md` (the longer runbook), `10x-log.md` (every run), `10x-final-report.md`, `HANDOFF.md`, `commits-for-owner-review.md`, `owner-issues.md` (drafts of the GitHub issues for the owners), `plc-channel-a-flat-proposal.md`, `ctc-office-tail.md`, and this file.

### Unresolved, and what it means

- A Track core runs slower in each later session of one agent process (4.7, 5.2, 5.6 ms in three replays). Cause not found. Restart the agent before a run you will compare.
- 0 to 3% of display lines (VIEW) are damaged on the USB link in a run; cause not found; display-only, and the relay skips them.
- Runs that start with Windows clipboard errors (`qt.qpa.mime`) stall several modules at once and lose about 0.45x. The code does not use the clipboard; Qt on Windows does. Turn clipboard history off and copy nothing before a run.
- Not run: both Pis real together; the flat PLC channel on the Green programs; the render warning and the Train Model frame-rate change on the target machine.

---

## 3. For the module owners

Each of these is a change to code the owner is responsible for. Each is one commit, self-contained, and can be reverted alone. None has been reviewed by its owner. The truth index names no owner for some of these modules, so "owner" means whoever is assigned to the module. The same list, with every commit that touches a shared area, is in `commits-for-owner-review.md`.

### 3.1 CTC Office owner: commit `b066cde`

**File:** `CTC-Office/ctc/module_process.py` (and one test in `CTC-Office/tests/test_module_process.py`).

**What changed.** A new constant `WINDOW_REFRESH_MS_AT_SPEEDUP = 1000`. While the clock is at 10x the window redraws at most once a second; at 1x it still redraws every `WINDOW_REFRESH_MS` (200 ms). Nothing else in the module changed: the reply to a STEP, the outputs and the schedule logic are the same.

**Why.** At 10x with the stress schedule (14 Green trains, 4 Red) the CTC Office's reply to a STEP is 4.5 ms at the median but p99 25 to 48 ms, with hundreds of stalls of 50 to 190 ms in a 600 s run. A profile (`ctc-office-tail.md`) showed the process busy 54% of the time; the window refresh (`CtcHost._refresh`, about 27 ms each, five times a second) is 25% of that and was behind 95 of the 170 stalls longer than 30 ms. The other stalls (75) are the per-step route search, below.

**Evidence.** All simulated, 40 s, alternated, two runs each: speed 9.78x and 9.86x became 10.00x and 10.00x; CTC reply p99 41 and 39 ms became 13 and 17 ms. On the Windows host with the Track Pi real, 600 s: speed unchanged at 8.45x (the Track Controller sets the pace there), the CTC no longer the slowest module in 5% of ticks (1.3%), round-trip p95 19.7 to 15.3 ms, max 244 to 72 ms.

**What the owner decides.**
1. Whether a window that shows data up to 1 s old at 10x is acceptable (a UI decision). The constant can be set equal to `WINDOW_REFRESH_MS` to turn the change off, or `git revert b066cde`.
2. Whether to take the larger fixes instead (none applied): make the refresh itself cheaper (the cost is in the slots behind `stateChanged` and `clockChanged`, not `snapshot()`, which is 0.21 ms); refresh less when no one is looking; cache the route search by train block and destination until the graph or occupancy changes (about 40% of the busy time, the source of 90 to 125 ms step stalls).

**Risk.** Low: the change is only in the redraw timer. Not seen on a target machine with a GPU; on the test host the window does paint.

### 3.2 TrackCtrlHw owner (the PLC interpreter): commit `1861469`

**File:** `TrackCtrlHw/track_ctrl_hw/plc.py` (and tests in `TrackCtrlHw/tests/test_plc.py`). **This is vital logic: please review it as such.**

**What changed.** The PLC program is evaluated on two channels, A (a tree of nested Python closures, one call per node) and B (postfix code on a stack machine). Channel A's trees are now compiled, on the first scan as before, into **one function per statement**, written as the text of one Python expression and built with `eval`:

```python
lambda v: ((v.get('A', False) and v.get('B', False)) or (not v.get('C', False)))
```

- Logic is the same: `AND` and `OR` still stop early, `XOR` is `!=`, `NOT` is `not`, an undefined name still reads False.
- A tree too deep to compile (`SyntaxError`, `RecursionError`, `MemoryError`) keeps the nested closures. None of the 1,151 statements in the six Red programs takes that path.
- Channel B, the compiler, the parser, the checksums, the diagnostics and what a checkpoint stores are unchanged.
- The only text put into the generated expression is `repr()` of a name the tokenizer already restricted to `[A-Za-z_][A-Za-z0-9_]*`, a constant's `repr`, and the fixed operators; `eval` runs with empty globals.

**Why.** On the Track Pi at 10x the core step is 4.7 to 5.6 ms of a 10 ms slot and 95% of it is the PLC interpreter. The reply of the Track Controller was above the slot in typical ticks, so the system ran at 8.45x.

**Evidence.**
- Same answers: 256,000 evaluations of 4,000 random trees; 18,000 scans of the six real Red programs; 23,964 scans replayed from a recording; a unit test over 500 random trees plus one for the fallback; all 118 tests in `TrackCtrlHw/tests` pass.
- Speed: Track Pi real, 600 s at 10x: Track Controller reply mean 10.17 to 8.56-8.88 ms, p50 9.64 to 8.1-8.3 ms; system 8.45x to 9.94x, 9.49x (disturbed host) and 9.99x. All simulated: 10.00x.
- Details and the benchmark on the Pi: `plc-channel-a-flat-proposal.md`.

**What the owner decides.** Not me:
1. **Whether `eval` of generated code is allowed in vital logic at all.** A version without `eval` (a nested function built from the same text) is possible but gives up most of the saving.
2. **Whether channels A and B stay diverse enough.** A is still a recursive-descent tree with short-circuiting and B is still a postfix stack machine, but A is now compiled Python rather than closures. If the project's rule is that PLC programs are interpreted and never compiled to host code, this change breaks the rule even though the program the engineer writes is unchanged, and it should be reverted (`git revert 1861469`; reinstall the Track bundle).
3. Whether the equivalence evidence is enough. It covers the Red programs and random trees, **not the Green programs**.

**Risk.** Medium, because it is vital logic. The result is the same on every check we ran, but the change is in how the interpreter executes the program.

### 3.3 A third: Train Model (commit `7474cc4`)

**File:** `TrainModel/train_model/module_process.py` (and `TrainModel/tests/test_view_interval.py`). When the harness finds Qt Quick rendering in software, it sets `TRACK_OVERFLOW_LOW_FRAME_RATE` and the Train Model redraws 4 times a second instead of 20 (0.25 s is a placeholder). Written but **not measured on the target machine**; no effect when rendering is hardware. Revert with `git revert 7474cc4`. The Train Model owner should confirm the interval.

### 3.4 Shared code (for whoever owns the harness and launcher)

`3929c46` (process pinning in `track_overflow.py` and `utils/process_cores.py`) and `bf21405` (software-rendering warning in `common/harness/app.py` and `utils/render_check.py`) change how every module is started. The pinning can be turned off with `TRACK_OVERFLOW_NO_PIN=1`; both can be reverted. Windows pinning was tested only against a stub.
