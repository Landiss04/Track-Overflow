# Train Controller (HW): Central Harness Integration

<<<<<<< HEAD
Oct 16, 2026 · @paperbird

## Overview

The central harness owns dispatch: it adds a Train Controller when a train enters service, removes it when it leaves, and steps every controller once per tick through `TrainControllerFleet`. The Train Controller owns the speed law and the safety path. The Train Model owns the physics (D009), so the fleet never runs its toy plant when the harness drives it.

The rules the controller follows (commanded speed as the limit, doors, announcements, timing) are in [`REQUIREMENTS.md`](REQUIREMENTS.md), rules M1–M15. Where this guide and that file disagree, `REQUIREMENTS.md` wins.
=======
Oct 16, 2026 · @paperbird · updated Oct 22, 2026

## Overview

The central harness owns dispatch: it adds a Train Controller when a train enters service, removes it when it leaves, and steps every controller once per tick through `TrainControllerFleet`. The Train Controller owns the speed law and the safety path, and knows only what it receives and sends (M0). The Train Model owns the physics (D009); the controller has none of its own.

Either the harness drives the controllers or the test bench does, never both. The bench drives them the same way, through `step_all`, with its own simulation (`bench_sim.py`) standing in for the rest of the system. The harness never uses that simulation.

The rules the controller follows (commanded speed as the limit, doors, announcements, timing) are in [`REQUIREMENTS.md`](REQUIREMENTS.md), rules M0–M20, each marked with whether the code has it yet. Where this guide and that file disagree, `REQUIREMENTS.md` wins.
>>>>>>> origin/Train_Ctrl_integration

The console is optional. Given the harness's fleet, it shows those trains and takes operator actions, but it adds, removes and steps nothing.

Each tick:

1. The harness builds one input dict per train from the Train Model and Track Model signals, in SI.
<<<<<<< HEAD
2. `fleet.step_all(TICK_S, inputs_by_id)` reads every train's inputs, then steps every controller.
=======
2. `fleet.step_all(TICK_S, inputs_by_id, time_s)` reads every train's inputs, then steps every controller. `time_s` is the shared clock's time this tick.
>>>>>>> origin/Train_Ctrl_integration
3. It returns one `TrainModelCommands` per train, which the harness maps onto the Train Model's inputs (D005).

## Getting the code

<<<<<<< HEAD
The package is `Train-Ctrl_HW/train_ctrl/` on the `Train_Ctrl_integration` branch. Commit: **`d8b88ae`**.
=======
The package is `Train-Ctrl_HW/train_ctrl/` on the `Train_Ctrl_integration` branch. This guide describes the interface as of Oct 21, 2026 (`step_all` with `time_s`, two brake state inputs); check `CHANGELOG.md` §2 for the commit.
>>>>>>> origin/Train_Ctrl_integration

| File | Imports Qt | Holds |
| --- | --- | --- |
| `fleet.py` | No | `TrainControllerFleet`: the spawner the harness calls |
<<<<<<< HEAD
| `control.py` | No | `ControllerCore`: one train's speed law, safety path and toy plant |
| `state.py` | No | `State`, `TrainModelCommands` |
| `inputs.py` | No | `read_inputs`: reads and checks one train's signals; `EVERY_TICK`: the keys required each tick |
| `errors.py` | No | The exceptions the fleet raises |
| `constants.py`, `units.py` | No | Rates (`TICK_S`), plant figures, thresholds, unit conversions |
=======
| `control.py` | No | `ControllerCore`: one train's speed law and safety path |
| `state.py` | No | `State`, `TrainModelCommands` |
| `inputs.py` | No | `read_inputs`: reads and checks one train's signals; `EVERY_TICK`: the keys required each tick |
| `errors.py` | No | The exceptions the fleet raises |
| `constants.py`, `units.py` | No | Rates (`TICK_S`, `CLOCK_START_S`), bench-simulation figures, thresholds, unit conversions |
| `bench_sim.py` | No | `SimTrain`: the test bench's stand-in for the Train Model and Track Model. Bench only; the harness ignores it, and `import train_ctrl` does not re-export it |
>>>>>>> origin/Train_Ctrl_integration
| `backend.py` | Yes | `ConsoleBackend`: the console's Qt bridge |
| `app.py` | Yes | `run()`: opens the console and bench windows |
| `console_theme.py` | No, but imports `ui.theme` | Console design tokens |

