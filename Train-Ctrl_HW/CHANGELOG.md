# Train-Ctrl_HW — changes for review

Everything changed in the HW Train Controller module since Ivan's last commit
(`493f16e`, "update compiled Python bytecode for check.py"), up to the
controller / test bench separation (2026-10-21). Work by Jonathan Tsang, with Claude. Open, unfixed items are in
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
| Failure detection | The Train Model no longer reports failures (truth), so the controller infers them from what it sends back (`detect_failures()`, REQ-FUNC-038): brake — service brake commanded but never shown applied for 0.5 s; engine — power that should pull ≥ 0.1 m/s² leaves the speed flat for 2 s; signal pickup — speed and authority drop to 0 together from ≥ 2 blocks. The bench's failure rows inject into the bench's simulation (Murphy) and the controller has to find them. Rules are the team's own design (`REQUIREMENTS.md` §4). |
| Any detected failure | Emergency brake applied and latched, power 0, target 0; the driver's target refused. Manual/Automatic switching is allowed (refused until 2026-10-21), so the driver can try the train. Latched until the failure is cleared on the test bench; the driver then releases the e-brake at a stand. |
| Engine failure | Traction is zero in the bench simulation; detected as above. |
| Signal pickup failure | The bench simulation sends zeros for commanded speed and authority, as the Train Model does; once detected they are treated as 0 until the bench clears it. The signal lights are unaffected. Once detected, the console shows "--" for commanded speed and "Stop in" (hero tiles and numbers drawer) rather than a 0 that reads like a real command. |
| Brake failure | Only the service brake fails (truth `modules/train-model.md`); the emergency brake still works. Once detected, the controller applies the emergency brake, the driver's service request is dropped and the service brake is never commanded; the Stop panel's service brake is greyed out, the emergency brake stays live. Detected 0.6 s after the service brake is asked for (the 0.5 s rule plus one 0.1 s tick), in Manual and Automatic. In the bench simulation, rolling resistance (C_rr 0.002) acts under an injected brake failure only; the controller models none (M19). |
| Emergency brake release | Only by the driver, only at a stand, and never while any detected failure is latched. A Train Model report of "off" never releases it (D011). A passenger pull is an emergency brake state that turns on while the controller is not commanding it, so a state still reported on after the release (the last command echoed, or a held passenger latch) does not latch it again: the driver's release overrides it (M2, 2026-10-21). |
| Reported state | Received, never made up: emergency and service brake state as two signals (M18), Door State and Light State. On the bench the simulation reports them: service false while an injected brake failure blocks it; doors and lights follow their commands on each change, with no door interlock of its own (the Train Model's is commented out, so the controller is the interlock), and a state the bench publishes stands until the next command. |
| Speed limit | Commanded speed is the limit, never above the car's 70 km/h / 43.5 mph (`REQUIREMENTS.md` M1; the Train Model has no governor, D009). Automatic targets the lower of the two; the driver's target is capped at it when set. The separate `speed_limit` input, row and readout are gone. |
| Doors | The controller's (M6): opened only at a stand, platform side only. Automatic opens the platform side on arriving at a station (a station beacon heard, no authority left, stopped; before 2026-10-21, at any stop after a new beacon), closes when the Track Signal resumes, and leaves only once Door State reports them closed. |
| Announcements | A command to the Train Model (M7), sent automatically in both modes (2026-10-21): "The train *id* is arriving soon" at 3 blocks of authority; "The train *id* has arrived at *station*" once a station beacon was heard and the train stands with no authority; "The train *id* is departing from *station*" once the doors report closed and the Track Signal resumes. Each held 5 s of system time. Manual's press sends the station name. Before: Automatic sent the station name on a new beacon. |
| Lights | Automatic in both modes (M8, 2026-10-21): on with an underground beacon and at 18:00; off with a later not-underground beacon (unless night) and at 06:00 (unless underground). Only those changes act; the driver's own choice stands in between. |
| Operators and trains | No driver before a train's gains are set (M9, 2026-10-21): selecting an uncommissioned train signs the driver out, Driver is refused, and the sign-in view says the train is waiting for its gains. Spawning a train keeps the current selection. |
| Emergency brake access | The driver only, to engage or release, in either mode (M2); a passenger pull still latches it. |
| Time | A fixed 0.1 s step (truth D017); 10× runs 100 ticks a second instead of a longer step. The system time is an input (M11, 2026-10-21): `step_all` takes it each tick, in seconds since midnight as `utils/system_clock.py` counts it, from the harness clock or the bench's own (from 05:00:00, simulated time). The console's clock shows the time the controller received. Pause on the bench holds every train and the bench clock. |
| Fleet input | `step_all(dt, inputs_by_id, time_s)` refuses a tick whose set is missing any signal sent every tick, so a stale brake state cannot read as a brake failure; any `dt` other than the fixed 0.1 s step; and a `time_s` that is not a finite time of at least 0. |
| Outputs to the Train Model | `ControllerCore.commands()` returns `TrainModelCommands` in SI, one field per truth signal (power, service/emergency brake, door bool[2], light bool[2] interior/exterior, temperature setpoint °C, announcement); `commands_changed` emits on change for the central harness (D005). |
| Train Model interface | One way in, `read_inputs` through `step_all`: SI in truth shapes (signed actual speed, `emergency_brake_state` and `service_brake_state`, `door_state` / `light_state` bool[2], beacon station + side + underground); `failure_status` is gone (truth withdrew it). The whole set is checked before any of it is applied. The console's `apply_inputs` slot, a second way in, is gone (2026-10-21). |
| Bench and controller | Separate (M0, 2026-10-21). `ControllerCore` holds only what it receives and sends: the toy plant, Murphy's injected failures and the plant's command edges moved to `train_ctrl/bench_sim.py` (`SimTrain`, no Qt). Standalone, the console steps the fleet the way the harness does: each train's signals from its `SimTrain`, one `step_all` with the bench clock, the commands back into the simulation. Speed curves are unchanged (0 → 43 mph reaches 42.9 mph at 42.3 s, and 11.18 / 22.37 / 33.55 mph at 10 / 20 / 30 s, before and after). |
| Bench interface | `apply_bench_inputs` converts the bench's mph / °F once, checks the set with `read_inputs`, and edits the bench's simulation; the controller gets it on the next tick, as it would a harness signal. A set it cannot read is refused whole and shown as a "Not sent" callout on the bench; so is any edit to a train a harness drives. Clearing an injected failure still clears it in the controller too, until the controller detects resolution itself (`OPEN_ISSUES.md` #23). Gains are commissioned only from the engineer's pop-up. The bench cannot set the service brake state. |
| Units on screen | Imperial throughout, conversion factors from truth `conventions/units.md`; acceleration in the numbers drawer is m/s², a debugging exception (M12). |
| Code conventions | snake_case verb slots, unit-suffixed constants, no magic numbers, docstrings, `TrainControllerError` / `InvalidInputError`, flake8 79/72 with pep8-naming clean. |

### Console UI (`ui_parts/`)

- Header names the train and shows Automatic / Manual only; an E-BRAKE badge
  for the emergency brake and one pill per reported failure.
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

2026-10-21 (evening): the mode switches both ways during each failure;
the time wheels run 24 / 60 / 60, a scroll notch steps one, a drag moves
them, and the time they show reaches the controller.

2026-10-21 (late afternoon): every checkpoint scans both windows for
text cut off (elided, or past the window edge) and fails on any; it found
seven on `5b99075`. New checks for the bench time setter, including noon
then 18:00 turning the lights on.

2026-10-21 (afternoon): new checks for a light tile answering after a
bench light edit, underground lights from the bench, the beacon heard
only at a station or once after a send, the three automatic announcements
in each mode, automatic lights through 18:00 and 06:00, spawning keeping
the selection, and no driver for an uncommissioned train. Each fails on
`3dfdf09`.

2026-10-21: the check drives the controller only through the bench
simulation or `step_all`, never by writing its state. New checks: stepping
the controller moves nothing it receives (M0); a held emergency report
does not undo the driver's release, a new turn on does latch (M2); a tick
missing either brake state is refused (M18); the harness's time reaches
the controller and a bad time is refused (M11); a bench block change spends
one block and the controller receives it (M16). Each fails on the previous
commit. Two waits that timed out unchecked (the 35 mph climb before the
slow-down test, which then sped up to 30 mph instead of slowing to it, and
the dial-scale test) now send and tick first, and the climb is an
`expect`.

### Repository

- `Train-Ctrl_HW/.gitignore`: `__pycache__/`, `.venv/`, `venv/`; the committed
  `__pycache__/check.cpython-314.pyc` was untracked.
- Venv at `Train-Ctrl_HW/.venv` (PySide6 6.11.2, PyInstaller 6.22.2), per truth
  `conventions/toolchain.md`. Not committed.
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
| (next) | 10-21 | Mode switching allowed during a failure; the bench's time on drag-and-scroll wheels. |

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
