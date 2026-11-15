# Issue drafts for the module owners

**Status:** text to paste into GitHub issues, one per owner. Nothing has been posted. Branch `hw_pi_test`: https://github.com/Landiss04/Track-Overflow/tree/hw_pi_test. Every change here is its own commit and can be reverted alone. The fuller write-up, with the evidence, is `what-was-changed.md` (section 3) in this folder.

| Issue | Assignee | Commit |
| --- | --- | --- |
| 1. PLC channel A (TrackCtrlHw, the hardware Track Controller) | `brabosil3` | `1861469` |
| 2. Train Model redraw rate | Kevin Schillinger (pick him in the Assignees box; his GitHub login is not recorded here) | `7474cc4` |
| 3. CTC Office redraw interval | `Landiss04` | `b066cde` |
| 4. Shared harness and launcher code (optional) | whoever owns the harness; not assigned | `3929c46`, `bf21405` |

The truth index names **Harry Tye** as the owner of the Track Controller module and leaves the CTC Office unassigned; the assignees above were chosen by the user. If Harry Tye should also be told about Issue 1, add him as a reviewer or mention him in the issue.

---

## Issue 1

**Title:** Review: PLC channel A as one expression per statement (TrackCtrlHw)

**Assignee:** `brabosil3`

**Body:**

Branch `hw_pi_test`, commit `1861469`. Files: `TrackCtrlHw/track_ctrl_hw/plc.py` and `TrackCtrlHw/tests/test_plc.py`. This is vital logic, so it needs the owner's decision before it goes near `development`.

**What changed.** Channel A's parse trees now run as one generated Python expression per statement, built with `eval`, instead of nested closures (one call per node):

```python
lambda v: ((v.get('A', False) and v.get('B', False)) or (not v.get('C', False)))
```

The logic is the same: AND and OR still stop early, XOR is `!=`, NOT is `not`, and an undefined name reads False. A tree too deep to compile falls back to the old nested form. Channel B, the compiler, the parser, the checksums and the checkpoint contents are unchanged. The agent hash changes (0a7cf856 to 8d1c457a) because it covers the core files.

**Why.** On the Track Pi at 10x the core step is 4.7 to 5.6 ms of a 10 ms slot and about 95% of it is the PLC interpreter. The Track Controller's reply was above the slot, so the system ran at 8.45x.

**Result.** Track Pi real, stress schedule, 600 s, 10x: 8.45x before, **9.94x, 9.49x (a run disturbed by host stalls) and 9.99x** after. Track Controller reply mean 10.2 ms to 8.6-8.9 ms.

**Evidence that the answers are the same.** 256,000 random-tree evaluations, 18,000 scans of the six real Red programs and 23,964 replayed scans differ in 0 cases. A new unit test covers 500 random trees and the fallback. All 118 tests in `TrackCtrlHw/tests` pass. **The Green programs are not covered.**

**Please decide**
1. Is `eval` of generated code allowed in vital logic? A version without `eval` is possible but gives up most of the saving.
2. Are channels A and B still diverse enough? A is still a recursive-descent tree with short-circuiting and B a postfix stack machine, but A is now compiled Python rather than closures. If the rule is that PLC programs are interpreted and never compiled to host code, this should be reverted.
3. Is the evidence enough, given it does not include the Green programs?

Details and the benchmark on the Pi: `bench/pi_hw_results/plc-channel-a-flat-proposal.md`. Undo: `git revert 1861469` and reinstall the Track bundle.

---

## Issue 2

**Title:** Review: Train Model redraw rate when the harness finds software rendering

**Assignee:** Kevin Schillinger

**Body:**

Branch `hw_pi_test`, commit `7474cc4`. Files: `TrainModel/train_model/module_process.py`, `TrainModel/tests/test_view_interval.py`, `TrainModel/CHANGELOG.md`.

**What changed.** When the harness finds Qt Quick rendering in software, it sets the environment variable `TRACK_OVERFLOW_LOW_FRAME_RATE` and the Train Model redraws 4 times a second (0.25 s) instead of 20. `VIEW_INTERVAL_S` is renamed `FULL_VIEW_INTERVAL_S` (still 0.05 s); new `LOW_VIEW_INTERVAL_S` and a function `view_interval_s()`. With hardware rendering nothing changes, and no step output changes.

**Why.** A 2026-11-04 run with software rendering at 20 redraws a second used every CPU core, which cannot hold a 10 ms tick at 10x.

**Please decide**
1. Is 0.25 s right? It is a placeholder and has not been measured on the target machine. At 10x a moving train changes about 100 times a second, so 4 a second may look jerky.
2. Is it acceptable for the module to read an environment variable set by the harness, or should it be an explicit option?
3. Is the rename fine? Nothing in the repository imported the old name; the changelog now records it.

Details: `bench/pi_hw_results/what-was-changed.md` section 3.3. Undo: `git revert 7474cc4` (the harness warning stays).

---

## Issue 3

**Title:** Review: CTC Office window redraw interval at 10x

**Assignee:** `Landiss04`

**Body:**

Branch `hw_pi_test`, commit `b066cde`. Files: `CTC-Office/ctc/module_process.py` and `CTC-Office/tests/test_module_process.py`.

**What changed.** A new constant `WINDOW_REFRESH_MS_AT_SPEEDUP = 1000`. While the clock is at 10x the window redraws at most once a second; at 1x it still redraws every 200 ms. Nothing else changed: the reply to a STEP, the outputs and the schedule logic are the same.

**Why.** At 10x with the stress schedule (14 Green trains, 4 Red) the CTC Office's reply to a STEP is 4.5 ms at the median but p99 25 to 48 ms, with hundreds of stalls of 50 to 190 ms in 600 s. The window refresh (about 27 ms each, five times a second) is 25% of the process's busy time and behind 95 of the 170 stalls longer than 30 ms.

**Result.** All simulated, 40 s, alternated: 9.78x and 9.86x became 10.00x and 10.00x; CTC reply p99 about 40 ms became 13-17 ms. With the Track Pi real the speed did not change (the Track Controller sets the pace there), but the CTC tail is smaller.

**Please decide**
1. Is a window that shows data up to 1 s old at 10x acceptable? (A UI decision.)
2. Larger fixes were measured but not applied; see `bench/pi_hw_results/ctc-office-tail.md`: make the refresh itself cheaper (the cost is in the slots behind `stateChanged` and `clockChanged`), refresh less when no one is looking, and cache the route search (about 40% of the busy time, the source of 90-125 ms step stalls).

Undo: `git revert b066cde`, or set the constant equal to `WINDOW_REFRESH_MS`.

---

## Issue 4 (optional)

**Title:** Review: launcher core pinning and the software-rendering warning

**Assignee:** none; whoever owns the harness and launcher.

**Body:**

Branch `hw_pi_test`, commits `3929c46` and `bf21405`.

- `3929c46`: `track_overflow.py` and `utils/process_cores.py`. Pins the harness off the last cores and each Pi link process onto them. `TRACK_OVERFLOW_NO_PIN=1` turns it off; with fewer than four cores nothing is pinned. The Windows path was tested only against a stub.
- `bf21405`: `common/harness/app.py` and `utils/render_check.py`. At startup, warns when Qt Quick renders in software and sets `TRACK_OVERFLOW_LOW_FRAME_RATE` for the modules it starts (the variable Issue 2 reads).

Neither has been run on the target machine. Please say whether the pinning should stay on by default. Details: `bench/pi_hw_results/what-was-changed.md` section 3.4.
