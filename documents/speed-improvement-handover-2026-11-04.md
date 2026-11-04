# Speed improvement work: handover (2026-11-04)

Branch `integrate/quirky-into-development-resolved`. Two Claude sessions did this work:
- **speed-improvement-fixes**: production changes.
- **speed-improvement-reg-tests**: regression tests and every test or performance run in this log.

The aim is enough headroom at 10x for the full system to run on the target, a Snapdragon X2 Plus with 6 cores. The target has the full GUI, trains running and PLC programs loaded. Both Pi agents run on the real Raspberry Pis, not on the PC.

## Where it stands

| Commit | What |
|---|---|
| `cede5cb` | Baseline before this work |
| `f452a64` | Regression tests (codec, STEP before VIEW, ModuleLink ownership) |
| `0345b24` | Production: one-pass Pi codec, STEP before VIEW, capped redraws, auto-run delay, no vsync |

`0345b24` is pushed. The working tree is clean apart from 8 unrelated untracked files that were already there before this work.

Software rendering (r6) does **not** keep up on 6 cores: CPUs 0–5 are saturated and nearly half the ticks are dropped. With GPU rendering, the same code runs cleanly.

## Changes, in order, and what happened to each

### 1. Pi codec: one pass instead of encode, parse, encode
- **What changed**
  - `common/hw_link/protocol.py`: encode is now Pi validate plus `hp._dump`; decode is `hp._parse` plus Pi validate.
  - `utils/harness_protocol.py`: split into `_dump` and `_parse` so the Pi codec can share them. Public behaviour is unchanged.
- **Known differences from the old codec**
  - Keys that collide after JSON coercion, such as `{1:"a","1":"b"}`, are now written twice on the wire. They decode to the same dict.
  - The Pi decode error wording now matches the shared codec. It is still `ProtocolError`.
- **Tests**: `common/hw_link/tests/test_codec_regressions.py`, 85 cases.
  - These pass on both the old and the new code, as compatibility tests should.
  - Two weakened mutants were caught: one with the surrogate check removed, one with `ensure_ascii=True`.
- **Result**: no regressions.

### 2. Agent writes the STEP reply before building its periodic VIEW
- **What changed** in `common/hw_link/agent.py`:
  - `_handle` and `_replies` are now generators.
  - `main()` writes each reply completely before the next one is produced.
  - Journal, cache and checkpoint writes still happen before the acknowledgement.
  - `handle()` and `feed()` still return lists.
- **Tests**: `common/hw_link/tests/test_step_reply_order.py`, 5 tests.
  - They run through `agent.main()` with fake file descriptors, short 5-byte writes, a fake core and a fake clock.
  - 3 of them fail on `cede5cb` for the intended reason: the VIEW is built before any byte of the reply is written.
- **Result**: passes on the new code.

### 3. ModuleLink deferred STEP: one deep copy removed
- **What changed**: `utils/module_link.py` now passes the decoded message to the deferred handler. The stored `_pending_request` remains the link's own deep copy.
- **Tests**: `utils/tests/test_module_link.py`, 4 new tests. A mutant with a shallow pending copy is caught.
- **Result**: passes.

### 4. Redraw caps and auto-run delay (edit 1), which caused 4 regressions
- **What changed**
  - Train Model `snapshotChanged` limited to 20/s for every change.
  - CTC `--run-delay-s`.
  - Harness `AUTO_RUN_DELAY_S = 10`.
- **Why it failed**
  - `TrainModel/train_model/link.py:215` relays `snapshotChanged` to the test harness. The limit delayed the passenger emergency-brake command and output values there by up to 50 ms. This broke 2 tests in `test_ui_sync` and `test_harness_clock::test_clock_controls_in_the_real_test_ui`.
  - The 10 s delay was longer than the 8 s `--run-seconds` in `test_cli_modes_keep_options_and_exit_cleanly` (system mode), so that test ended at tick 0.
- **First full-GUI run (r1) was invalid**: the desktop was locked (`LockedHint=yes`) and no window was exposed, so nothing rendered.

