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
| M0 | **The controller knows only what it receives and what it sends.** Either the test bench drives it or the central harness does, never both at once, and the controller cannot tell which. The bench feeds it through the same input path as the harness; the bench's own simulation (the toy plant, Murphy's injected failures, the bench clock) is not part of the controller. | Met (2026-10-21): the bench's simulation is `bench_sim.py`, and the bench steps the fleet through `step_all`. One reach remains: clearing an injected failure on the bench also clears it in the controller, until M3's resolution detection is built (#23) |
| M1 | **The target is capped by the commanded speed only, in both modes.** Automatic: the target is the commanded speed. Manual: the target is the driver's dial setpoint, capped at the commanded speed: when the commanded speed drops, the setpoint drops with it; when it rises, the setpoint stays where it is and the driver reacts to the change. There is no separate speed limit and no 70 km/h cap, because the controller does not know the true limit; keeping the train under it is the wayside's, through the commanded speed. The speed limit the Train Model passes through is not used (#24). | Met (R30) |
| M2 | **Emergency brake.** The driver engages it from the cab; a passenger can also engage it through the Train Model. It latches. **Only the driver releases it**, only at a stand (< 0.1 m/s): with no failure latched, in either mode; with a failure still latched, only in Manual (M3). The driver's release overrides whatever the Train Model reports for the passenger brake. The engineer has no e-brake control. | Met in the controller (R31): only a turn on of the reported state is a pull. What the Train Model reports after the release is still open (#25) |
| M3 | **Failures are detected, and so is their resolution.** The driver can still switch between Manual and Automatic while a failure is latched, to try the train and see whether it has been resolved. A detected failure latches the emergency brake and keeps the target at 0, in either mode; once the train stands, the driver may release the emergency brake in Manual (M2), and the failure, still latched, does not engage it again. Nothing reports failures to the controller, and nothing tells it one has cleared: it infers both from the signals it gets back (§4), whether the bench or the harness is driving. The failure pills clear when the controller believes the failure is resolved; the driver then releases the emergency brake, if it is still on, and carries on. | Partial: resolution is not detected; the bench clears a failure directly (`clear_failure`, #23). The release in Manual is built (R31) |
| M4 | **Brake failure.** The service brake is commanded whenever it is asked for, failure or not, and shows as applied. When the next tick's service brake state from the Train Model still reads off, the controller concludes a brake failure, latches the emergency brake and shows the failure. | Met (R32) |
| M5 | **Clearing a failure** follows M3 in both modes. On the bench, clearing an injected failure removes it from the bench's simulation only; the controller has to see that it is resolved. There is no driver reset. | Planned (#23) |
| M6 | **Doors.** Manual: the driver may open either side whenever the train is at a full stop, except at a station (arrived, as M7 defines it, until it departs), where only the platform side the beacon gave opens. Automatic: on arriving at a station (M7: a station beacon heard, no authority left, stopped), open the platform side the beacon gave; when a non-zero Track Signal resumes, close the doors, then depart. The dwell is the Train Model's. The Train Model's door interlock is commented out, so the controller is the only one. The console's door tiles read "Open left" / "Close left" (and right), greyed whenever the driver cannot use them. | Met (R33). Automatic opens on arrival (2026-10-21; before, at any stop after a new beacon) |
| M7 | **Announcements are commands.** The controller sends an announcement command; the Train Model makes the announcement. Sent automatically, in both modes: "The train *id* is arriving soon" when the authority reaches 3 blocks (it normally comes down to 3; a rise to 3 announces too); "The train *id* has arrived at *station*" once a station beacon has been heard and the train stands (< 0.1 m/s) with no authority left; "The train *id* is departing from *station*" once, at that station, the doors report closed and the Track Signal resumes (commanded speed and authority above 0). Each is held for 5 s of system time. **In Manual the driver may send any of the three again once its state has been met**: after the automatic "arriving soon" at 3 blocks, say, again at 2 or 1. The automatic announcements are still sent in Manual; the driver's press only repeats one. Each stays available until the next announcement is sent. In Automatic the console's button reads "Sending automatically". A beacon is heard only near a station: one turning up, or naming a new station, is a station to serve. | Met (R34): one button repeats the last automatic announcement, the only one available under this rule; greyed while one plays and before any was sent |
| M8 | **Automatic lights, in both modes.** On when a beacon says underground; off when a later beacon says not underground. On at 18:00 system time and off at 06:00. Leaving underground between 18:00 and 06:00 keeps them on. The driver may switch them on or off at any time: the automatic rules act only on those transitions, and the driver's choice stands until the next one. A train spawns with nothing on (lights off, doors closed, brakes released, no announcement); one spawned at the yard between 18:00 and 06:00 has its lights set to on. | Met (R35, R36): a train's first tick is its spawn and sets the lights from the time of day. Underground is only taken in on that tick |
| M9 | **Kp/Ki** are set by the engineer only, once, at the very start, in an Engineer-only pop-up. Defaults are offered but never applied on their own; until the engineer commissions the gains the train commands 0 W. This holds for harness-dispatched trains too. **No driver before the gains:** while the selected train is uncommissioned, its console stays hidden behind the sign-in view, which says it is waiting for its gains; the Driver role is refused, and selecting such a train signs the driver out. | Met (no driver before the gains: 2026-10-21) |
| M10 | **Max power 480 kW** (truth, provisional). | Met |
| M11 | **Time follows the harness.** Integrated, all timing comes from the central harness's clock (`utils/system_clock.py`: a fixed 0.1 s tick, time of day from 05:00:00). Driven by the bench, the bench keeps its own clock the same way: it starts when the first train is commissioned and from then on always advances, whichever train is selected. 10× runs more ticks, never a longer step. Pause holds every train and the clock; presses made while paused act on the first tick after resuming. | Met (R37): `step_all` takes `time_s` each tick and the console shows it; the automatic lights and the announcement lockout run on it, the Manual repeat's too (R34) |
| M12 | **Acceleration is shown in m/s²** in the numbers drawer only: a debugging exception to `units.md`'s ft/s². The drawer will be removed. | Met |
| M13 | **The SW variant is closed.** Only this module is developed. | Met |
| M14 | **Driver speed changes are in 1 mph steps** on the dial. Keyboard arrow keys are not required. The dial's scale is fixed at the car's 70 km/h (43.5 mph), whatever is commanded, by decision: it is display only, not a cap (M1), and a commanded speed above 43.5 mph cannot be set from the dial (#29); a press in the bottom gap reads 0, and a drag past either end holds that end rather than wrapping. | Met |
| M15 | **The test bench has no cab controls.** It feeds what the Train Model and Track Model send, and Murphy's failures; the cab is driven from the console only. Its `at_station` row (in the Train Model column, under `authority_blocks`) says whether the beacon is heard: every tick while at a station, otherwise once, when a beacon row is sent. Three wheels beside its clock (hours 0–23, minutes and seconds 0–59; dragged or scrolled) and **Set time** set the bench clock to a time of day (greyed under a harness, whose clock is the time). Spawning a train from the bench does not switch the console or the bench to it (the first train spawned is selected, as nothing else is). The bench's input rows are for debugging and will be removed later. | Met |
| M16 | **Authority is used as given.** The controller never counts blocks: the count it receives is how far it may go, and it changes only when a new count arrives. Integrated, the Train Model reports a block change to the Track Model, which then sends the next block's count. On the bench, a **Block change** button stands in for that: the next count, one fewer, never below 0. | Met (2026-10-21) |
| M17 | **Authority 0 sets the target to 0**, and the service brake is applied while the train moves, as a fail safe. Stopping at the right block or station is still the rest of the system's, which lowers the commanded speed in time. | Met: `enforce_safety`. The speed law also holds the service brake at any target of 0 until the train stands, below the 0.05 m/s band too (`stopping`) |
| M18 | **Brake State arrives as two separate inputs:** emergency brake state and service brake state, each what is engaged, not what was commanded. | Met (2026-10-21): `emergency_brake_state` and `service_brake_state` |
| M19 | **The controller assumes perfect movement.** It models no rolling resistance, grade, mass or brake rate; the speed error is what absorbs every outside force, and the physics is the Train Model's (or, on the bench, the bench's simulation). | Partial: engine-failure detection still uses mass and `F = P/v` (§4) |
| M20 | **Signal light ahead comes from the Track Model**, directly, on the tick the train enters a signal block. Display only. | Partial: read as `signal_light_ahead`; not mapped from the Track Model yet (#27) |

## 2. Course requirements (SRS §3.2.4 and rubric)

| SRS | Rubric | Requirement | Status | Notes |
|---|---|---|---|---|
| FUNC-025 | 4.0 (2) | Manual: regulate to the driver's setpoint | Met | M1 |
| FUNC-026 | 4.0 | Automatic: regulate to the commanded speed | Met | M1 |
| FUNC-027 | 4.1 (2) | Set the cabin temperature setpoint | Met | 60–80 °F, driver in Manual |
| FUNC-028 | 4.2 (1) | Driver emergency brake | Met | M2; the Train Model's side of the passenger release is open (#25) |
| FUNC-029 | 4.3 (1) | Driver service brake | Met | Manual; live under a brake failure too (M4) |
| FUNC-030 | 4.4 (1) | Engineer sets Kp and Ki | Met | M9. Defaults 400,000 W per m/s and 8,000 W per m |
| FUNC-031 | 4.5 (2) | Driver increases and decreases speed | Met | M14; the dial's whole bottom gap reads 0 |
| FUNC-032 | 4.6 (2) | Use speed and authority from the track circuit | Partial | M16. Sent by the Track Controller over the track circuit and passed through the Train Model to us; wired at integration |
| FUNC-033 | 4.7 (1) | Lights on and off | Met | Driver toggles in Manual; automatic lights in both modes (M8) |
| FUNC-034 | 4.8 (1) | Doors open and close | Met | M6 |
| FUNC-035 | 4.9 (1) | Announce stations | Met | M7 |
| FUNC-036 | 4.9 | Stop correctly at each station | Partial | Stops where authority and commanded speed end, then serves the station (M6, M17); where that is depends on the wayside. Dwell is the Train Model's |
| FUNC-037.1 | 4.10 (1) | Stop when authority is exhausted | Partial | M17: target 0 and the service brake at a count of 0; stopping in time is the wayside's, through the commanded speed |
| FUNC-037.2 | 4.10 | Stop when a failure is detected | Met | M3: any detected failure latches the emergency brake and sets the target to 0 |
| FUNC-038 | — | Detect engine, signal pickup and brake failures | Partial | Detection from returned signals (M3); detecting resolution is not built (#23); engine and brake rules being revised (§4). The SRS wording "reported by the Train Model" is out of date (§6) |
| FUNC-047 | 5.8 | Passenger emergency brake | Met | A reported pull latches the controller's e-brake (M2) |
| FUNC-001 / 002 | 1.2 / 1.4 | Run at 1× and 10× | Met | Fixed 0.1 s step; 10× is 100 ticks a second (M11) |
| FUNC-003 | 1.3 | Pause | Met (bench) | Holds every train and the clock; the harness clock owns it when integrated |
| INTF-001.6 | 9.0 (5) | A GUI for the HW Train Controller | Met | |
| INTF-004 | — | Consistent error messages | Met (bench) | Shared `Callout`, "Not sent"; the console cannot produce bad input |
| INTF-007 | — | Separate hardware variation | Deferred | No hardware I/O layer yet |
| INTF-010 | — | HW and SW interfaces equivalent | Not applicable | SW closed (M13) |
| INTF-013 / DSN-005 | — | One shared simulation clock | Met | M11: the harness passes `utils/system_clock.py`'s time to `step_all`; the bench passes its own |
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
| Track Signal | commanded speed m/s; authority int blocks (D013) | Passed through. Lost pickup arrives as zeros; once a pickup failure is detected (§4) the console shows "--" |
| Beacon | station, side `L`/`R`/`LR`, underground | Only on the tick the train passes one |

Not used: the speed limit the Train Model also passes through (M1, #24).

**In, from the Track Model directly:** signal light ahead, on the tick the
train enters a signal block (`TrackModelOutputs.signal_seen`; M20).

**In, from the harness:** the tick (`dt`, fixed 0.1 s) and the system time (`time_s`, seconds since midnight of the first simulated day, as `utils/system_clock.py` counts it) (M11).

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
| Brake | The service brake was commanded, and the next tick's service brake state still reads off | The service brake state reads applied again when commanded | Detection as decided (R32); resolution not detected |
| Engine | Power is commanded above 0; no brake, service or emergency, at any time in the window; speed has fallen by more than a small threshold over the window. Never while the speed is within the control band of the commanded speed. The window is a few seconds longer than 2 s, so a slow fall on the flat is caught without trips from tick noise | Commanded power gives rising speed again | "Should pull ≥ 0.1 m/s² by `F = P/v`, speed not up 0.05 m/s in 2 s", which false-positives; resolution not detected |
| Signal pickup | Commanded speed and authority fall to 0 together from ≥ 2 blocks | A valid non-zero Track Signal resumes | Detection as decided; resolution not detected |

The engine window and threshold are not fixed yet (#28).

Known limits:
- A brake failure is only seen when the service brake is asked for.
- A cut from ≥ 2 blocks straight to 0 reads as a pickup failure.
- Brake and engine resolution cannot be seen while the emergency brake is
  on. Once the train stands, the driver may release it in Manual (M2, M3,
  R31); a repaired service brake can then be seen once M4 is built, an
  engine still cannot (#23).

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
| R15 | Bench simulation out of the controller (M0): the toy plant, injected failures and command edges moved to `bench_sim.py` (`SimTrain`); the bench steps the fleet through `step_all` like the harness; the console's `apply_inputs` slot removed; bench edits go to the simulation, and edits to a harness's trains are refused. Speed curves unchanged before and after (0 → 43 mph reaches 42.9 mph at 42.3 s) | `bench_sim.py`, `control.py`, `state.py`, `constants.py`, `backend.py`, `check.py` |
| R16 | Brake State split into `emergency_brake_state` and `service_brake_state` (M18); bench row renamed to match. A pull is a turn on of the emergency state while not commanded, so the driver's release overrides a held report (M2): without it, the bench driving through `step_all` re-latched the brake on its own echo | `inputs.py`, `control.py` `apply_staged`, `TestInputsPanel.qml`, `harness_sim.py` |
| R17 | System time as a `step_all` input (`time_s`, M11), validated; the console's clock shows what the selected train received, under the bench or a harness | `fleet.py`, `state.py`, `backend.py`, `harness_sim.py` |

### 2026-10-21 (afternoon)

From `3dfdf09`. Each item was shown failing on `3dfdf09` first.

| R | Change | Where |
|---|---|---|
| R18 | A light or door tile press is answered by the bench's train even when the command is unchanged. A light state published on the bench (in Automatic, say) no longer locks the tiles once the driver is in Manual: a regression from R15, which had dropped the old plant's equivalent | `bench_sim.py` `answer_next`, `backend.py` |
| R19 | Door tiles read "Open left" / "Close left" (and right) again, greyed when unavailable; the "stop first" text is gone (M6) | `CabinPanel.qml` |
| R20 | Automatic lights, both modes (M8) | `control.py` `_auto_lights`, `constants.py` |
| R21 | Automatic announcements, both modes: arriving soon at 3 blocks, arrived, departing (M7). A station is armed by a beacon turning up or naming a new station, not only by a new name; Automatic opens its doors on arrival. The old Automatic announcement of the station name on a new beacon is gone. Bench `at_station` row: the beacon is heard every tick at a station, once after a beacon row is sent (M15) | `control.py` `apply_staged`, `_station_stop`; `bench_sim.py`; `backend.py`; `TestInputsPanel.qml` |
| R22 | Spawning keeps the selection; an uncommissioned train has no driver: picking it signs the driver out, Driver is refused, the sign-in view says it is waiting for its gains; the train picker works signed out (M9) | `backend.py`, `SignInView.qml`, `OperatorBar.qml` |

### 2026-10-21 (late afternoon)

From `5b99075`.

| R | Change | Where |
|---|---|---|
| R23 | No text is cut off. The self-check now scans both windows at each checkpoint for text Qt elides and text drawn past the window edge, and found seven: the bench status line (95 px short), "Send station announcement" (28 px), "Sent automatically on approach" (66 px), "Stop the train" beside "BRAKE FAILURE" (2 px), and the bench's announcement row running off the screen. Fixed: the status line wraps to two lines; the announcement button wraps to two lines in a fixed two-line height; the Automatic label reads "Sending automatically"; the Stop panel's badge reads "Brake fault", as the header pill does; the bench's announcement value wraps in its column | `check.py` `scan`, `BenchBar.qml`, `AnnouncementPanel.qml`, `backend.py`, `StopPanel.qml`, `SignalEditRow.qml` `wrapValue`, `TestOutputsPanel.qml` |
| R24 | Bench `at_station` row moved to the Train Model column, under `authority_blocks` (M15) | `TestInputsPanel.qml` |
| R25 | Bench time setter beside the bench clock: HH:MM or HH:MM:SS, on the current simulated day; a time that is not one is refused with a "Not sent" note. Noon then 18:00 turns the lights on (M8, M15) | `TestWindow.qml`, `ConsoleHeader.qml` `clockTools`, `backend.py` `set_bench_time` |

### 2026-10-21 (evening)

From `a6366c8`.

| R | Change | Where |
|---|---|---|
| R26 | Mode switching allowed while a failure is latched (M3), both ways; the target stays refused and the emergency brake on. Shown refused on `a6366c8` | `backend.py` `set_manual`, `check.py` |
| R27 | The bench's time is set on three wheels, hours 0–23, minutes and seconds 0–59, each wrapping; drag or scroll one number per notch; Set time applies them. Replaces the HH:MM text field | `components/TimeWheels.qml`, `TestWindow.qml`, `check.py` |

### 2026-10-21 (night)

From `d8bd163`. `REQUIREMENTS.md` only; no code changed.

| R | Change | Where |
|---|---|---|
| R28 | Statuses checked line by line against the code. Recorded: M1's Manual setpoint is capped only when set; M7's "arriving soon" also fires on a rise to 3; M8's first tick also takes underground in; M11 is Partial (the bench clock runs only once the selected train is commissioned, #31; presses while paused act on resume); M15's first spawn is selected; M17's speed law also brakes at a target of 0; FUNC-037.2 met by M3, not M4; the console's "--" follows a detected pickup failure | `REQUIREMENTS.md` |
| R29 | Decisions from that review: M2/M3, the driver may release the emergency brake in Manual at a stand with a failure still latched; M7, a rise to 3 announces too, and in Manual the driver may repeat any announcement once its state is met, until the next one is sent; M14, the dial keeps its 70 km/h scale as display only (#29); M8, a train spawned at the yard between 18:00 and 06:00 has its lights set to on; M11, the bench clock runs from the first commissioning on, whichever train is selected, and Pause is as built; M17, the service brake at authority 0 is a fail safe (now Met) | `REQUIREMENTS.md` |

### 2026-10-21 (late night)

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

## 6. Later

**Outside this folder (separate PR):**
- SRS: reword FUNC-038 to "detect, from the signals the Train Model returns, each failure and its resolution"; change NFR-001.1 to truth's 0.1 s tick.
- Fill in the Train Controller section of `documents/test_plan.md`.
- `development`: remove the stale `TrainController/` folder; update `TRAINS_PROJECT_CONTEXT.md` (gains are an Engineer pop-up).
- `common/interfaces.py` `ISwTrainController` and `TrainState` are stale (authority in metres, failure flags reported by the Train Model).

**In this module:** the Planned and Partial rules in §1, in chunks
(`OPEN_ISSUES.md` #30).

**Deviations from truth, by decision:**
- M1 has no separate speed limit. Truth D009 and `signals/track-info.md` pass one to the controller.
- M12 shows acceleration in m/s².

**Open, found in the 2026-10-16 review:**
- The engineer hand-over still signs a driver in unasked (`OPEN_ISSUES.md` #16).
- `ui/__pycache__/*.pyc` is committed (`OPEN_ISSUES.md` #20).
- flake8 reports 30-odd issues in the split files from `1bc21d1` (unused re-exports in `__init__.py`, missing final newlines, blank-line spacing). Not fixed here.
- `check.py` is timing-sensitive under load (`OPEN_ISSUES.md` #21).
