# Train-Ctrl_HW — changes for review

Everything changed in the HW Train Controller module since Ivan's last commit
(`493f16e`, "update compiled Python bytecode for check.py"), up to the
vital power command (2026-10-24). Work by Jonathan Tsang, with Claude. Open, unfixed items are in
[`OPEN_ISSUES.md`](OPEN_ISSUES.md); rules and their status in
[`REQUIREMENTS.md`](REQUIREMENTS.md).

Base for every check below: `python main.py --check` (run with the module's
venv) — 0 QML warnings, 0 behaviour problems at `700d83d`, and again after
the 2026-10-21 changes.

---

## 1. Where things stand (net effect)

### Control and safety (`train_ctrl/`)

| Area | Behaviour now |
|---|---|
| Maximum power | 480 kW (truth `modules/train-model.md`: 4 × 120 kW, provisional). Before: 120 kW, which held the rated 0.5 m/s² only to about 10 mph; now to about 67 km/h (0 → 70 km/h in 43 s). |
| Traction under braking | Power is 0 W whenever the service brake is applied, and the PI integrator holds (truth `arbitration/traction-cut-under-braking`). Before: up to 120 kW against the brake. |
| Stopping on a zero target | A target of 0 brakes the train to a stand instead of leaving it creeping inside the service band. |
| Service band | 0.05 m/s. Ivan's 0.5 m/s left slow-downs about 1.1 mph over target, since nothing slows the train once the brake lets go; 35 → 30 mph now settles at 30.08 mph (480 kW, 0.1 s step), with no brake chatter. |
| Authority | A count of blocks remaining, used as given (M16): it changes only when a new count arrives, and the control law stops the train when it reaches 0. Nothing counts blocks: integrated, the Track Model sends the next block's count after the Train Model reports a block change to it; on the bench, the **Block change** button sends one fewer. The 100 m countdown is gone (2026-10-21). |
| Failure detection | The Train Model no longer reports failures (truth), so the controller infers them from what it sends back (`detect_failures()`, REQ-FUNC-038): brake — service brake commanded (e-brake off) and the next tick's service brake state still off (before 2026-10-21: off for 0.5 s); engine — power that should pull ≥ 0.1 m/s² leaves the speed flat for 2 s; signal pickup — speed and authority drop to 0 together from ≥ 2 blocks. The bench's failure rows inject into the bench's simulation (Murphy) and the controller has to find them. Rules are the team's own design (`REQUIREMENTS.md` §4). |
| Any detected failure | Emergency brake applied and latched, power 0, target 0; the driver's target refused. Manual/Automatic switching is allowed (refused until 2026-10-21), so the driver can try the train. Latched until the failure is cleared on the test bench. The e-brake latches once, on detection: at a stand the driver may release it in Manual with the failure still latched, and it is not engaged again (M2, M3, 2026-10-21); in Automatic it waits for the failure to clear. |
| Engine failure | Traction is zero in the bench simulation; detected as above. |
| Signal pickup failure | The bench simulation sends zeros for commanded speed and authority, as the Train Model does; once detected they are treated as 0 until the bench clears it. The signal lights are unaffected. Once detected, the console shows "--" for commanded speed and "Stop in" (hero tiles and numbers drawer) rather than a 0 that reads like a real command. |
| Brake failure | Only the service brake fails (truth `modules/train-model.md`); the emergency brake still works. Once detected, the controller applies the emergency brake; the service brake is still commanded when asked for and its button stays live, so the driver can try it (M4, 2026-10-21; before, the request was dropped and the button greyed). Detected 0.2 s after the press on the bench (one tick to command it, one for the answer; before: 0.6 s), in Manual and Automatic. In the bench simulation, rolling resistance (C_rr 0.002) acts under an injected brake failure only; the controller models none (M19). |
| Emergency brake release | Only by the driver, only at a stand; with a detected failure latched, only in Manual (before 2026-10-21: never). A Train Model report of "off" never releases it (D011). A passenger pull is an emergency brake state that turns on while the controller is not commanding it, so a state still reported on after the release (the last command echoed, or a held passenger latch) does not latch it again: the driver's release overrides it (M2, 2026-10-21). |
| Reported state | Received, never made up: emergency and service brake state as two signals (M18), Door State and Light State. On the bench the simulation reports them: service false while an injected brake failure blocks it; doors and lights follow their commands on each change, with no door interlock of its own (the Train Model's is commented out, so the controller is the interlock), and a state the bench publishes stands until the next command. |
| Speed limit | Commanded speed is the only cap, in both modes (`REQUIREMENTS.md` M1): the controller cannot know the true limit. Automatic targets it; the driver's target is capped at it when set and lowered with it when it drops. No 70 km/h cap since 2026-10-21 (before: the lower of the commanded speed and 43.5 mph); the dial's 70 km/h scale is display only (M14). The separate `speed_limit` input, row and readout are gone. |
| Doors | The controller's (M6): opened only at a stand; either side, except at a station (arrived, until it departs), where only the platform side opens (2026-10-21; before, the platform side only, anywhere). Automatic opens the platform side on arriving at a station (a station beacon heard, no authority left, stopped; before 2026-10-21, at any stop after a new beacon), closes when the Track Signal resumes, and leaves only once Door State reports them closed. |
| Announcements | A command to the Train Model (M7), sent automatically in both modes (2026-10-21): "The train *id* is arriving soon" at 3 blocks of authority; "The train *id* has arrived at *station*" once a station beacon was heard and the train stands with no authority; "The train *id* is departing from *station*" once the doors report closed and the Track Signal resumes. Each held 5 s of system time. In Manual the press repeats the last of them, held the same way (2026-10-21; before, it sent the station name on a wall-clock timer). Before: Automatic sent the station name on a new beacon. |
| Lights | Automatic in both modes (M8, 2026-10-21): on with an underground beacon and at 18:00; off with a later not-underground beacon (unless night) and at 06:00 (unless underground). Only those changes act; the driver's own choice stands in between. A train spawns with nothing on, lights included, and one spawned at the yard between 18:00 and 06:00 has its lights set on (2026-10-21; before, lights started on). |
| Operators and trains | No driver before a train's gains are set (M9, 2026-10-21): selecting an uncommissioned train signs the driver out, Driver is refused, and the sign-in view says the train is waiting for its gains. Spawning a train keeps the current selection. The gains hand-over signs a driver in only if the engineer is still signed in on the train just commissioned (2026-10-24; before, it signed one in unconditionally after 1.5 s). |
| Emergency brake access | The driver only, to engage or release, in either mode (M2); a passenger pull still latches it. |
| Time | A fixed 0.1 s step (truth D017); 10× runs 100 ticks a second instead of a longer step. The system time is an input (M11, 2026-10-21): `step_all` takes it each tick, in seconds since midnight as `utils/system_clock.py` counts it, from the harness clock or the bench's own (from 05:00:00, simulated time). The console's clock shows the time the controller received. Pause on the bench holds every train and the bench clock. The bench clock starts at the first commissioning and then always runs, whichever train is selected (2026-10-21; before, only while the selected train was commissioned). |
| Fleet input | `step_all(dt, inputs_by_id, time_s)` refuses a tick whose set is missing any signal sent every tick, so a stale brake state cannot read as a brake failure; any `dt` other than the fixed 0.1 s step; and a `time_s` that is not a finite time of at least 0. |
| Outputs to the Train Model | `ControllerCore.commands()` returns `TrainModelCommands` in SI, one field per truth signal (power, service/emergency brake, door bool[2], light bool[2] interior/exterior, temperature setpoint °C, announcement), plus this module's `power_verified` (M21, 2026-10-24); `commands_changed` emits on change for the central harness (D005). |
| Vital power command | Calculated three times a tick from the same inputs (`vital.py`) and used only if at least two results agree (M21, 2026-10-24). With no two equal, a vitality breach: 0 W, the emergency brake latched, `power_verified` false, and a "Vitality breach" pill until a tick agrees; the driver may release the brake only after that. Speed curves and every power command are unchanged (43 mph: 42.89 at 42.3 s; 60 mph: 60.11 at 120 s). |
| Train Model interface | One way in, `read_inputs` through `step_all`: SI in truth shapes (signed actual speed, `emergency_brake_state` and `service_brake_state`, `door_state` / `light_state` bool[2], beacon station + side + underground); `failure_status` is gone (truth withdrew it). The whole set is checked before any of it is applied. The console's `apply_inputs` slot, a second way in, is gone (2026-10-21). |
| Bench and controller | Separate (M0, 2026-10-21). `ControllerCore` holds only what it receives and sends: the toy plant, Murphy's injected failures and the plant's command edges moved to `train_ctrl/bench_sim.py` (`SimTrain`, no Qt). Standalone, the console steps the fleet the way the harness does: each train's signals from its `SimTrain`, one `step_all` with the bench clock, the commands back into the simulation. Speed curves are unchanged (0 → 43 mph reaches 42.9 mph at 42.3 s, and 11.18 / 22.37 / 33.55 mph at 10 / 20 / 30 s, before and after). |
| Bench interface | `apply_bench_inputs` converts the bench's mph / °F once, checks the set with `read_inputs`, and edits the bench's simulation; the controller gets it on the next tick, as it would a harness signal. A set it cannot read is refused whole and shown as a "Not sent" callout on the bench; so is any edit to a train a harness drives. Clearing an injected failure still clears it in the controller too, until the controller detects resolution itself (`OPEN_ISSUES.md` #23). Gains are commissioned only from the engineer's pop-up. The bench cannot set the service brake state. |
| Units on screen | Imperial throughout, conversion factors from truth `conventions/units.md`; acceleration in the numbers drawer is m/s², a debugging exception (M12). |
| Code conventions | snake_case verb slots, unit-suffixed constants, no magic numbers, docstrings, `TrainControllerError` / `InvalidInputError`, flake8 79/72 with pep8-naming clean (the whole folder since 2026-10-24). |

### Console UI (`ui_parts/`)

- Header names the train and shows Automatic / Manual only; an E-BRAKE badge
  for the emergency brake and one pill per reported failure, and a
  "Vitality breach" pill during a breach (M21, 2026-10-24).
- The numbers drawer's Motion card shows the three power calculations and
  the vote (2026-10-24). The drawer is to be removed in the final
  iteration (`OPEN_ISSUES.md`, Notes).
- Searchable **train picker** (`components/TrainPicker.qml`) on the console and
  the bench: type a number, ID or line; All / Green / Red chips; ↑ ↓ Enter
  Esc; "N of M trains". The roster refreshes only when a train is added or
  removed.
- **Failure banners removed** — failures show in the header pills, the Stop
  panel badge ("Brakes failed" / "Emergency" / "Braking"), the numbers drawer
  and the hint under the speed dial.
- **Traffic light**: Ivan's sizing; colours from style-guide tokens
  (`danger` / `warning` / `success`). Shows the real aspect during a signal
  pickup failure.
- **Sizes are Ivan's**: the four top readouts at 72 px (`size_hero`, a pending
  token), dial figures scaled to the dial, 52 px door/light tiles with small
  labels, emergency-brake text at 18 px (never changed).
- The temperature dial is keyboard-reachable (arrow keys, focus ring); the
  speed dial is not, by decision (M14). The speed dial keeps a fixed 70 km/h
  scale; a press in its bottom gap reads 0, and a drag past either end holds
  that end instead of wrapping.
  The gains dialog keeps keyboard focus inside it.
- Door tiles read "Open left" / "Close left" (and right), greyed when the
  driver cannot use them ("stop first" text removed 2026-10-21); the header
  shows a Paused pill.
- The train picker works while signed out, so a driver signed out by an
  uncommissioned train can pick their way back (2026-10-21).
- Light and door tiles always act when pressed: a state the bench
  published no longer locks them (2026-10-21).
- Nothing is cut off (2026-10-21): the announcement button wraps to two
  lines and reads "Sending automatically" in Automatic; the Stop panel's
  badge reads "Brake fault", leaving its title room.
- Style-guide fixes: signal-head, scrim and readout colours on tokens; bench bar
  on `radius_lg`. The service brake stays amber (`brake_service`, a pending
  token) by decision.
- Lights are named interior / exterior (truth).

### Test bench

- **Remove train**: red at all times, next to the train picker; the first press
  arms it ("Remove T-114" / Cancel).
- Bench bar in three groups: train (picker, remove) | spawn (number, line,
  stops at, spawn) | status line (train count · last note) and 1× / 10×.
- "Send to controller" sends only the rows edited, not the whole draft.
- The cab column is gone (2026-10-16): the cab is driven from the console
  only. The bench holds Train Model rows on the left, injected failures and
  the signal aspect on the right. Pause holds the whole simulation.
- Train Model rows follow truth shapes: beacon as three fields, failures in
  engine / pickup / brake order, interior / exterior lights, emergency-brake
  report only (no service-brake row). The emergency row is
  `emergency_brake_state` (was `brake_state_emergency`, 2026-10-21) and
  acts as a passenger pull.
- **Block change** button in the Inputs header (2026-10-21): sends the next
  block's authority, one fewer, as the Track Model does.
- **`at_station`** row (2026-10-21): at a station the beacon rows are heard
  every tick; otherwise once, when one of them is sent.
- Spawning a train no longer switches the bench or the console to it.
- `at_station` sits under `authority_blocks`; **Set time** beside the
  bench clock sets it to a time of day, picked on three wheels (hours
  0–23, minutes and seconds 0–59) dragged or scrolled (2026-10-21). The status line and
  the announcement output wrap instead of being cut off.
- Outputs panel adds the Announcement row; values at 18 px.

### Self-check (`check.py`)

New or changed checks cover: the traction cut, failure responses and the
release rule, removing a train, the door interlock and repeat presses, the SI
interface and bench conversion, bad input leaving nothing applied, the bench
sending only edited rows, the roster signalling only on change, and the train
picker's search. The 10× check waits on the speed gain instead of a 300 ms
stopwatch (it failed 4 of 4 runs on Windows before).

2026-10-21, in the order made:

- The check drives the controller only through the bench simulation or
  `step_all`, never by writing its state. New checks: stepping the
  controller moves nothing it receives (M0); a held emergency report does
  not undo the driver's release, a new turn on does latch (M2); a tick
  missing either brake state is refused (M18); the harness's time reaches
  the controller and a bad time is refused (M11); a bench block change
  spends one block and the controller receives it (M16). Each fails on the
  previous commit. Two waits that timed out unchecked (the 35 mph climb
  before the slow-down test, which then sped up to 30 mph instead of
  slowing to it, and the dial-scale test) now send and tick first, and the
  climb is an `expect`.
- New checks for a light tile answering after a bench light edit,
  underground lights from the bench, the beacon heard only at a station or
  once after a send, the three automatic announcements in each mode,
  automatic lights through 18:00 and 06:00, spawning keeping the
  selection, and no driver for an uncommissioned train. Each fails on
  `3dfdf09`.
- Every checkpoint scans both windows for text cut off (elided, or past
  the window edge) and fails on any; it found seven on `5b99075`. New
  checks for the bench time setter, including noon then 18:00 turning the
  lights on.
- The mode switches both ways during each failure; the time wheels run
  24 / 60 / 60, a scroll notch steps one, a drag moves them, and the time
  they show reaches the controller.

2026-10-24: the vote's truth table; one faulty power channel outvoted with
no change to the run; two giving a breach (0 W, the e-brake, unverified),
the release refused during it and allowed after; the pill on both headers
and the drawer rows on screen, not cut off; the gains hand-over signing
nobody in after a sign-out or a pick of an uncommissioned train. The new
checks step the controller tick by tick. Each fails on the commit before.
`check.py` is a development self-check only: the integration does not
run or ship it.

### Repository

- `Train-Ctrl_HW/.gitignore`: `__pycache__/`, `.venv/`, `venv/`; the committed
  `__pycache__/check.cpython-314.pyc` was untracked.
- Venv at `Train-Ctrl_HW/.venv` (PySide6 6.11.2, PyInstaller 6.22.2), per truth
  `conventions/toolchain.md`. Not committed.
- The console no longer needs `check.py` on the import path (2026-10-24).
- `OPEN_ISSUES.md` and this file added; `REQUIREMENTS.md` and
  `HARNESS_INTEGRATION.md` (how the central harness drives the fleet)
  added 2026-10-16.
- Truth proposals in `truth/_inbox/Train-Ctrl_HW/`: one left, the 72 px
  hero size token (which also carries the service-brake colour token). The
  three authority proposals were settled by truth D013 and withdrawn with
  the separate brake-service one (2026-10-15).

---

## 2. Commit history

| Commit | Date | What |
|---|---|---|
| `4bdb3b7` | 10-06 | Truth compliance pass: traction cut, authority countdown removed, `TrainModelCommands` outputs, ft/s², style-guide token fixes, dial keyboard access, conventions, `--check` 10× fix. |
| `8283671` | 10-06 | Truth proposals: authority as blocks remaining (conflict ×3), service-brake token. |
| `98eccfd` | 10-06 | Failure modes (first version), remove train, brake/door/light reported state, SI interface + bench conversion, interior/exterior lights, 3-field beacon, dead slots removed, target-0 stop. |
| `278c158` | 10-06 | Rolling resistance everywhere, service band 0.1 m/s. **Reverted in `c06ba6c`.** |
| `caba05d` | 10-06 | Searchable train picker (console and bench). |
| `3fa0d16` | 10-06 | Module `.gitignore` covers the venv. |
| `c06ba6c` | 10-07 | Revert of `278c158` (by request). |
| `48c403d` | 10-07 | Traffic light resize beside the pickup notice. **Undone in `a69495c`.** |
| `7611dc9` | 10-07 | Review fixes: bench sends only edits, inputs validated first, door/light repeat presses, roster signal, (head sizing — later undone). `OPEN_ISSUES.md` added. |
| `a69495c` | 10-07 | Failure responses reworked (e-brake on engine/pickup, resistance only on brake failure); failure banners removed; Ivan's traffic-light sizing; pickup no longer hides the aspect; bench bar regrouped, Remove always red. |
| `2fa4b6d` | 10-07 | Bench service-brake input removed; Ivan's sizes restored (72 px readouts, dial figures, tiles, output rows). |
| `700d83d` | 10-07 | Truth proposal: `--size-hero` token. |
| `ee22c30` | 10-07 | Brakes locked out during a brake failure in both modes (**replaced** by the next row); service band 0.05 m/s; slow-down check added. |
| `55d66c3` | 10-08 | Authority countdown back in the toy plant as a stand-in for the Track Model: one block per 100 m, part-blocks carried. `check.py` gives the drives 200 blocks and checks 2.5 blocks of travel spends 2. Open issue 11 (block lengths unknown; overrun above 34.6 mph). |
| `962f823` | 10-15 | 480 kW; failures detected from returned signals, injected from the bench; brake failure = service brake only, e-brake applied; the bench clears failures; requirements gaps documented. |
| `3ffb11b` | 10-15 | Audit before push: 61 behaviour checks (no false detections in normal running at 1× and 10×, Manual and Automatic; each failure detected, latched, stopped, cleared from the bench; multi-train isolation). Engine failure at a steady cruise found undetectable on the toy plant (no resistance), documented with a check; how a failure clears once integrated logged as undecided (`OPEN_ISSUES.md` items 12–14). |
| `76e0926` | 10-15 | Signal pickup failure shows "--" for commanded speed and authority on the console (hero tiles and numbers drawer) instead of a 0 that reads like a real command; the controller still acts on 0. |
| `8ca396f` | 10-16 | Operator bar no longer shifts when the gains are set: the Gains badge sits in a slot as wide as "Gains missing", so its narrower "Gains set" label no longer hands 15 px to the toggles. Checked by comparing the bar's geometry before and after commissioning. |
| `37ec328` | 10-16 | Instance spawner: `TrainControllerFleet`, one controller per train ID, stepped together by `step_all`. Reverted on `Train-Ctrl_HW` (`515cc24`); kept in Ivan's split as `train_ctrl/fleet.py`. |
| `1bc21d1`, `d444312`, `b9e3f6a` | 10-16 | Ivan: `main.py` split into the `train_ctrl/` package; `harness_sim.py`, a stand-in central harness (55 mph, 20 blocks, 75 °F; trains no longer armed on spawn). |
| `4688cb4`, `d8b88ae` | 10-16 | Requirements review (`REQUIREMENTS.md`): commanded speed is the limit; e-brake for the driver only; dial on a fixed 70 km/h scale, gap press reads 0, drags past an end hold it, no dial keys; door logic and Automatic station stop in the controller; Automatic announcement command; 0.1 s step, 10× by tick rate, 05:00 clock; Pause holds the simulation; full input set per fleet tick; bench errors shown; bench cab column removed. Each rule has a check shown failing on the old code. |
| `5a62ca7` | 10-21 | Authority used as given: the 100 m countdown removed, bench Block change button. `REQUIREMENTS.md` rules M0–M20 from the 2026-10-21 review, each marked with whether the code has it; `OPEN_ISSUES.md` #11, #14, #17, #22 resolved, #23–#30 added. |
| `3dfdf09` | 10-21 | Bench simulation moved out of the controller (`bench_sim.py`); the bench steps the fleet like the harness; `apply_inputs` removed. Brake State split into two inputs. System time as a `step_all` input; the console shows it. A passenger pull is a turn on, so the driver's release overrides a held report. `harness_sim.py`, `HARNESS_INTEGRATION.md` and this file updated. |
| `5b99075` | 10-21 | Light tiles answer every press (fixes a lock after a bench light edit); door tiles back to Open/Close; automatic lights; automatic announcements in both modes and the bench `at_station` row; spawning keeps the selection; no driver before a train's gains. |
| `a6366c8` | 10-21 | No text cut off (scan in the self-check; seven fixed); "Sending automatically"; bench announcement wraps; `at_station` under `authority_blocks`; bench Set time. |
| `d8bd163` | 10-21 | Mode switching allowed during a failure; the bench's time on drag-and-scroll wheels. |
| `95e8fe6`, `7820732` | 10-21 | `REQUIREMENTS.md` checked against the code (R28) and the review's decisions recorded (R29); `OPEN_ISSUES.md` to match. |
| `0d0938a`, `33db86d` | 10-21 | M1: no 70 km/h cap; the Manual target follows a lowered commanded speed (R30), and the rule says so. |
| `56b6a5d`, `80c02a7` | 10-21 | M2, M3: the e-brake can be released in Manual at a stand under a failure (R31); open issue #34 (e-brake left off in Automatic under a failure). |
| `1aab718` | 10-21 | M4: brake failure on the next tick, service brake still commanded (R32). |
| `cb71ff6` | 10-21 | M6: Manual doors either side at a stand, platform side at a station (R33). |
| `ed63229` | 10-21 | M7: the Manual press repeats the last announcement on system time (R34). |
| `289bf28`, `da532ac` | 10-21 | M8: lights set from the time of day at spawn; trains spawn with nothing on (R35, R36). |
| `235fdc1` | 10-21 | M11: the bench clock runs from the first commissioning (R37). |
| `3714edc` | 10-21 | `OPEN_ISSUES.md` #28: the engine rule measured against the Train Model's grades. |
| `cfba866` | 10-22 | Ivan: `HARNESS_INTEGRATION.md` brought up to `3714edc`. |
| `fd584ed` | 10-24 | `REQUIREMENTS.md` restructured (M5 merged into M3, status and notes split, revision log moved here as §4) and, with `OPEN_ISSUES.md`, brought up to date. |
| `6d9e571` | 10-24 | The console starts without `check.py`: it is imported, and the snapshot contract checked, only under `--check`. |
| `c3fc32f`, `c29be48` | 10-24 | M21: the power command calculated three times a tick and voted two out of three; a vitality breach sends 0 W, latches the e-brake and shows a pill until a tick agrees. `power_verified` on the commands; the numbers drawer shows the vote. |
| `bf277b1` | 10-24 | The gains hand-over signs a driver in only on the train just commissioned, with the engineer still signed in (#16, M9). |
| `7a1f581` | 10-24 | flake8 clean, no behaviour change. |

---

## 3. Superseded along the way

Kept here so a reviewer reading old commits is not misled.

- **Rolling resistance in normal running and a 0.1 m/s band** (`278c158`) —
  reverted; resistance now applies under a brake failure only.
- **Failure banners** on the Speed, Stop and Signal panels (`98eccfd`) —
  removed in `a69495c`.
- **Traffic-light resize** (`48c403d`, refined in `7611dc9`) — removed in
  `a69495c`; Ivan's sizing is back.
- **Signal pickup failure showing the aspect as UNKNOWN** (`98eccfd`) — removed
  in `a69495c`; pickup affects speed and authority only.
- **A brake failure disabling both brakes** (`a69495c`, `ee22c30`) — replaced
  on 10-15: only the service brake fails and the emergency brake stops the
  train.
- **Failure Status as a controller input** — removed on 10-15 (truth withdrew
  it); failures are now detected.
- **Failures stopping the train on the service brake** (`98eccfd`) — replaced
  in `a69495c` by the emergency brake for engine and pickup failures.
- **Authority countdown removed** (`4bdb3b7`) — a countdown was back from
  2026-10-08 to 2026-10-21, in the toy plant only and at 100 m per block;
  removed again in `5a62ca7` (authority is used as given, M16).
- **The toy plant inside `ControllerCore`** (`_plant()`, `step(plant=True)`,
  `State.injected`, `State.accel_mps2`) — moved to `bench_sim.py` on
  2026-10-21 (M0).
- **Brake State as one `brake_state` bool[2] input** — split into
  `emergency_brake_state` and `service_brake_state` on 2026-10-21 (M18).
- **Door tiles saying "Left: stop first"** while moving (`4688cb4`) — back
  to "Open left" / "Close left" on 2026-10-21.
- **Automatic announcing the station name on a new beacon** (R6) —
  replaced on 2026-10-21 by the arriving / arrived / departing
  announcements in both modes.
- **A new train selected on spawn**, with the driver kept signed in —
  replaced on 2026-10-21: spawning keeps the selection, and an
  uncommissioned train has no driver.
- **Style-guide sizes** (36 px readouts, 36 px dial figures, 44 px tiles,
  13 px bench outputs, from `4bdb3b7`) — reverted to Ivan's sizes in
  `2fa4b6d`.

---

## 4. Revisions R2–R37

Moved here from `REQUIREMENTS.md` §5 on 2026-10-24, which refers to
them by number.

### 2026-10-16

All done on `Train_Ctrl_integration` from `d444312`. Each rule change has
a `check.py` check, shown failing with the old rule and passing with the
new one.

| R | Change | Where |
|---|---|---|
| R2 | E-brake: the driver engages and releases; greyed, with the reason, for anyone else; a passenger pull still latches it | `backend.py` `can_ebrake`, `StopPanel.qml` |
| R3 | Commanded speed is the only cap (M1); the speed limit input, bench row and drawer row removed. With it, the bench's cab column (M15) | `control.py`, `inputs.py`, `state.py`, `TestInputsPanel.qml` |
| R4 | Dial: fixed 70 km/h scale (`dial_max_mph`); a press in the bottom gap reads 0, a drag past either end holds it; keyboard arrows and focus ring removed; whole mph | `SpeedDial.qml`, `SpeedPanel.qml`, `constants.py` `MAX_SPEED_MPS` |
| R5 | Door logic in the controller (M6); door tiles say "stop first" while moving | `control.py` `_station_stop`, `command_door`; `CabinPanel.qml` |
| R6 | Automatic announcement command on a new station beacon; labels say a command is sent | `control.py` `apply_staged`; `backend.py`; `AnnouncementPanel.qml` |
| R7 | `TICK_S` 0.1 s; 10× = 10 ms ticks; clock from 05:00:00 on simulated time. Curves unchanged from the 0.05 s step (0 → 43 mph in 42.4 s; 35 → 30 mph settles at 30.08) | `constants.py`, `control.py`, `backend.py`, `harness_sim.py` |
| R8 | Bench Pause holds every train and the clock; Paused pill in both headers | `backend.py` `set_paused`; `ConsoleHeader.qml`; `TestInputsPanel.qml` |
| R9 | `step_all` refuses a tick missing any `EVERY_TICK` signal, and any `dt` other than `TICK_S` (0.1 s); `harness_sim.py` sends the full set | `inputs.py`, `fleet.py`, `harness_sim.py` |
| R10 | A refused bench set shows a "Not sent" callout instead of raising from the slot | `backend.py` `apply_bench_inputs`; `TestInputsPanel.qml` |
| R11 | `OPEN_ISSUES.md`: stale mass and SW references removed; items 16–22 added | `OPEN_ISSUES.md` |
| R12 | Settle (30.08 mph) and detection delay (0.6 s = 0.5 s rule + one tick) agree across CHANGELOG, OPEN_ISSUES and code | `CHANGELOG.md`, `OPEN_ISSUES.md`, `constants.py` |

### 2026-10-21

From `c98393e`.

| R | Change | Where |
|---|---|---|
| R13 | Authority used as given (M16): the toy plant's 100 m countdown, `BLOCK_LENGTH_M` and `block_progress_m` removed; the bench's **Block change** button sends the next count, one fewer, never below 0. The `check.py` check fails on the old plant (3 blocks became 1 over 250 m) and passes now | `control.py` `_plant`, `constants.py`, `state.py`, `backend.py` `bench_block_change`, `TestInputsPanel.qml`, `check.py` |
| R14 | Rules M0–M20 and §3–§4 rewritten from the 2026-10-21 decisions; `OPEN_ISSUES.md` updated to match | `REQUIREMENTS.md`, `OPEN_ISSUES.md` |
| R15 | Bench simulation out of the controller (M0): the toy plant, injected failures and command edges moved to `bench_sim.py` (`SimTrain`); the bench steps the fleet through `step_all` like the harness; the console's `apply_inputs` slot removed; bench edits go to the simulation, and edits to a harness's trains are refused. Speed curves unchanged before and after (0 → 43 mph reaches 42.9 mph at 42.3 s) | `bench_sim.py`, `control.py`, `state.py`, `constants.py`, `backend.py`, `check.py` |
| R16 | Brake State split into `emergency_brake_state` and `service_brake_state` (M18); bench row renamed to match. A pull is a turn on of the emergency state while not commanded, so the driver's release overrides a held report (M2): without it, the bench driving through `step_all` re-latched the brake on its own echo | `inputs.py`, `control.py` `apply_staged`, `TestInputsPanel.qml`, `harness_sim.py` |
| R17 | System time as a `step_all` input (`time_s`, M11), validated; the console's clock shows what the selected train received, under the bench or a harness | `fleet.py`, `state.py`, `backend.py`, `harness_sim.py` |

From `3dfdf09`. Each item was shown failing on `3dfdf09` first.

| R | Change | Where |
|---|---|---|
| R18 | A light or door tile press is answered by the bench's train even when the command is unchanged. A light state published on the bench (in Automatic, say) no longer locks the tiles once the driver is in Manual: a regression from R15, which had dropped the old plant's equivalent | `bench_sim.py` `answer_next`, `backend.py` |
| R19 | Door tiles read "Open left" / "Close left" (and right) again, greyed when unavailable; the "stop first" text is gone (M6) | `CabinPanel.qml` |
| R20 | Automatic lights, both modes (M8) | `control.py` `_auto_lights`, `constants.py` |
| R21 | Automatic announcements, both modes: arriving soon at 3 blocks, arrived, departing (M7). A station is armed by a beacon turning up or naming a new station, not only by a new name; Automatic opens its doors on arrival. The old Automatic announcement of the station name on a new beacon is gone. Bench `at_station` row: the beacon is heard every tick at a station, once after a beacon row is sent (M15) | `control.py` `apply_staged`, `_station_stop`; `bench_sim.py`; `backend.py`; `TestInputsPanel.qml` |
| R22 | Spawning keeps the selection; an uncommissioned train has no driver: picking it signs the driver out, Driver is refused, the sign-in view says it is waiting for its gains; the train picker works signed out (M9) | `backend.py`, `SignInView.qml`, `OperatorBar.qml` |

From `5b99075`.

| R | Change | Where |
|---|---|---|
| R23 | No text is cut off. The self-check now scans both windows at each checkpoint for text Qt elides and text drawn past the window edge, and found seven: the bench status line (95 px short), "Send station announcement" (28 px), "Sent automatically on approach" (66 px), "Stop the train" beside "BRAKE FAILURE" (2 px), and the bench's announcement row running off the screen. Fixed: the status line wraps to two lines; the announcement button wraps to two lines in a fixed two-line height; the Automatic label reads "Sending automatically"; the Stop panel's badge reads "Brake fault", as the header pill does; the bench's announcement value wraps in its column | `check.py` `scan`, `BenchBar.qml`, `AnnouncementPanel.qml`, `backend.py`, `StopPanel.qml`, `SignalEditRow.qml` `wrapValue`, `TestOutputsPanel.qml` |
| R24 | Bench `at_station` row moved to the Train Model column, under `authority_blocks` (M15) | `TestInputsPanel.qml` |
| R25 | Bench time setter beside the bench clock: HH:MM or HH:MM:SS, on the current simulated day; a time that is not one is refused with a "Not sent" note. Noon then 18:00 turns the lights on (M8, M15) | `TestWindow.qml`, `ConsoleHeader.qml` `clockTools`, `backend.py` `set_bench_time` |

From `a6366c8`.

| R | Change | Where |
|---|---|---|
| R26 | Mode switching allowed while a failure is latched (M3), both ways; the target stays refused and the emergency brake on. Shown refused on `a6366c8` | `backend.py` `set_manual`, `check.py` |
| R27 | The bench's time is set on three wheels, hours 0–23, minutes and seconds 0–59, each wrapping; drag or scroll one number per notch; Set time applies them. Replaces the HH:MM text field | `components/TimeWheels.qml`, `TestWindow.qml`, `check.py` |

From `d8bd163`. `REQUIREMENTS.md` only; no code changed.

| R | Change | Where |
|---|---|---|
| R28 | Statuses checked line by line against the code. Recorded: M1's Manual setpoint is capped only when set; M7's "arriving soon" also fires on a rise to 3; M8's first tick also takes underground in; M11 is Partial (the bench clock runs only once the selected train is commissioned, #31; presses while paused act on resume); M15's first spawn is selected; M17's speed law also brakes at a target of 0; FUNC-037.2 met by M3, not M4; the console's "--" follows a detected pickup failure | `REQUIREMENTS.md` |
| R29 | Decisions from that review: M2/M3, the driver may release the emergency brake in Manual at a stand with a failure still latched; M7, a rise to 3 announces too, and in Manual the driver may repeat any announcement once its state is met, until the next one is sent; M14, the dial keeps its 70 km/h scale as display only (#29); M8, a train spawned at the yard between 18:00 and 06:00 has its lights set to on; M11, the bench clock runs from the first commissioning on, whichever train is selected, and Pause is as built; M17, the service brake at authority 0 is a fail safe (now Met) | `REQUIREMENTS.md` |

From `0f2e2d2`, one rule at a time.

| R | Change | Where |
|---|---|---|
| R30 | M1: the 70 km/h cap removed (`speed_cap_mps` gone); the commanded speed is the only cap, and in Manual it lowers the driver's target when it drops. Commanded 60 mph now settles at 60.1 mph (was held at 43.6). Below 70 km/h the curves are unchanged (43 mph: 33.55 at 30 s, 43.1 at 60 s, before and after). The `check.py` check fails three ways on the old code | `control.py`, `constants.py`, `check.py` |
| R31 | M2, M3: a failure latches the emergency brake once, on detection; at a stand the driver may release it in Manual with the failure still latched, and it is not engaged again; in Automatic the release is still refused ("Release it in Manual: …"). The dial hint no longer says brake release waits for the failure to clear. The `check.py` check fails on the old code for each failure ("could not release … in Manual", "engaged the emergency brake again") | `control.py` `respond_to_failures`, `release_emergency`; `backend.py`; `check.py` |
| R32 | M4: a brake failure is concluded when last tick commanded the service brake (with the e-brake off) and this tick's service brake state still reads off: 0.2 s after the press on the bench (was 0.6 s, `BRAKE_DETECT_S` removed). The service brake stays commanded when asked for, failure or not, and the Stop panel's service button stays live. The `check.py` checks fail three ways on the old code | `control.py` `detect_failures`, `respond_to_failures`, `enforce_safety`; `constants.py`; `backend.py` `toggle_service_brake`; `StopPanel.qml`; `check.py` |
| R33 | M6: in Manual either side opens at a stand, only the platform side at a station (arrived, until it departs); the door tiles grey from the same rule (`may_open_left` / `may_open_right` replace `platform_*` and `at_stand` in the snapshot). The `check.py` check fails on the old code ("Open left" at a stand, platform on the right) | `control.py` `may_open`, `command_door`; `backend.py`; `CabinPanel.qml`; `check.py` |
| R34 | M7: in Manual the press repeats the last automatic announcement, held 5 s on system time like the automatic ones (was: the beacon's station name on a 5 s wall-clock timer in the console). Greyed while one plays and before any was sent; labels "Repeat last announcement", "Nothing to repeat yet". The console's `announcing` set and timer removed. On the old code the press sent "DORMONT" where the check expects the repeat | `control.py` `last_announcement`, `can_repeat`, `repeat_announcement`; `backend.py`; `AnnouncementPanel.qml`; `check.py` |
| R35 | M8: a train's first tick (its spawn at the yard) sets its lights on between 18:00 and 06:00 and off by day (before: whatever it started with, on). The `check.py` check fails at 19:00, 05:00 and 12:00 on the old code | `control.py` `_auto_lights`; `check.py` |
| R36 | M8: a train spawns with nothing on: the lights' defaults are now off, as everything else already was. The `check.py` check fails on the old defaults | `state.py`; `check.py` |
| R37 | M11: the bench clock starts at the first commissioning and then always runs, whichever train is selected (was: only while the selected train was commissioned). The `check.py` check fails on the old code with an uncommissioned train selected | `backend.py` `_step_all`; `check.py` |
