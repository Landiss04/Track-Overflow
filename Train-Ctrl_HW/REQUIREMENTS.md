# Train-Ctrl_HW — requirements

What the HW Train Controller must do, where each rule comes from, and how
far the module meets it. Reviewed by Jonathan 2026-10-16 against the SRS
(`documents/srs-filled.md` v1.0), the course rubric (4.0–4.10), the course
deck (`Final Project vF.pdf`), truth (`origin/truth` f7c52c1) and the code
at `d444312` (branch `Train_Ctrl_integration`). Rules updated 2026-10-21
from the review that separates the controller from the test bench, checked
against `development` `de7a98f` (`TrainModel/`, `TrackModel/`,
`utils/system_clock.py`); code status is as of the commit that carries
this file. Restructured 2026-10-24: M5 merged into M3, status and notes
in separate columns, and the revision log moved to `CHANGELOG.md` §4.

Status: **Met** · **Partial** · **Missing** · **Planned** (decided, not
yet in the code) · **Deferred** (later, by decision) · **Not ours**
(another module's).

## 1. Module rules (decided by the team)

Rules specific to this module. Truth records none of them yet; the
module documentation is to be updated later (see §6).

| # | Rule | Status | Notes |
|---|---|---|---|
| M0 | **The controller knows only what it receives and what it sends.** Either the test bench drives it or the central harness does, never both at once, and the controller cannot tell which. The bench feeds it through the same input path as the harness; the bench's own simulation (the toy plant, Murphy's injected failures, the bench clock) is not part of the controller. | Partial | The bench's simulation is `bench_sim.py`, and the bench steps the fleet through `step_all` (2026-10-21). One reach remains: clearing an injected failure on the bench also clears it in the controller, until M3's resolution detection is built (#23) |
| M1 | **The target is capped by the commanded speed only, in both modes.** Automatic: the target is the commanded speed. Manual: the target is the driver's dial setpoint, capped at the commanded speed: when the commanded speed drops, the setpoint drops with it; when it rises, the setpoint stays where it is and the driver reacts to the change. There is no separate speed limit and no 70 km/h cap, because the controller does not know the true limit; keeping the train under it is the wayside's, through the commanded speed. The speed limit the Train Model passes through is not used (#24). | Met | R30 |
| M2 | **Emergency brake.** The driver engages it from the cab; a passenger can also engage it through the Train Model. It latches. **Only the driver releases it**, only at a stand (< 0.1 m/s): with no failure latched, in either mode; with a failure still latched, only in Manual (M3). The driver's release overrides whatever the Train Model reports for the passenger brake. The engineer has no e-brake control. | Met | In the controller (R31): only a turn on of the reported state is a pull. What the Train Model reports after the release is still open (#25) |
| M3 | **Failures are detected, and so is their resolution.** The driver can still switch between Manual and Automatic while a failure is latched, to try the train and see whether it has been resolved. A detected failure latches the emergency brake and keeps the target at 0, in either mode; once the train stands, the driver may release the emergency brake in Manual (M2), and the failure, still latched, does not engage it again. Nothing reports failures to the controller, and nothing tells it one has cleared: it infers both from the signals it gets back (§4), whether the bench or the harness is driving. The failure pills clear when the controller believes the failure is resolved; the driver then releases the emergency brake, if it is still on, and carries on. On the bench, clearing an injected failure removes it from the bench's simulation only; the controller has to see that it is resolved. There is no driver reset. | Partial | Resolution is not detected; the bench clears a failure directly (`clear_failure`, #23). The release in Manual is built (R31) |
| M4 | **Brake failure.** The service brake is commanded whenever it is asked for, failure or not, and shows as applied. When the next tick's service brake state from the Train Model still reads off, the controller concludes a brake failure, latches the emergency brake and shows the failure. | Met | R32 |
| M6 | **Doors and station boarding**, in both modes unless marked. Doors open only at a stand (< 0.1 m/s); while the train moves they stay closed, and a door still commanded open is closed. Away from a station, in Manual, the driver may open either side at a stand. **Arrival** is the beacon received (only while the train is on the station's block), authority 0, commanded speed 0 and the train at a stand: the controller opens the platform side the beacon gave. The **dwell** runs 45 s of system time (truth D007) from Door State reporting the doors open; the train is held, and the driver cannot close them; a "Station dwell" pill in the header, with the failures, starts full and empties as it runs. At its end the controller closes the doors. After the dwell, until a new Track Signal (commanded speed and authority both above 0), the driver may open and close the platform side in Manual; in Automatic the console is locked and the doors stay closed. A **new Track Signal** closes any open door and locks the doors; one that arrives during the dwell waits for it to end. Switching to Automatic with the doors open after the dwell leaves them open until the new Track Signal closes them. No traction until Door State reports both doors closed; then Automatic departs, and in Manual the driver sets a speed. The Train Model's door interlock is commented out, so the controller is the only one. The console's door tiles read "Open left" / "Close left" (and right), greyed whenever the driver cannot use them; the Cab controls badge reads "Doors free" or "Doors locked" in Manual, "Locked" in Automatic. | Met | 2026-10-24: the dwell is the controller's, as truth D007 has it (was the Train Model's), and boarding runs in Manual too. |
| M7 | **Announcements are commands.** The controller sends an announcement command; the Train Model makes the announcement. Sent automatically, in both modes: "The train *id* is arriving soon" when the authority reaches 3 blocks (it normally comes down to 3; a rise to 3 announces too), never while at a station; at a departure (from the yard, or from a station once "departing" has played) it is sent at once if the authority is 3 or fewer. "The train *id* has arrived at *station*" on arrival (M6). "The train *id* is departing from *station*" once, after the dwell, a new Track Signal has arrived and the doors report closed. Each is held for 5 s of system time; a new one replaces one still playing. **In Manual the driver may send any of the three again once its state has been met**: after the automatic "arriving soon" at 3 blocks, say, again at 2 or 1. The automatic announcements are still sent in Manual; the driver's press only repeats one. Each stays available until the next announcement is sent. In Automatic the console's button reads "Sending automatically". | Met | R34: one button repeats the last automatic announcement, the only one available under this rule; greyed while one plays and before any was sent. 2026-10-24: none at a station; at a departure, 3 blocks or fewer at once |
| M8 | **Automatic lights, in both modes.** On when a beacon says underground; off when a later beacon says not underground. On at 18:00 system time and off at 06:00. Leaving underground between 18:00 and 06:00 keeps them on. The driver may switch them on or off at any time: the automatic rules act only on those transitions, and the driver's choice stands until the next one. A train spawns with nothing on (lights off, doors closed, brakes released, no announcement); one spawned at the yard between 18:00 and 06:00 has its lights set to on. | Met | R35, R36: a train's first tick is its spawn and sets the lights from the time of day. Underground is only taken in on that tick |
| M9 | **Kp/Ki** are set by the engineer only, once, at the very start, in an Engineer-only pop-up. Defaults are offered but never applied on their own; until the engineer commissions the gains the train commands 0 W. This holds for harness-dispatched trains too. **No driver before the gains:** while the selected train is uncommissioned, its console stays hidden behind the sign-in view, which says it is waiting for its gains; the Driver role is refused, and selecting such a train signs the driver out. | Met | No driver before the gains: 2026-10-21 |
| M10 | **Max power 480 kW** (truth, provisional). | Met | — |
| M11 | **Time follows the harness.** Integrated, all timing comes from the central harness's clock (`utils/system_clock.py`: a fixed 0.1 s tick, time of day from 05:00:00). Driven by the bench, the bench keeps its own clock the same way: it starts when the first train is commissioned and from then on always advances, whichever train is selected. 10× runs more ticks, never a longer step. Pause holds every train and the clock; presses made while paused act on the first tick after resuming. | Met | R37: `step_all` takes `time_s` each tick and the console shows it; the automatic lights and the announcement lockout run on it, the Manual repeat's too (R34) |
| M12 | **Acceleration is shown in m/s²** in the numbers drawer only: a debugging exception to `units.md`'s ft/s². The drawer will be removed. | Met | — |
| M13 | **The SW variant is closed.** Only this module is developed. | Met | — |
| M14 | **Driver speed changes are in 1 mph steps** on the dial. Keyboard arrow keys are not required. The dial's scale is fixed at the car's 70 km/h (43.5 mph), whatever is commanded, by decision: it is display only, not a cap (M1), and a commanded speed above 43.5 mph cannot be set from the dial (#29); a press in the bottom gap reads 0, and a drag past either end holds that end rather than wrapping. | Met | — |
| M15 | **The test bench has no cab controls.** It feeds what the Train Model and Track Model send, and Murphy's failures; the cab is driven from the console only. Its `at_station` row (in the Train Model column, under `authority_blocks`) says whether the beacon is heard: every tick while at a station, otherwise once, when a beacon row is sent. Three wheels beside its clock (hours 0–23, minutes and seconds 0–59; dragged or scrolled) and **Set time** set the bench clock to a time of day (greyed under a harness, whose clock is the time). Spawning a train from the bench does not switch the console or the bench to it (the first train spawned is selected, as nothing else is). The bench's input rows are for debugging and will be removed later. | Met | — |
| M16 | **Authority is used as given.** The controller never counts blocks: the count it receives is how far it may go, and it changes only when a new count arrives. Integrated, the Train Model reports a block change to the Track Model, which then sends the next block's count. On the bench, a **Block change** button stands in for that: the next count, one fewer, never below 0. | Met | 2026-10-21 |
| M17 | **Authority 0 sets the target to 0**, and the service brake is applied while the train moves, as a fail safe. Stopping at the right block or station is still the rest of the system's, which lowers the commanded speed in time. | Met | `enforce_safety`. The speed law also holds the service brake at any target of 0 until the train stands, below the 0.05 m/s band too (`stopping`) |
| M18 | **Brake State arrives as two separate inputs:** emergency brake state and service brake state, each what is engaged, not what was commanded. | Met | 2026-10-21: `emergency_brake_state` and `service_brake_state` |
| M19 | **The controller assumes perfect movement.** It models no rolling resistance, grade, mass or brake rate; the speed error is what absorbs every outside force, and the physics is the Train Model's (or, on the bench, the bench's simulation). | Partial | Engine-failure detection still uses mass and `F = P/v` (§4) |
| M20 | **Signal light ahead comes from the Track Model**, directly, on the tick the train enters a signal block. Display only. | Partial | Read as `signal_light_ahead`; not mapped from the Track Model yet (#27) |
| M21 | **The power command is vital: three calculations, voted two out of three.** Each tick the power command (§3) is calculated three times, fresh, from the same inputs; nothing is kept per calculation. A result (the power and the integrator it carries to the next tick) that at least two agree on is used, and the command is marked verified. With no two equal it is a **vitality breach**: this tick's command is rejected and 0 W is sent, the emergency brake latches, the command is marked unverified, and a "Vitality breach" pill shows in the header with the failures. The breach clears on the next tick that agrees; the emergency brake stays on, and the driver may release it only after that (M2). The three calculations are identical, so the vote guards against a corrupted calculation or state, not against a design error common to all three. | Met | `vital.py` `compute_power`, `vote_2oo3`; `power_verified` on the commands (§3). The numbers drawer shows the three calculations and the vote. Shown failing only in `check.py`: the bench cannot reach inside the controller (M0) |

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
| FUNC-036 | 4.9 | Stop correctly at each station | Partial | Stops where authority and commanded speed end, then serves the station (M6, M17); where that is depends on the wayside. The 45 s dwell is the controller's (M6) |
| FUNC-037.1 | 4.10 (1) | Stop when authority is exhausted | Partial | M17: target 0 and the service brake at a count of 0; stopping in time is the wayside's, through the commanded speed |
| FUNC-037.2 | 4.10 | Stop when a failure is detected | Met | M3: any detected failure latches the emergency brake and sets the target to 0 |
| FUNC-038 | — | Detect engine, signal pickup and brake failures | Partial | Detection from returned signals (M3); detecting resolution is not built (#23); the engine rule is being revised (§4, #28). The SRS wording "reported by the Train Model" is out of date (§6) |
| FUNC-047 | 5.8 | Passenger emergency brake | Met | A reported pull latches the controller's e-brake (M2) |
| FUNC-001 / 002 | 1.2 / 1.4 | Run at 1× and 10× | Met | Fixed 0.1 s step; 10× is 100 ticks a second (M11) |
| FUNC-003 | 1.3 | Pause | Met (bench) | Holds every train and the clock; the harness clock owns it when integrated |
| INTF-001.6 | 9.0 (5) | A GUI for the HW Train Controller | Met | |
| — | — | Vital architecture for the Train Controller (course deck; `documents/requirements-matrix.md` §3) | Met | M21: the power command, the only vital calculation, is voted two out of three. The SRS has no requirement for it yet (§6) |
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
| Beacon | station, side `L`/`R`/`LR`, underground | Every tick while the train is on a station's block, nothing otherwise (M6) |

Not used: the speed limit the Train Model also passes through (M1, #24).

**In, from the Track Model directly:** signal light ahead, on the tick the
train enters a signal block (`TrackModelOutputs.signal_seen`; M20).

**In, from the harness:** the tick (`dt`, fixed 0.1 s) and the system time (`time_s`, seconds since midnight of the first simulated day, as `utils/system_clock.py` counts it) (M11).

**Out, to the Train Model, every tick:** power (W, ≥ 0), service brake,
emergency brake, doors bool[2], lights bool[2], temperature setpoint
(°C), announcement (text); and power verified (bool, this module's own:
false on a vitality breach, M21).

**Power** is the controller's only power calculation, and its only vital
one (M21): velocity error
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

A vitality breach (M21) is not a Train Model failure: it is the
controller's own calculations disagreeing, and it clears on the next tick
they agree.

Known limits:
- A brake failure is only seen when the service brake is asked for.
- A cut from ≥ 2 blocks straight to 0 reads as a pickup failure.
- Brake and engine resolution cannot be seen while the emergency brake is
  on. Once the train stands, the driver may release it in Manual (M2, M3,
  R31); a repaired service brake can then read applied (M4), but nothing
  yet concludes that it is resolved, and an engine still cannot be seen
  (#23).

## 5. Revisions made

The revisions R2–R37, each with what changed and where, are in
`CHANGELOG.md` §4. Later changes are recorded there by commit (§2).

## 6. Later

**Outside this folder (separate PR):**
- SRS: add a requirement for the Train Controller's vital architecture (M21).
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
- `ui/__pycache__/*.pyc` is committed (`OPEN_ISSUES.md` #20).
- `check.py` is timing-sensitive under load (`OPEN_ISSUES.md` #21).