### 5. Edit 2 fixed those regressions
- **What changed**
  - The limit is opt-in: `view_interval_s=0` by default. Only the harness-driven `TrainModel/train_model/module_process.py` sets 0.05.
  - Only tick-driven refreshes go through the limit; user actions update immediately.
  - `AUTO_RUN_DELAY_S` is now 3.0.
- **Units**: all pass. The only failures left are the known baseline ones below.
- **r2**
  - The windows were rearranged during the run, so only the stretch from +155 s counts. That stretch had 0 drops.
  - Train Model still drew 22–26 frames/s, above its cap.
  - There was one slip of 101 ticks at +49 s.

### 6. Edit 3: clock drift goes through the limit
- **Cause of the 22–26 frames/s**: `set_clock_drift` emitted directly, about 6.7 times a second at 10x, on top of the limited tick updates.
- **Fix**: it now calls `_notify()`.
- **r3**: Train Model at or under about 20 frames/s, 0 slips, CPUs 0–5 about 28% busy.
- **Correction**: in r2 I blamed the Train Model drop from 20 to 10 frames/s at about +45 s on the window rearrangement. It happens in every run, so it is a change in what the model is doing.

### 7. Edit 4: no vsync, fixing the slips while windows are resized
- **Cause**: with vsync, each resized frame blocks that window's GUI thread until the next display refresh. The same thread answers STEPs, so a long drag slips the clock. CPU stayed at about 25% and no main-thread stall exceeded 100 ms.
- **Fix**: `track_overflow.py main()` calls `os.environ.setdefault("QSG_NO_VSYNC", "1")`. The harness and every module it spawns inherit it.
- **r4 was misleading**: the stress wrapper `run_gui.py` called `app.main()` directly, so the harness never got the variable.
  - The harness drag dropped 502 ticks (5 slips).
  - The module drags dropped none.
- **r5, after the wrapper was fixed to go through `track_overflow.main()`**
  - 0 slips in all 4 drags, 500 ticks per 5 s.
  - The modules' start-up environment showed `QSG_NO_VSYNC=1`.
  - The harness drew up to 102 frames/s during its drag, against 50 with vsync.
  - Outside drags, frame rates were unchanged: no window draws continuously.

## Performance summary (all runs with CPUs 0–5 for the system, Pi agents pinned to 6–7, 10x, 600 s)

| Run | Rendering | Slips / dropped | Ticks per 5 s (inner) | Round trip mean / max | CPUs 0–5 mean | Notes |
|---|---|---|---|---|---|---|
| Pre-fix `stress` | software | 125 / 12 395 | median 326, min 143 | 11.3 / 759 ms | 65% (max 95) | old tree in `/tmp/.../after` |
| r3, edit 3 | GPU | 0 / 0 | 499–502 | 7.08 / 42.7 ms | 28% | all windows exposed |
| r5, edit 4b, with drags | GPU | 0 / 0 | 497–503 | 7.16 / 50.6 ms | 31% | Train Model lost exposure in its drag |
| r6, current code | software (llvmpipe) | 275 / 27 734 | median 282, min 120 | 18.4 / 720 ms | 93.5% (all six ≥95% in 53 samples) | all windows exposed; final tick 31 750 of about 59 700 |

Frames/s per window in steady state: CTC Office 14.6, Train Model 10 (20 while trains move), Train Ctrl SW 10, harness 10, Track Model 9.2, Track Ctrl SW 5, Track Ctrl HW and Train Ctrl HW 4.8.

