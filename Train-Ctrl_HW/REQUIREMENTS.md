# Train-Ctrl_HW — requirements

What the HW Train Controller must do, where each rule comes from, and how
far the module meets it. Reviewed by Jonathan 2026-10-16 against the SRS
(`documents/srs-filled.md` v1.0), the course rubric (4.0–4.10), the course
deck (`Final Project vF.pdf`), truth (`origin/truth` f7c52c1) and the code
at `d444312` (branch `Train_Ctrl_integration`). Rules updated 2026-10-21
from the review that separates the controller from the test bench, checked
against `development` `de7a98f` (`TrainModel/`, `TrackModel/`,
`utils/system_clock.py`); code status is as of the commit that carries
this file.

Status: **Met** · **Partial** · **Missing** · **Planned** (decided, not
yet in the code) · **Deferred** (later, by decision) · **Not ours**
(another module's).

## 1. Module rules (decided by the team)

Rules specific to this module. Truth records none of them yet; the
module documentation is to be updated later (see §6).

| # | Rule | Code |
|---|---|---|
| M0 | **The controller knows only what it receives and what it sends.** Either the test bench drives it or the central harness does, never both at once, and the controller cannot tell which. The bench feeds it through the same input path as the harness; the bench's own simulation (the toy plant, Murphy's injected failures, the bench clock) is not part of the controller. | Planned: the toy plant and the injected-failure flags still live in `ControllerCore` (`OPEN_ISSUES.md` #26) |
| M1 | **The target is capped by the commanded speed only, in both modes.** Automatic: the target is the commanded speed. Manual: the target is the driver's dial setpoint, capped at the commanded speed. There is no separate speed limit and no 70 km/h cap, because the controller does not know the true limit; keeping the train under it is the wayside's, through the commanded speed. The speed limit the Train Model passes through is not used (#24). | Planned: the code still also caps at 70 km/h (`speed_cap_mps`) |
| M2 | **Emergency brake.** The driver engages it from the cab; a passenger can also engage it through the Train Model. It latches. **Only the driver releases it**, only at a stand (< 0.1 m/s) and with no failure latched. The driver's release overrides whatever the Train Model reports for the passenger brake. The engineer has no e-brake control. | Partial: a held passenger report re-latches the brake after the release (#25) |
| M3 | **Failures are detected, and so is their resolution.** Nothing reports failures to the controller, and nothing tells it one has cleared: it infers both from the signals it gets back (§4), whether the bench or the harness is driving. The failure pills clear when the controller believes the failure is resolved; the driver then releases the emergency brake and carries on. | Partial: resolution is not detected; the bench clears a failure directly (`clear_failure`), and resolution cannot be seen while the e-brake is on (#23) |
| M4 | **Brake failure.** The service brake is commanded whenever it is asked for, failure or not, and shows as applied. When the next tick's service brake state from the Train Model still reads off, the controller concludes a brake failure, latches the emergency brake and shows the failure. | Planned: the code waits 0.5 s, and forces the service command off once the failure is latched |
| M5 | **Clearing a failure** follows M3 in both modes. On the bench, clearing an injected failure removes it from the bench's simulation only; the controller has to see that it is resolved. There is no driver reset. | Planned (#23) |
| M6 | **Doors.** Manual: the driver may open either side whenever the train is at a full stop. Automatic: only at a station, on the platform side the beacon gave, once stopped; when a non-zero Track Signal resumes, close the doors, then depart. The dwell is the Train Model's. The Train Model's door interlock is commented out, so the controller is the only one. | Partial: Manual is still limited to the platform side |
| M7 | **Announcements are commands.** The controller sends an announcement command; the Train Model makes the announcement. Automatic sends it on the approach to a station (beacon); Manual on the driver's press. The lockout runs on system time. | Partial: the Manual press's lockout runs on a wall-clock timer in the console |
| M8 | **Automatic lights, in both modes.** On when a beacon says underground; off when a later beacon says not underground. On at 18:00 system time and off at 06:00. Leaving underground between 18:00 and 06:00 keeps them on. The driver may switch them on or off at any time: the automatic rules act only on those transitions, and the driver's choice stands until the next one. | Planned (#18) |
| M9 | **Kp/Ki** are set by the engineer only, once, at the very start, in an Engineer-only pop-up. Defaults are offered but never applied on their own; until the engineer commissions the gains the train commands 0 W. This holds for harness-dispatched trains too. | Met |
| M10 | **Max power 480 kW** (truth, provisional). | Met |
| M11 | **Time follows the harness.** Integrated, all timing comes from the central harness's clock (`utils/system_clock.py`: a fixed 0.1 s tick, time of day from 05:00:00). Driven by the bench, the bench keeps its own clock the same way. 10× runs more ticks, never a longer step. Pause stops the whole console. | Partial: the time of day is not an input yet; under a harness the console estimates its clock |
| M12 | **Acceleration is shown in m/s²** in the numbers drawer only: a debugging exception to `units.md`'s ft/s². The drawer will be removed. | Met |
| M13 | **The SW variant is closed.** Only this module is developed. | Met |
| M14 | **Driver speed changes are in 1 mph steps** on the dial. Keyboard arrow keys are not required. The dial's scale is fixed at the car's 70 km/h (43.5 mph), whatever is commanded; a press in the bottom gap reads 0, and a drag past either end holds that end rather than wrapping. | Met (see #29 against M1) |
| M15 | **The test bench has no cab controls.** It feeds what the Train Model and Track Model send, and Murphy's failures; the cab is driven from the console only. The bench's input rows are for debugging and will be removed later. | Met |
| M16 | **Authority is used as given.** The controller never counts blocks: the count it receives is how far it may go, and it changes only when a new count arrives. Integrated, the Train Model reports a block change to the Track Model, which then sends the next block's count. On the bench, a **Block change** button stands in for that: the next count, one fewer, never below 0. | Met (2026-10-21) |
| M17 | **Authority 0 sets the target to 0.** The train then stops by the normal service-brake rule (over target). There is no separate forced brake: stopping at the right block or station is the rest of the system's, which lowers the commanded speed in time. | Partial: the code also forces the service brake at 0 authority while moving |
| M18 | **Brake State arrives as two separate inputs:** emergency brake state and service brake state, each what is engaged, not what was commanded. | Planned: read as one `brake_state` bool[2] |
| M19 | **The controller assumes perfect movement.** It models no rolling resistance, grade, mass or brake rate; the speed error is what absorbs every outside force, and the physics is the Train Model's (or, on the bench, the bench's simulation). | Partial: engine-failure detection still uses mass and `F = P/v` (§4) |
| M20 | **Signal light ahead comes from the Track Model**, directly, on the tick the train enters a signal block. Display only. | Partial: read as `signal_light_ahead`; not mapped from the Track Model yet (#27) |

## 2. Course requirements (SRS §3.2.4 and rubric)

| SRS | Rubric | Requirement | Status | Notes |
|---|---|---|---|---|
| FUNC-025 | 4.0 (2) | Manual: regulate to the driver's setpoint | Met | M1 |
| FUNC-026 | 4.0 | Automatic: regulate to the commanded speed | Met | M1 |
| FUNC-027 | 4.1 (2) | Set the cabin temperature setpoint | Met | 60–80 °F, driver in Manual |
| FUNC-028 | 4.2 (1) | Driver emergency brake | Partial | M2; passenger override (#25) |
| FUNC-029 | 4.3 (1) | Driver service brake | Met | Manual; disabled under a brake failure |
| FUNC-030 | 4.4 (1) | Engineer sets Kp and Ki | Met | M9. Defaults 400,000 W per m/s and 8,000 W per m |
| FUNC-031 | 4.5 (2) | Driver increases and decreases speed | Met | M14; the dial's whole bottom gap reads 0 |
| FUNC-032 | 4.6 (2) | Use speed and authority from the track circuit | Partial | M16. Sent by the Track Controller over the track circuit and passed through the Train Model to us; wired at integration |
| FUNC-033 | 4.7 (1) | Lights on and off | Partial | Driver toggles only; automatic lights decided, not built (M8) |
| FUNC-034 | 4.8 (1) | Doors open and close | Partial | M6; Manual still limited to the platform side |
| FUNC-035 | 4.9 (1) | Announce stations | Met | M7 |
| FUNC-036 | 4.9 | Stop correctly at each station | Partial | Stops where authority and commanded speed end, then serves the station (M6, M17); where that is depends on the wayside. Dwell is the Train Model's |
| FUNC-037.1 | 4.10 (1) | Stop when authority is exhausted | Partial | M17: target 0 at a count of 0; stopping in time is the wayside's, through the commanded speed |
| FUNC-037.2 | 4.10 | Stop when a failure is detected | Met | M4 |
| FUNC-038 | — | Detect engine, signal pickup and brake failures | Partial | Detection from returned signals (M3); detecting resolution is not built (#23); engine and brake rules being revised (§4). The SRS wording "reported by the Train Model" is out of date (§6) |
| FUNC-047 | 5.8 | Passenger emergency brake | Met | A reported pull latches the controller's e-brake (M2) |
| FUNC-001 / 002 | 1.2 / 1.4 | Run at 1× and 10× | Met | Fixed 0.1 s step; 10× is 100 ticks a second (M11) |
| FUNC-003 | 1.3 | Pause | Met (bench) | Holds every train and the clock; the harness clock owns it when integrated |
| INTF-001.6 | 9.0 (5) | A GUI for the HW Train Controller | Met | |
| INTF-004 | — | Consistent error messages | Met (bench) | Shared `Callout`, "Not sent"; the console cannot produce bad input |
| INTF-007 | — | Separate hardware variation | Deferred | No hardware I/O layer yet |
| INTF-010 | — | HW and SW interfaces equivalent | Not applicable | SW closed (M13) |
| INTF-013 / DSN-005 | — | One shared simulation clock | Partial | M11: `utils/system_clock.py` exists on `development`; not an input here yet |
| INTF-015 / NFR-008 | — | CSV event log | Deferred | Not needed now |
| INTF-017 | — | Track circuit carries speed and authority to the TC | Partial | Via the Train Model; wired at integration |
| NFR-001.1 | — | Tick size | Met (truth) | Truth's 0.1 s, not the SRS's 1 ms (§6) |
| NFR-003 / 004 | — | Validate input; reject without changing state | Met | All or nothing |
| DSN-001 / 002 | — | Standalone executable | Deferred | |

Not taken up, by decision: the
deck's trapezoidal PI form (the code sums rectangles; to consider later)
and a stability analysis of Kp and Ki.

## 3. Interfaces

**In, from the Train Model** (SI; `development` `TrainModel/train_model/interface.py` `ControllerOutputs`):

| Signal | Shape | Note |
|---|---|---|
| Actual speed | m/s, signed | |
| Emergency brake state | bool | Engaged, not commanded; also true for a passenger pull (M2, M18) |
| Service brake state | bool | Engaged; the Train Model reports false while the e-brake is engaged or the brake has failed (M4, M18, #23) |
| Door State | bool[2] [left, right] | |
| Light State | bool[2] [interior, exterior] | Cabin and headlights |
| Cabin temperature | °C | |
| Track Signal | commanded speed m/s; authority int blocks (D013) | Passed through. Lost pickup arrives as zeros; the console shows "--" |
| Beacon | station, side `L`/`R`/`LR`, underground | Only on the tick the train passes one |

Not used: the speed limit the Train Model also passes through (M1, #24).

**In, from the Track Model directly:** signal light ahead, on the tick the
train enters a signal block (`TrackModelOutputs.signal_seen`; M20).

**In, from the harness:** the tick and the time of day (M11; planned).

**Out, to the Train Model, every tick:** power (W, ≥ 0), service brake,
emergency brake, doors bool[2], lights bool[2], temperature setpoint
(°C), announcement (text).

**Power** is the controller's only power calculation: velocity error
(commanded or setpoint minus actual) through Kp + Ki/s. Traction is cut to
0 while any brake is applied (truth
`arbitration/traction-cut-under-braking.md`); the Train Model does not cut
it itself.

## 4. Failure detection

Rules are this module's own design. Each one reads only what the
controller sends and receives (M0, M19).

| Failure | Detected when (decided) | Resolved when (decided) | Code today |
|---|---|---|---|
| Brake | The service brake was commanded, and the next tick's service brake state still reads off | The service brake state reads applied again when commanded | 0.5 s rule; resolution not detected |
| Engine | Power is commanded above 0; no brake, service or emergency, at any time in the window; speed has fallen by more than a small threshold over the window. Never while the speed is within the control band of the commanded speed. The window is a few seconds longer than 2 s, so a slow fall on the flat is caught without trips from tick noise | Commanded power gives rising speed again | "Should pull ≥ 0.1 m/s² by `F = P/v`, speed not up 0.05 m/s in 2 s", which false-positives; resolution not detected |
| Signal pickup | Commanded speed and authority fall to 0 together from ≥ 2 blocks | A valid non-zero Track Signal resumes | Detection as decided; resolution not detected |

The engine window and threshold are not fixed yet (#28).

Known limits:
- A brake failure is only seen when the service brake is asked for.
- A cut from ≥ 2 blocks straight to 0 reads as a pickup failure.
- Brake and engine resolution cannot be seen while the emergency brake is
  on (#23).

## 5. Revisions made

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

## 6. Later

**Outside this folder (separate PR):**
- SRS: reword FUNC-038 to "detect, from the signals the Train Model returns, each failure and its resolution"; change NFR-001.1 to truth's 0.1 s tick.
- Fill in the Train Controller section of `documents/test_plan.md`.
- `development`: remove the stale `TrainController/` folder; update `TRAINS_PROJECT_CONTEXT.md` (gains are an Engineer pop-up).
- `common/interfaces.py` `ISwTrainController` and `TrainState` are stale (authority in metres, failure flags reported by the Train Model).

**In this module:** the Planned and Partial rules in §1, in chunks,
starting with M0 (`OPEN_ISSUES.md` #26). `HARNESS_INTEGRATION.md` and
`CHANGELOG.md` still describe the 2026-10-16 interface (`brake_state`
bool[2], the authority countdown) and are updated with the code.

**Deviations from truth, by decision:**
- M1 has no separate speed limit. Truth D009 and `signals/track-info.md` pass one to the controller.
- M12 shows acceleration in m/s².

**Open, found in the 2026-10-16 review:**
- The engineer hand-over still signs a driver in unasked (`OPEN_ISSUES.md` #16).
- `ui/__pycache__/*.pyc` is committed (`OPEN_ISSUES.md` #20).
- flake8 reports 30-odd issues in the split files from `1bc21d1` (unused re-exports in `__init__.py`, missing final newlines, blank-line spacing). Not fixed here.
- `check.py` is timing-sensitive under load (`OPEN_ISSUES.md` #21).