<<<<<<< HEAD
`import train_ctrl` imports no Qt and re-exports everything in the No rows. Import `train_ctrl.backend` and `train_ctrl.app` by name, and only when you want the console.
=======
`import train_ctrl` imports no Qt and re-exports everything in the No rows except `bench_sim.py`. Import `train_ctrl.backend` and `train_ctrl.app` by name, and only when you want the console.
>>>>>>> origin/Train_Ctrl_integration

`Train-Ctrl_HW` is not a valid package name because of the hyphen, so the harness puts that folder on the import path itself:

```python
import sys
sys.path.insert(1, "<repo>/Train-Ctrl_HW")   # for train_ctrl
sys.path.insert(1, "<repo>")                 # only for the console: ui.*

from train_ctrl import TrainControllerFleet
```

## Lifecycle

One fleet holds every train's controller, keyed by train ID. IDs are opaque strings (identifiers.md); the fleet never parses them.

```python
from train_ctrl import TICK_S, TrainControllerFleet

fleet = TrainControllerFleet()
<<<<<<< HEAD
=======
time_s = clock.sim_time_s               # utils/system_clock.py, this tick
>>>>>>> origin/Train_Ctrl_integration

# A train enters service.
core = fleet.add("T-114", "GREEN LINE")     # returns its ControllerCore

# Every tick: exactly one input dict per train in service, with every
# key in EVERY_TICK.
commands = fleet.step_all(TICK_S, {
    "T-114": {
        "commanded_speed": 12.0,        # m/s
        "authority_blocks": 10,
        "actual_speed": 0.0,            # m/s, from the Train Model
<<<<<<< HEAD
        "brake_state": [False, False],  # [emergency, service], as applied
=======
        "emergency_brake_state": False, # as engaged, not as commanded
        "service_brake_state": False,   # as engaged, not as commanded
>>>>>>> origin/Train_Ctrl_integration
        "door_state": [False, False],   # [left, right], as reported
        "light_state": [True, True],    # [interior, exterior], as reported
        "cabin_temperature": 21.0,      # °C, as reported
    },
<<<<<<< HEAD
})
=======
}, time_s)
>>>>>>> origin/Train_Ctrl_integration
cmd = commands["T-114"]                 # TrainModelCommands

# A train leaves service.
fleet.remove("T-114")
```

Also available: `fleet.get(id)`, `fleet.ids()` in the order trains were added, `id in fleet`, `len(fleet)` for how many controllers exist, and iteration over the cores.

`dt` must be `TICK_S`, 0.1 s of simulation (truth D006 / D017). Any other value raises `InvalidInputError` and no train steps. Faster simulation means more ticks per second, never a longer tick. `dt` is still an argument so the call matches `TrainModelFleet.step_all`.

<<<<<<< HEAD
=======
`time_s` is the system time this tick: seconds since midnight of the first simulated day, as `utils/system_clock.py` counts it (it starts at 05:00:00, 18,000 s, and keeps counting past midnight). All the controller's timing follows it (M11), and the console's clock shows it. Anything that is not a finite number of at least 0 (text, `True`, NaN, a negative) raises `InvalidInputError` and no train steps.

>>>>>>> origin/Train_Ctrl_integration
## Inputs

Each train's input dict uses the keys and shapes in truth `signals/`, in SI. These are every key `read_inputs` accepts.

**Required every tick** (`EVERY_TICK`):

