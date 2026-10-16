# Train-Ctrl_HW — requirements

What the HW Train Controller must do, where each rule comes from, and how
far the module meets it. Reviewed by Jonathan 2026-10-16 against the SRS
(`documents/srs-filled.md` v1.0), the course rubric (4.0–4.10), the course
deck (`Final Project vF.pdf`), truth (`origin/truth` f7c52c1) and the code
at `d444312` (branch `Train_Ctrl_integration`).

Status: **Met** · **Partial** · **Missing** · **Planned** (an R item
below) · **Deferred** (later, by decision) · **Not ours** (another
module's).

## 1. Module rules (decided by the team)

Rules specific to this module. Truth records none of them yet; the
module documentation is to be updated later (see §6).

| # | Rule |
|---|---|
| M1 | **Commanded speed is the speed limit.** There is no separate speed limit. Automatic: the target is the commanded speed. Manual: the driver's target is capped at the commanded speed when set, then follows the driver exactly. |
| M2 | **Emergency brake.** The driver engages it from the cab; a passenger can also engage it through the Train Model. It latches. **Only the driver releases it**, only at a stand (< 0.1 m/s) and with no failure latched. A Train Model report of "off" never releases it. The engineer has no e-brake control. |
| M3 | **Failures are detected, not reported.** The Train Model no longer sends failure status; the controller infers engine, brake and signal pickup failures from the signals it gets back (§4). |
| M4 | **A brake failure disables the service brake only.** On detection the controller applies and latches the emergency brake. |
| M5 | **Clearing a failure:** when the test UI drives the system, the bench clears it, and there is no driver reset. Once integrated this is undecided (`OPEN_ISSUES.md` #14). |
| M6 | **Doors are the controller's.** Door-open commands go out only when the Train Model reports speed 0. Automatic: at a station (beacon), once stopped, open the platform side; when a non-zero Track Signal resumes, close the doors, then depart. The dwell is the Train Model's. |
| M7 | **Announcements are commands.** The controller sends an announcement command; the Train Model makes the announcement. Automatic sends it on the approach to a station (beacon); Manual on the driver's press. |
| M8 | **Lights in Automatic:** on in a tunnel (beacon underground) and at dusk. Nothing tells the train when it is dark yet, so this is documented for later. |
| M9 | **Kp/Ki** are set in an Engineer-only pop-up, not in the driver's cab. |
| M10 | **Max power 480 kW** (truth, provisional). |
| M11 | **Time follows truth:** a fixed 0.1 s step; 10× ticks faster, never a longer step. Pause stops the whole console. For now the clock lives in the test UI; later all modules share one. |
| M12 | **Acceleration is shown in m/s²** in the numbers drawer only: a debugging exception to `units.md`'s ft/s². The drawer will be removed. |
| M13 | **The SW variant is closed.** Only this module is developed. |
| M14 | **Driver speed changes are in 1 mph steps** on the dial. Keyboard arrow keys are not required. The dial's scale is fixed at the car's 70 km/h (43.5 mph), whatever is commanded; a press in the bottom gap reads 0, and a drag past either end holds that end rather than wrapping. |
| M15 | **The test bench has no cab controls.** It feeds what the Train Model and Track Model send, and Murphy's failures; the cab is driven from the console only. |

## 2. Course requirements (SRS §3.2.4 and rubric)

| SRS | Rubric | Requirement | Status | Notes |
|---|---|---|---|---|
| FUNC-025 | 4.0 (2) | Manual: regulate to the driver's setpoint | Met | M1 |
| FUNC-026 | 4.0 | Automatic: regulate to the commanded speed | Met | M1 |
| FUNC-027 | 4.1 (2) | Set the cabin temperature setpoint | Met | 60–80 °F, driver in Manual |
| FUNC-028 | 4.2 (1) | Driver emergency brake | Met | M2 |
| FUNC-029 | 4.3 (1) | Driver service brake | Met | Manual; disabled under a brake failure |
| FUNC-030 | 4.4 (1) | Engineer sets Kp and Ki | Met | Defaults 400,000 W per m/s and 8,000 W per m |
| FUNC-031 | 4.5 (2) | Driver increases and decreases speed | Met | M14; the dial's whole bottom gap reads 0 |
| FUNC-032 | 4.6 (2) | Use speed and authority from the track circuit | Partial | Sent by the Track Controller over the track circuit and passed through the Train Model to us; wired at integration |
| FUNC-033 | 4.7 (1) | Lights on and off | Partial | Driver toggles only; automatic lights deferred (M8) |
| FUNC-034 | 4.8 (1) | Doors open and close | Met | M6 |
| FUNC-035 | 4.9 (1) | Announce stations | Met | M7 |
| FUNC-036 | 4.9 | Stop correctly at each station | Partial | Stops where authority and commanded speed end, then serves the station (M6); where that is depends on the wayside. Dwell is the Train Model's |
| FUNC-037.1 | 4.10 (1) | Stop when authority is exhausted | Partial | Brakes at a count of 0 only; overruns above 34.6 mph with 100 m blocks (`OPEN_ISSUES.md` #11). Left open. |
| FUNC-037.2 | 4.10 | Stop when a failure is detected | Met | M4 |
| FUNC-038 | — | Detect engine, signal pickup and brake failures | Met | From returned signals (M3). The SRS wording "reported by the Train Model" is out of date (§6). |
| FUNC-047 | 5.8 | Passenger emergency brake | Met | A reported pull latches the controller's e-brake (M2) |
| FUNC-001 / 002 | 1.2 / 1.4 | Run at 1× and 10× | Met | Fixed 0.1 s step; 10× is 100 ticks a second (M11) |
| FUNC-003 | 1.3 | Pause | Met (bench) | Holds every train and the clock; the shared clock will own it later |
| INTF-001.6 | 9.0 (5) | A GUI for the HW Train Controller | Met | |
| INTF-004 | — | Consistent error messages | Met (bench) | Shared `Callout`, "Not sent"; the console cannot produce bad input |
| INTF-007 | — | Separate hardware variation | Deferred | No hardware I/O layer yet |
| INTF-010 | — | HW and SW interfaces equivalent | Not applicable | SW closed (M13) |
| INTF-013 / DSN-005 | — | One shared simulation clock | Deferred | M11 |
| INTF-015 / NFR-008 | — | CSV event log | Deferred | Not needed now |
| INTF-017 | — | Track circuit carries speed and authority to the TC | Partial | Via the Train Model; wired at integration |
| NFR-001.1 | — | Tick size | Met (truth) | Truth's 0.1 s, not the SRS's 1 ms (§6) |
| NFR-003 / 004 | — | Validate input; reject without changing state | Met | All or nothing |
| DSN-001 / 002 | — | Standalone executable | Deferred | |

Not taken up, by decision: the 70 km/h car maximum (not needed), the
deck's trapezoidal PI form (the code sums rectangles; to consider later)
and a stability analysis of Kp and Ki.

## 3. Interfaces

**In, from the Train Model** (SI; truth signal entries):

| Signal | Shape | Note |
|---|---|---|
| Actual speed | m/s, signed | |
| Brake State | bool[2] [emergency, service] | Engaged, not commanded; emergency is also true for a passenger pull |
| Door State | bool[2] [left, right] | |
| Light State | bool[2] [interior, exterior] | |
| Cabin temperature | °C | |
| Track Signal | commanded speed m/s (also the speed limit, M1); authority int blocks ahead (D013) | Lost pickup arrives as zeros; the console shows "--" |
| Beacon | station, side `L`/`R`/`LR`, underground | |

**Out, to the Train Model, every tick:** power (W, ≥ 0), service brake,
emergency brake, doors bool[2], lights bool[2], temperature setpoint
(°C), announcement (text).

Traction is cut to 0 while any brake is applied (truth
`arbitration/traction-cut-under-braking.md`).

## 4. Failure detection

Rules are this module's own design (`control.py` `detect_failures`):

| Failure | Detected when | Constant |
|---|---|---|
| Brake | Service brake commanded, e-brake off, Brake State never shows the service brake | 0.5 s |
| Engine | Power that should pull ≥ 0.1 m/s², no brake on, speed not up 0.05 m/s | 2 s |
| Signal pickup | Commanded speed and authority fall to 0 together from ≥ 2 blocks | — |

Known limits:
- A brake failure is only seen when the service brake is asked for.
- An engine failure at a steady cruise is not seen on the toy plant (no resistance).
- A steep up-grade could trip engine detection.
- A cut from ≥ 2 blocks straight to 0 reads as a pickup failure.

## 5. Revisions made (2026-10-16)

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
| R9 | `step_all` refuses a tick missing any `EVERY_TICK` signal; `harness_sim.py` sends the full set | `inputs.py`, `fleet.py`, `harness_sim.py` |
| R10 | A refused bench set shows a "Not sent" callout instead of raising from the slot | `backend.py` `apply_bench_inputs`; `TestInputsPanel.qml` |
| R11 | `OPEN_ISSUES.md`: stale mass and SW references removed; items 16–22 added | `OPEN_ISSUES.md` |
| R12 | Settle (30.08 mph) and detection delay (0.6 s = 0.5 s rule + one tick) agree across CHANGELOG, OPEN_ISSUES and code | `CHANGELOG.md`, `OPEN_ISSUES.md`, `constants.py` |

## 6. Later

**Outside this folder (separate PR):**
- SRS: reword FUNC-038 to "detect from the signals the Train Model returns"; change NFR-001.1 to truth's 0.1 s tick.
- Fill in the Train Controller section of `documents/test_plan.md`.
- `development`: remove the stale `TrainController/` folder; update `TRAINS_PROJECT_CONTEXT.md` (gains are an Engineer pop-up).

**In this module:**
- Record M1–M14 in the module documentation and truth's Train Controller contract, which is still a placeholder.
- Automatic lights at dusk need a darkness source (M8).
- How a failure clears once integrated (`OPEN_ISSUES.md` #14).
- Harness wiring, the shared clock and dispatch, at integration.

**Deviations from truth, by decision:**
- M1 has no separate speed limit. Truth D009 and `signals/track-info.md` pass one to the controller.
- M12 shows acceleration in m/s².

**Open, found in this review:**
- The engineer hand-over still signs a driver in unasked (`backend.py:618-621`). Signing out within 1.5 s of commissioning still ends with a driver signed in. It was dropped from `OPEN_ISSUES.md` but not fixed.
- `OPEN_ISSUES.md` #11 says a block-change dummy exists; none was found in `train_ctrl/`.
- `old_main.py` is an unused copy of the pre-split `main.py`.
- `ui/__pycache__/*.pyc` is committed again (`d444312`).
- flake8 reports 30-odd issues in the split files from `1bc21d1` (unused re-exports in `__init__.py`, missing final newlines, blank-line spacing). Not fixed here.
- `check.py` is timing-sensitive under load (`OPEN_ISSUES.md` #21).
