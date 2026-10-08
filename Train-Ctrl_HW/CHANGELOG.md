# Train-Ctrl_HW — changes for review

Everything changed in the HW Train Controller module since Ivan's last commit
(`493f16e`, "update compiled Python bytecode for check.py"), up to `700d83d`
(2026-10-07). Work by Jonathan Tsang, with Claude. Open, unfixed items are in
[`OPEN_ISSUES.md`](OPEN_ISSUES.md).

Base for every check below: `python main.py --check` (run with the module's
venv) — 0 QML warnings, 0 behaviour problems at `700d83d`.

---

## 1. Where things stand (net effect)

### Control and safety (`main.py`)

| Area | Behaviour now |
|---|---|
| Traction under braking | Power is 0 W whenever the service brake is applied, and the PI integrator holds (truth `arbitration/traction-cut-under-braking`). Before: up to 120 kW against the brake. |
| Stopping on a zero target | A target of 0 brakes the train to a stand instead of leaving it creeping inside the service band. |
| Service band | 0.5 m/s (Ivan's value; a 0.1 m/s version was reverted). Slow-downs settle about 1.1 mph over target — see OPEN_ISSUES. |
| Authority | A count of blocks remaining, as sent. The controller no longer counts blocks down itself (the fixed 500 m countdown, `enter_block()` and `current_block` are gone); it stops when the count reaches 0. |
| Engine failure | Emergency brake applied and latched, power 0, target 0. Cannot be released until the failure clears. |
| Signal pickup failure | Same as engine; commanded speed and authority are treated as 0 (the track circuit cannot be read). The signal lights are unaffected. |
| Brake failure | Both brakes disabled, power cut, no brake commanded. Rolling resistance (truth C_rr 0.002 × g 9.81 = 0.0196 m/s²) coasts the train to a stand — about 7 min from 19 mph at 1×. Resistance applies only under a brake failure, as a trial. |
| Emergency brake release | Only by the driver, only at a stand, and never while any failure is active. A Train Model report of "off" never releases it (D011). |
| Reported state | The toy plant reports Brake State `[emergency, service]` (false when brakes have failed), Door State with the door interlock (opens only at a stand), and Light State. Door and light commands are answered when pressed, including a repeat press after the interlock held a door shut. |
| Outputs to the Train Model | `ControllerCore.commands()` returns `TrainModelCommands` in SI, one field per truth signal (power, service/emergency brake, door bool[2], light bool[2] interior/exterior, temperature setpoint °C, announcement); `commands_changed` emits on change for the central harness (D005). |
| Train Model interface | `apply_inputs` takes SI in truth shapes (signed actual speed, `failure_status` bool[3] engine/pickup/brake, `brake_state` / `door_state` / `light_state` bool[2], beacon station + side + underground). The whole set is checked before any of it is applied. |
| Bench interface | `apply_bench_inputs` converts the bench's mph / °F once and calls `apply_inputs`; gains commission only after the rest applies. The bench cannot set the service-brake state. |
| Units on screen | Imperial throughout (acceleration in ft/s²); conversion factors from truth `conventions/units.md`. |
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
- Dials are keyboard-reachable (arrow keys, focus ring); the gains dialog keeps
  keyboard focus inside it.
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
- Train Model rows follow truth shapes: beacon as three fields, failures in
  engine / pickup / brake order, interior / exterior lights, emergency-brake
  report only (no service-brake row).
- Outputs panel adds the Announcement row; values at 18 px.

### Self-check (`check.py`)

New or changed checks cover: the traction cut, failure responses and the
release rule, removing a train, the door interlock and repeat presses, the SI
interface and bench conversion, bad input leaving nothing applied, the bench
sending only edited rows, the roster signalling only on change, and the train
picker's search. The 10× check waits on the speed gain instead of a 300 ms
stopwatch (it failed 4 of 4 runs on Windows before).

### Repository

- `Train-Ctrl_HW/.gitignore`: `__pycache__/`, `.venv/`, `venv/`; the committed
  `__pycache__/check.cpython-314.pyc` was untracked.
- Venv at `Train-Ctrl_HW/.venv` (PySide6 6.11.2, PyInstaller 6.22.2), per truth
  `conventions/toolchain.md`. Not committed.
- `OPEN_ISSUES.md` and this file added.
- Truth proposals in `truth/_inbox/Train-Ctrl_HW/` (5 files: authority as a
  block count, as conflicts, in units / identifiers / track-signal; the
  service-brake colour token; the 72 px hero size token). Not promoted.

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
- **Failures stopping the train on the service brake** (`98eccfd`) — replaced
  in `a69495c` by the emergency brake for engine and pickup failures.
- **Style-guide sizes** (36 px readouts, 36 px dial figures, 44 px tiles,
  13 px bench outputs, from `4bdb3b7`) — reverted to Ivan's sizes in
  `2fa4b6d`.