| Key | Unit or shape | Notes |
| --- | --- | --- |
| `commanded_speed` | m/s | Negative is clamped to 0. This is the speed limit: there is no separate one (M1) |
| `authority_blocks` | int, blocks | Negative is clamped to 0 |
| `actual_speed` | m/s, signed | Kept signed for rollback |
<<<<<<< HEAD
| `brake_state` | `[emergency, service]` | What is applied, not what was commanded |
=======
| `emergency_brake_state` | bool | Engaged, not commanded: true for the controller's command or a passenger pull. Train Model `ControllerOutputs.emergency_brake_active` |
| `service_brake_state` | bool | Engaged, not commanded: false under a brake failure, and false while the e-brake is engaged. Train Model `ControllerOutputs.service_brake_active` |
>>>>>>> origin/Train_Ctrl_integration
| `door_state` | `[left, right]` | Reported door state |
| `light_state` | `[interior, exterior]` | Reported light state |
| `cabin_temperature` | °C | Reported cabin temperature |

**Optional** (a key left out keeps its last value):

| Key | Unit or shape | Notes |
| --- | --- | --- |
<<<<<<< HEAD
| `beacon_station` | str | Station name. A new name is how the controller learns a station is ahead |
| `beacon_side` | `"L"`, `"R"`, `"LR"` | Any other value is ignored |
| `beacon_underground` | bool |  |
| `signal_light_ahead` | `"RED"`, `"YELLOW"`, `"GREEN"`, `"SUPER GREEN"` | Shown only; any other value is ignored |
=======
| `beacon_station` | str | Station name |
| `beacon_side` | `"L"`, `"R"`, `"LR"` | Any other value is ignored |
| `beacon_underground` | bool | Turns the lights on when true, off when a later beacon says false (unless night; M8) |
| `signal_light_ahead` | `"RED"`, `"YELLOW"`, `"GREEN"`, `"SUPER GREEN"` | Shown only; any other value is ignored. From the Track Model directly (`TrackModelOutputs.signal_seen[train_id]`, on the tick the train enters a signal block; M20), not yet mapped (`OPEN_ISSUES.md` #27) |

**Send the beacon keys only on a tick the train hears a beacon**, as the Train Model passes it (`ControllerOutputs.beacon`, `None` on every other tick): leave all three out otherwise. A beacon turning up, or naming a new station, is a station to serve (M7). Sending the beacon every tick is also safe: only the first tick of an unbroken run counts. The last values are kept between beacons.

Not an input: the speed limit the Train Model passes through (`ControllerOutputs.speed_limit_mps`); leave it out, or it is ignored like any unknown key (M1, `OPEN_ISSUES.md` #24).
>>>>>>> origin/Train_Ctrl_integration

Rules:

- **One entry per train in service, every tick.** An unknown ID raises `UnknownTrainError`; a missing one raises `TrainControllerError`.
<<<<<<< HEAD
- **Every required key, every tick.** A train missing any `EVERY_TICK` key raises `InvalidInputError`, so a stale `brake_state` can never read as a brake failure.
=======
- **Every required key, every tick.** A train missing any `EVERY_TICK` key raises `InvalidInputError`, so a stale brake state can never read as a brake failure.
>>>>>>> origin/Train_Ctrl_integration
- **Unknown keys are ignored silently.** A misspelt optional key does nothing and raises nothing. `speed_limit` is ignored the same way.
- **All or nothing.** Every train's inputs are read before any train steps. One bad value raises `InvalidInputError` and leaves the whole fleet unchanged.
- **There is no failure-status input.** The Train Model no longer reports failures; the controller infers them from what it sends back (see Known issues).

## Outputs

`step_all` returns `dict[str, TrainModelCommands]`, one frozen dataclass per train, with one field per truth signal. The harness maps these onto the Train Model's own input types (D005).

| Field | Unit or shape | Signal |
| --- | --- | --- |
| `power_w` | W, 0 to 480,000 | power-command |
| `service_brake` | bool | service-brake-command |
| `emergency_brake` | bool | emergency-brake-command |
| `door_command` | `(left, right)` | door-command |
| `light_command` | `(interior, exterior)` | light-command |
| `temperature_setpoint_c` | °C | temperature-setpoint |
| `announcement` | str | announcement: a command for the Train Model to play, otherwise empty |
<<<<<<< HEAD
| `passenger_brake_release` | bool, one-shot | passenger-brake-release: true on the step after the driver releases the emergency brake, which releases a passenger pull with it; false otherwise |

- **Speed.** The target is the commanded speed, never above the car's 70 km/h (43.5 mph). The Train Model has no governor (D009), so the controller holds the cap (M1).
- **Traction** is 0 while either brake is commanded, and while an Automatic station stop holds the train. A train that is not commissioned commands 0 W (see Commissioning).
- **Doors** (M6). A door opens only when `actual_speed` reports the train stopped (under 0.1 m/s), and only on the platform side the last beacon gave. In Automatic, when a new `beacon_station` has arrived and the train stops, the controller opens the platform side and holds the train for the 45 s dwell, which the CTC Office schedules and the controller enforces (truth D007). Once the dwell is over and the Track Signal has resumed (commanded speed and authority both above 0), it closes the doors, and it moves off only once `door_state` reports both closed. A station the train runs through stays pending until its next stop (`OPEN_ISSUES.md` #25).
- **Announcements** (M7). The controller only sends the command; the Train Model makes the announcement. In Automatic, a new `beacon_station` sends that station's name for 5 s. In Manual, the driver's press does.

## Under the central harness

Added 2026-10-20 for Phase 1 of the central harness (`documents/system-integration-design.md` §5). The harness runs every module in its own process (D005), so it does not import this package. `python track_overflow.py --module train-controller-sw` runs [`train_ctrl/module_process.py`](train_ctrl/module_process.py), which:

- holds one `TrainControllerFleet(echo_ticks=ECHO_TICKS)` and shows the console for it, without the bench;
- steps the fleet once per harness tick, on the inputs the harness sends for every train in service, keyed by train ID, as the Inputs section describes;
- adds a train the first time the harness names it, and removes it when the harness stops naming it (D022: the CTC Office releases and retires trains);
- replies with each train's `TrainModelCommands`, field by field, and rejects the tick whole when `step_all` raises.

Two things differ from the in-process use described above:

- **Reports come back two ticks late.** Each module reads the others' outputs from the tick before (truth D017), so a command this controller sends on one tick reaches the Train Model on the next, and its report arrives the tick after that. `echo_ticks` tells the fleet so: a reported emergency brake that the controller itself commanded within the last `echo_ticks` steps is its own command coming back, not a passenger pull. The console's own fleet keeps the default, 0, since the toy plant and the bench answer on the same step.
- **Tests can stand in for the engineer.** `--engineer-gains KP KI` sets those gains on each train as it joins, the way `commission_gains` does. It exists for automated tests only; a real run never passes it, and every train waits for an engineer (truth D024).
=======

- **Speed.** The commanded speed is the only cap (M1): Automatic targets it; in Manual it caps the driver's setpoint, also when it drops. There is no 70 km/h cap, since the controller cannot know the true limit; keeping under it is the wayside's, through the commanded speed.
- **Traction** is 0 while either brake is commanded, and while an Automatic station stop holds the train. A train that is not commissioned commands 0 W (see Commissioning).
- **Doors** (M6). A door opens only when `actual_speed` reports the train stopped (under 0.1 m/s): either side, except at a station (arrived, until it departs), where only the platform side the last beacon gave opens. In Automatic, on arriving at a station (a station beacon heard, `authority_blocks` 0, stopped) the controller opens the platform side and holds the train. When the Track Signal resumes (commanded speed and authority both above 0), it closes the doors, and it moves off only once `door_state` reports both closed. The dwell itself is the Train Model's.
- **Announcements** (M7). The controller only sends the command; the Train Model makes the announcement. In both modes it sends, each for 5 s of `time_s`: "The train *id* is arriving soon" when `authority_blocks` reaches 3 (normally coming down; a rise to 3 announces too); "The train *id* has arrived at *station*" once a station beacon has been heard and the train stands (`actual_speed` under 0.1 m/s) with `authority_blocks` 0; "The train *id* is departing from *station*" once `door_state` reports both closed and `commanded_speed` and `authority_blocks` are back above 0. *id* is the ID the train was added with. In Manual, the driver's press repeats the last of these, held 5 s of `time_s` the same way.
- **Lights** (M8). In both modes the controller turns `light_command` on with an underground beacon and at 18:00 of `time_s`, and off with a later not-underground beacon (unless it is 18:00–06:00) and at 06:00 (unless underground). In between, the driver's choice stands. On a train's first tick (its spawn at the yard) the controller sets `light_command` on if `time_s` is 18:00–06:00, off otherwise.
>>>>>>> origin/Train_Ctrl_integration

## Showing the console

Pass the harness's fleet in, and the console shows its trains without stepping them. Either build the backend yourself:

```python
from train_ctrl.backend import ConsoleBackend

console = ConsoleBackend(fleet=fleet)
```

or let `run()` open the window, which reuses a `QGuiApplication` the harness already made:

```python
from train_ctrl.app import run

run(console=True, bench=False, fleet=fleet)   # blocks until the window closes
```

How it behaves with a harness fleet:

- **No stepping.** The console's control timer (10 ticks a second at 1×, 100 at 10×, 0.1 s each) only runs when it owns its fleet, so no train is stepped twice per tick.
- **Roster follows the harness.** The console compares the fleet's IDs once per UI tick (10 Hz) and updates its train pickers. If the selected train is removed, selection moves to the first remaining train.
- **Count.** The snapshot's `train_count` is `len(fleet)`.
<<<<<<< HEAD
- **Clock.** The console's clock is only an estimate under a harness fleet, until D017's shared clock reaches the console.
- **Pause.** The bench's Pause holds only a fleet the console owns; it does not stop the harness.
- **Console only.** Open the console without the bench: see Known issues.
=======
- **Clock.** The console shows the `time_s` the selected train last received from the harness.
- **Pause.** The bench's Pause holds only a fleet the console owns; it does not stop the harness.
- **Console only.** Open the console without the bench: the bench refuses edits to a harness's trains, but spawning from it still breaks the harness (see Known issues).
>>>>>>> origin/Train_Ctrl_integration
- **Path.** `run()` needs the repo root and `Train-Ctrl_HW` on the import path, for `ui.*` and `check.py`.

## Commissioning

Every train starts uncommissioned and commands 0 W until an engineer sets its gains. The brakes and the safety path run from the first tick regardless, so an uncommissioned train can still be stopped and still reports its brakes.

<<<<<<< HEAD
Today gains can only be set from the console:
=======
Decided (M9): the engineer commissions every train, harness-dispatched or not, once, at the very start. Defaults are offered but never applied on their own. Until then the train has no driver: with it selected, the console stays behind the sign-in view and the Driver role is refused. Gains are set from the console:
>>>>>>> origin/Train_Ctrl_integration

1. Select the train in the console.
2. Sign in as Engineer, and set Kp and Ki.
3. The gains are fixed for that train's run, and the console hands back to the driver after 1.5 s.

Each train is commissioned once, separately. The Engineer role is refused on a train that is already commissioned.

<<<<<<< HEAD
There is no harness-side way to commission a train (`OPEN_ISSUES.md` #22). Setting `core.armed = True` directly skips the engineer and locks the role out, so the harness should not do it.
=======
So there is no harness-side way to commission a train, by design. Setting `core.armed = True` directly skips the engineer and locks the role out, so the harness must not do it.
>>>>>>> origin/Train_Ctrl_integration

## Errors

Every error derives from `TrainControllerError`, so one `except` catches them all. All are importable from `train_ctrl`.

| Exception | Raised by | When |
| --- | --- | --- |
| `DuplicateTrainError` | `add` | That ID already has a controller |
| `UnknownTrainError` | `get`, `remove`, `step_all` | No controller for that ID. Also a `KeyError` |
| `TrainControllerError` | `step_all` | A train in service has no inputs this tick |
<<<<<<< HEAD
| `InvalidInputError` | `step_all` | `dt` is not `TICK_S`; a train is missing an `EVERY_TICK` key; or a value can't be read as its type, e.g. `authority_blocks: "abc"` or a `brake_state` of the wrong length |
=======
| `InvalidInputError` | `step_all` | `dt` is not `TICK_S`; `time_s` is not a finite time of at least 0; a train is missing an `EVERY_TICK` key; or a value can't be read as its type, e.g. `authority_blocks: "abc"` or a `door_state` of the wrong length |
>>>>>>> origin/Train_Ctrl_integration

A failed `step_all` changes no train.

## Comparison with TrainModelFleet

The calls a harness makes look the same on both fleets, so one dispatch loop can drive both. Compared against `TrainModelFleet` on `development`.

| Member | `TrainModelFleet` | `TrainControllerFleet` |
| --- | --- | --- |
| `add` | `(train_id, line="", config=None, *, state=None)` | `(train_id, line="")` |
| `remove`, `get`, `ids`, `in`, `len`, iteration | Same | Same |
<<<<<<< HEAD
| `step_all` arguments | `(dt, Mapping[str, TrainModelInputs], *, override_passenger_brake=())` | `(dt, Mapping[str, dict])` |
=======
| `step_all` arguments | `(dt, Mapping[str, TrainModelInputs], *, override_passenger_brake=())` | `(dt, Mapping[str, dict], time_s)` |
>>>>>>> origin/Train_Ctrl_integration
| `step_all` returns | `dict[str, TrainModelOutputs]` | `dict[str, TrainModelCommands]` |
| Validates `dt` | Yes | Yes: must be `TICK_S` (0.1 s) |
| Missing-inputs error | `TrainModelFleetError` | `TrainControllerError` |
| `DuplicateTrainError`, `UnknownTrainError` | Its own module's classes | `train_ctrl.errors` |
| Selection and roster for a window | On the fleet, a `QObject` | On `ConsoleBackend`; the fleet is Qt-free |

<<<<<<< HEAD
Not checked: `TrainModelInputs`, `TrainModelOutputs`, and where the Train Model's exceptions are defined. If both modules share an error module, the exception rows match after all.
=======
The Train Model's exceptions are its own classes in `train_model/fleet.py` (`TrainModelFleetError`, derived from `TrainModelError`; its `UnknownTrainError` is also a `KeyError`), so the exception rows do differ. Not compared here: `TrainModelInputs` and `TrainModelOutputs`.
>>>>>>> origin/Train_Ctrl_integration

## Known issues

The controller infers failures from what the harness sends back, so three inputs must be faithful or it will stop a healthy train on the emergency brake.

| Failure inferred | Trigger | What the harness must send |
| --- | --- | --- |
<<<<<<< HEAD
| Brake | Service brake commanded, and `brake_state[1]` false for 0.5 s (seen 0.6 s after the request, one 0.1 s tick later) | The service brake's real applied state |
| Engine | Over the last 6 s: power commanded every tick, no brake commanded or shown in `brake_state` on any tick, and `actual_speed` falling steadily by more than 0.05 m/s; never within 0.05 m/s of target (Kevin Schillinger, 2026-10-21) | The real `actual_speed` and `brake_state` every tick |
| Signal pickup | `commanded_speed` and `authority_blocks` both drop to 0 in one update, from 2 or more blocks | Authority counting down normally, not a jump to 0 |

A detected failure latches until cleared; the harness has no call to clear one.
=======
| Brake | Last tick commanded the service brake with the e-brake off, and this tick's `service_brake_state` is false (M4). The service brake stays commanded under a brake failure | The service brake's real applied state |
| Engine | Power that should pull 0.1 m/s² or more, and `actual_speed` up by less than 0.05 m/s for 2 s. **Known false positive on grades:** against `development`'s Train Model it flags a healthy full train 2.4–2.9 s onto a +2 % or +5 % grade, latching the emergency brake (`OPEN_ISSUES.md` #28). A replacement rule is undecided | The real `actual_speed` every tick |
| Signal pickup | `commanded_speed` and `authority_blocks` both drop to 0 in one update, from 2 or more blocks | Authority counting down normally, not a jump to 0 |

A detected failure latches until cleared; the harness has no call to clear one. Decided: the controller detects resolution itself (M3), not yet built; it cannot see brake or engine resolution while the e-brake is on (`OPEN_ISSUES.md` #23). The failure latches the e-brake once, on detection; at a stand the driver may release it in Manual with the failure still latched, and `emergency_brake` then stays false.
>>>>>>> origin/Train_Ctrl_integration

`door_state` must be faithful too: an Automatic train leaves a station only once `door_state` reports both doors closed. If it never does, the train waits at the station.

Open issues:

<<<<<<< HEAD
- [x] **Emergency echo re-latches the brake.** Fixed 2026-10-20 for the central harness: see Under the central harness. `brake_state[0]` true while the controller has not commanded the brake within the last `echo_ticks` steps reads as a passenger pull; within them it is the controller's own command coming back. The driver's release also sends the one-shot `passenger_brake_release`, so the Train Model clears a passenger pull with it.
- [ ] **The bench breaks a harness fleet.** A train spawned from the bench is unknown to the harness, so the next `step_all` raises. Open the console only.
- [ ] **No harness commissioning.** See Commissioning.
- [ ] **Exception classes differ from `TrainModelFleet`'s.** See the comparison above.
=======
- [x] **Emergency echo re-latched the brake.** Fixed Oct 21: a pull is an `emergency_brake_state` that turns on while the controller isn't commanding it, so last tick's brake echoed back, or a passenger latch still held, does not undo the driver's release (M2). Still open with Kevin: what the Train Model reports after the driver's release, since only a test call clears its passenger latch (`OPEN_ISSUES.md` #25). One consequence: a pull reported within a tick or two of a release, before the reported state has gone false, is not seen.
- [ ] **The bench breaks a harness fleet.** A train spawned from the bench is unknown to the harness, so the next `step_all` raises. The bench now refuses edits to a harness's trains, but not spawning. Open the console only.
- [x] **No harness commissioning.** Decided: by design (see Commissioning).
- [ ] **Exception classes differ from `TrainModelFleet`'s.** See the comparison above.
- [ ] **Engine detection trips on grades.** A healthy train climbing a +2 % or steeper grade under full power is taken for an engine failure and stopped on the emergency brake (`OPEN_ISSUES.md` #28). Until it is replaced, expect this on the Green line's grades.
>>>>>>> origin/Train_Ctrl_integration

## Trying it

`Train-Ctrl_HW/harness_sim.py` is a stand-in central harness: it owns a fleet, spawns and removes trains on a schedule, and plays a minimal Train Model. Run it from `Train-Ctrl_HW`:

**It is for testing only.** The real central harness doesn't import or run it, and can ignore it entirely when integrating.

```
python harness_sim.py
```

The terminal prints the controller count at each change, and the console's train picker follows it.

| Time | Event | Controllers |
| --- | --- | --- |
| 0 s | `T-1` spawned | 1 |
| 5 s | `T-2` spawned | 2 |
| 10 s | `T-3` spawned | 3 |
| 30 s | `T-1` removed | 2 |

<<<<<<< HEAD
Every train gets the same inputs each tick, the full `EVERY_TICK` set at the 0.1 s step: 55 mph commanded, 20 blocks of authority, a 75 °F cabin, a GREEN signal ahead, and doors and lights echoed from the last commands. Trains stay stopped until an engineer commissions each one from the console.
=======
Every train gets the same inputs each tick, the full `EVERY_TICK` set at the 0.1 s step: 55 mph commanded, 20 blocks of authority, a 75 °F cabin, a GREEN signal ahead, and doors, lights and the service brake echoed from the last commands. It keeps its own clock, from 05:00:00, and passes it as `time_s`. Trains stay stopped until an engineer commissions each one from the console.
>>>>>>> origin/Train_Ctrl_integration

What the stand-in simplifies:

- Its physics is power into acceleration, capped at 0.5 m/s², and the two brake rates. There is no grade or resistance.
<<<<<<< HEAD
- It reports the emergency brake only for a passenger pull, which it never makes, to avoid the echo issue above.
- The cabin reads 75 °F whatever the thermostat says. The 55 mph command is capped at the car's 43.5 mph (M1): trains settle at about 43.6 mph.
=======
- It reports the emergency brake state as false always: it never makes a passenger pull, and does not echo the command.
- The cabin reads 75 °F whatever the thermostat says. The commanded speed is the only cap (M1), so trains settle at about 55.1 mph (since Oct 21; before, a 70 km/h cap held them at about 43.6 mph).
>>>>>>> origin/Train_Ctrl_integration