## Open issues
1. **Software rendering is CPU-bound (r6, 600 s, `LIBGL_ALWAYS_SOFTWARE=1`).**
   - `QSG_INFO` lines confirm `llvmpipe (LLVM 21.1.8)`. The screen was unlocked throughout (61 of 61 checks) and every window stayed exposed.
   - Ticks: 275 TIME_SLIPPED events and 27 734 ticks dropped; ticks per 5 s median 282 (min 120, max 335). The run reached tick 31 750; at 100/s it should have reached about 59 700.
   - Round trip mean 18.4 ms, max 720 ms.
   - CPUs 0–5: time-weighted mean 93.5%. 53 samples had all six CPUs at or above 95%, starting from +6 s.
   - CPU per process, as % of one core: ctc-office 102, harness 92, track-model 71, train-model 61, track-controller-hw 59, train-controller-sw 51, track-controller-sw 49, train-controller-hw 28.
   - Frames/s, median: CTC Office 9.8, harness 10, Track Model 7.8, Train Model 6.0 (max 18.6, never above 20), the rest about 5–10. Drawing slows too, but the cost is mainly the per-frame software rasterising.
   - Start-up: ALL_READY at +2.07 s, Run pressed at +3.58 s, CPUs already about 90% in the 10 s around the press.
   - Against the pre-fix software run (`stress`, older tree): that run averaged 65% CPU with a median of 326 ticks per 5 s; r6 is worse. The difference may come from different pinning and windows, and is not explained. Neither run is acceptable.
   - Next steps to consider: much lower frame caps or static views when software rendering is detected; confirm the target's GPU driver works on Windows ARM (D3D11/12 backend, not WARP).
2. **Train Model window loses exposure about 1–2 s into a scripted drag.** It happened in r4 and r5 at the same point. The window still exists but `isExposed()` stays false to the end of the run. The cause is probably the hook's `drag()`, possibly its `showNormal()` call; this is not verified.
3. **Baseline failures, not caused by this work:**
   - `common/harness/tests/test_red_owner_diagnostics.py::test_review_red_trains_go_out_together[2]` and `[3]` fail with `('to yard',…) == ('held',…)` on `cede5cb` too. This is CTC or dispatch behaviour.
   - `utils/tests/test_clock_driver.py` has intermittent wall-clock tolerance misses.
4. **CPU difference between r5 and r4**: r5 was about 2.6 points higher. It is unexplained and may just vary between runs.

## How to test
Unit suites, one at a time from the repo root, using the venv interpreter `/home/kevin/ECE/Trains/.venv/bin/python`:
```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 /home/kevin/ECE/Trains/.venv/bin/python -m pytest -p no:cacheprovider -q TrainModel/tests
```
Run the same command for `CTC-Office/tests`, `common/harness/tests` (about 5 min), `utils/tests` and `common/hw_link/tests`.

Full-GUI run:
```bash
/tmp/to-perf-1GMRPz/run_stress.sh /home/kevin/ECE/Trains/Track-Overflow <outdir> 600 [RESIZE_PLAN=...] [LIBGL_ALWAYS_SOFTWARE=1]
```
- The screen must be unlocked for the whole run. Check before and after:
  ```bash
  loginctl show-session <id> -p LockedHint -p IdleHint
  ```
  Session 110 was used here.
- Do not set `QT_QPA_PLATFORM` for this run.
- Run nothing else that is CPU-heavy at the same time.
- A run is valid only where every window renders and is exposed in each 5 s frame record.

## How to measure
The analysis scripts are in the previous session's scratchpad, `/tmp/claude-1000/-home-kevin--claude-spares-spare-rfPolG/df2d0535-e714-49ee-8c08-ab61dd1fe374/scratchpad/`. `/tmp` may be cleared, so copy them if you need them.
- `analyse.py <run> [valid-start-epoch]`: status lines, per-window frame series, exposure, CPU, start-up.
- `drags.py <run> <reference run>`: per-drag ticks, stalls and frames.
- `compare.py <run>...`: the same summary for any runs, including old ones without frame logs.

Inputs written by each run: `run.out` (status lines every 5 s), `logs/*.csv` (events with wall time), `samples.jsonl` (CPU), `frames/*.jsonl` and `frames/stalls-*.log` (from the `/tmp/to-perf-1GMRPz/hook` sitecustomize).

## Lessons
- Check `LockedHint` and the window exposure records before trusting any frame or CPU figure.
- A test wrapper must start through the production entry point (`track_overflow.main`), or environment changes made there are silently skipped.
- Signal throttling also delays anything else listening to that signal, such as the test-harness relay. Scope it to the view path only.
- The Qwen delegate made no progress on the codec tests: 45 minutes with provider retries and no edits. Plan to do the work locally.
