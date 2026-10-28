# Prompt: add a sequence diagram for every use case

You are editing an existing draw.io file, `train-model-uml.drawio`. It holds the UML
diagrams of one software module, the **Train Model**: the physics simulation of one
train in a five-module course project. You have no access to its code. Every fact you
need is in this prompt. Don't invent messages, methods or participants that aren't
listed here. If something seems missing, say so in your report rather than filling the
gap.

## 1. The task

- **What exists.** The file's use case page has 16 use cases. One of them, *Advance one
  simulation step*, already has a sequence diagram, on the page named
  `Sequence: Advance one simulation step`.
- **What to add.** Add one new page for each of the other 15 use cases, so every use
  case has its own sequence diagram.
- **Don't change existing pages.** Leave every existing page, including the existing
  sequence page, exactly as it is.

Name each new page `Sequence: <use case name>` with the use case's name as it appears
on the use case page, minus the requirement IDs. Examples:
`Sequence: Pull passenger emergency brake` and `Sequence: Receive track data`. Put the
new pages straight after the existing sequence page, in the order of section 5.

## 2. Match the existing sequence page

Open `Sequence: Advance one simulation step` and copy its conventions exactly. Every
new page should look like part of the same set.

- **Frame.** An outer `umlFrame` labelled `sd <use case name>` around the whole
  diagram.
- **Styles.** Reuse the existing styles for lifelines, synchronous calls (filled
  arrowhead), asynchronous signals (open arrowhead, solid line), replies (open
  arrowhead, dashed), self-calls (label to the right), `alt` / `opt` fragments, dashed
  operand separators, guard text cells and notes. Copy the style strings from that
  page; don't invent new ones.
- **Lifeline labels.** Use the same labels as that page wherever the same participant
  appears:
  - `clock: SystemClock`
  - `«external»<br>central harness`
  - `state: TrainModelState`
  - `model: train_model::model::TrainModel`
  - `Main.qml (Train Model window)`
- **Actor lifelines.** For a human or an outside module, use an actor-headed lifeline:
  draw.io's `umlLifeline` with `participant=umlActor`, labelled as on the use case
  page:
  - `Passenger`
  - `Murphy`
  - `«external module»<br>Train Controller`
  - `«external module»<br>Track Model`
- **Numbering.** Number messages from 1 on each page: `1 : …`, `2 : …`.
- **Reuse with `ref`.** Where a diagram says "ref: Advance one simulation step", draw
  an interaction use. That's a `umlFrame` labelled `ref`, spanning the lifelines
  involved, with the centred text `Advance one simulation step`. Don't redraw the step.
- **Editability.** Use native draw.io shapes only, with no images, and give every new
  cell a readable id prefixed with the page, e.g. `sq-ebrake-msg-3`. Keep each message
  exactly horizontal. Size the lifeline spacing so every label fits on its arrow. Keep
  each page compact: only the lifelines that page uses.

## 3. Background you need

This background is for labelling things correctly. Don't draw it.

- **How a step happens.** The **central harness** sits outside the module. It owns the
  shared simulation clock (`SystemClock`, a tick every 0.1 s at 1× or ten times as
  often at 10×, with dt fixed). On each tick it calls `TrainModelState.step(dt, inputs)`.
  `TrainModelState` is the module's Qt wrapper; it calls
  `train_model::model::TrainModel.step(dt, inputs)`, which does the physics.
- **The Train Model reads no other module.** The Train Controller and the Track Model
  never call it directly. The harness collects their outputs, maps them into the Train
  Model's input types (`ControllerCommands`, `TrackInputs`), and delivers the Train
  Model's outputs back to them (`ControllerOutputs` to the Train Controller,
  `TrackOutputs` to the Track Model). Show external modules talking **to the harness**,
  never to `state` or `model`.
- **The window.** It (`Main.qml`) binds to `TrainModelState`. After every change,
  `state` calls its own `_refresh()`, which rebuilds the snapshot the window reads, and
  emits `snapshotChanged`. Window buttons call `state` slots directly.
- **Physics only.** The Train Model doesn't regulate speed, cap speed at 70 km/h, cut
  traction under braking or enforce a door interlock (D009). Never draw any of these.
- **Failures.** There are three: engine, signal pickup and brake. Murphy sets them in
  the window. They aren't reported to the Train Controller.
- **Units and terms.** SI, with grade in degrees and temperature in °C. The track
  signal carries **commanded speed**, never "suggested speed".

## 4. Constants you may quote

| Name | Value |
|---|---|
| `MAX_DT_S` | 60 |
| `MAX_COUNT` | 2^31 − 1 |
| `MAX_BEACON_CHARS` | 128 |
| Cabin rate `CABIN_TEMP_RATE_PER_S` | 1/300 |
| Initial cabin temperature | 20 °C |
| Capacity | 222 |
| Crew | 5 |
| Passenger mass | 77.1107 kg |
| Max power | 480 kW |
| Traction limit | 25,717 N |
| Service brake | 61,720 N |
| Emergency brake | 140,413 N |
| Rolling resistance | c_rr 0.002 |
| g | 9.81 m/s² |
| Announcement popup timeout | 30 s |

## 5. The 15 diagrams

Each section lists the lifelines, left to right, then the messages in order. "a → b" is
a call from a to b. *(self)* is a self-call, *(reply)* a reply, *(async)* an
asynchronous signal. Fragments are written as `alt [guard] … else [guard] … end` and
`opt [guard] … end`. Notes are attached to the message or fragment named.

### 5.1 Sea-level use cases (one actor goal each)

#### View train status

**Lifelines:** Passenger · Main.qml · state

1. ref: Advance one simulation step (spanning `state` only; it ends in steps 2–3 here)
2. state *(self)* `_refresh()`
3. state → Main.qml *(async)* `snapshotChanged`
4. Main.qml → state `read snapshot, doors, failures, activeFailureCount, running`
5. state → Main.qml *(reply)* `current values (SI)`
6. Main.qml → Passenger *(async)* `show speed, acceleration, mass, crew and passengers,
   doors, lights, brakes, cabin temperature, position, failures, clock`

**Note:** "Read only. The window converts the SI values for display. Train ID, line and
arrival time have no source yet and show a dash."

#### View announcement

**Lifelines:** Train Controller · central harness · state · model · Main.qml · Passenger

1. Train Controller → central harness *(async)* `ControllerCommands (announcement)`
2. central harness → state `step(dt, inputs)`
3. state → model `step(dt, inputs)`
4. model → state *(reply)* `TrainModelOutputs`
5. state *(self)* `_refresh(): snapshot.announcement = inputs.announcement`
6. state → Main.qml *(async)* `snapshotChanged`
7. `alt [announcement changed and not empty]`
   1. Main.qml *(self)* `open(): show popup, restart 30 s timer`
   2. Main.qml → Passenger *(async)* `announcement text`

   `else [announcement is empty]`

   3. Main.qml *(self)* `close()`

   `end`
8. `opt [Passenger presses Dismiss or Escape]`
   1. Passenger → Main.qml `dismiss`
   2. Main.qml *(self)* `close()`

   `end`
9. `opt [30 s pass]` Main.qml *(self)* `close()` `end`

**Note:** "The popup isn't modal, so the emergency brake button stays in reach. The
same announcement on later steps doesn't reopen it."

#### Pull passenger emergency brake

**Lifelines:** Passenger · Main.qml · state · model

1. Passenger → Main.qml `press "Apply emergency brake" and confirm`
2. Main.qml → state `applyEmergencyBrake()`
3. state → model `pull_passenger_emergency_brake()`
4. model *(self)* `_passenger_ebrake_pulled = True`
5. model *(self)* `_refresh_discrete_outputs(): emergency_brake_active = true`
6. state *(self)* `_refresh()`
7. state → Main.qml *(async)* `snapshotChanged`
8. Main.qml *(self)* `disable the button while the emergency brake is active`
9. ref: Advance one simulation step (spanning `state` and `model`), with a note:
   "Every later step: `_brake_n()` applies the emergency force, 140,413 N."

**Note:** "The pull latches. The window offers no release; `releaseEmergencyBrake()`
does nothing, and how the latch is released is undecided (D011). A brake failure
doesn't stop it: brake failure blocks only the service brake."

#### Board and disembark passengers

**Lifelines:** Passenger · Track Model · central harness · state · model

1. Passenger → Track Model *(async)* `board at the station`
2. Track Model → central harness *(async)* `passengers_boarded`
3. central harness → state `step(dt, inputs)`
4. state → model `step(dt, inputs)`
5. model *(self)* `_update_passengers(door_left, door_right, boarded, stopped)`
6. `alt [stopped and a door open]`
   1. `opt [no draw yet this stop]`
      1. model *(self)* `n_passengers −= random 0..n_passengers (seeded _rng)`
      2. model *(self)* `_stop_drawn = True`

      `end`
   2. model *(self)* `n_passengers += min(boarded, 222 − n_passengers)`

   `else [moving or doors closed]`

   3. model *(self)* `nobody boards; the count is not kept`

   `end`
7. model *(self)* `_mass_kg(): empty mass + (5 crew + passengers) × 77.1107 kg`
8. model → state *(reply)* `TrainModelOutputs (passenger_capacity)`
9. state → central harness *(reply)* `TrainModelOutputs`
10. central harness → Track Model *(async)* `TrackOutputs (passenger_capacity)`

**Note:** "Passengers get off once per stop, before anyone boards. A stop ends when the
train moves, which resets `_stop_drawn`."

#### Inject / clear failure

**Lifelines:** Murphy · Main.qml · state · model

1. Murphy → Main.qml `press Induce (or Clear) on a failure`
2. Main.qml → state `setFailure(name, active)`
3. `alt [already in that state]`
   1. state → Main.qml *(reply)* `no change`

   `else [changed]`

   2. state *(self)* `_failures[name] = active`
   3. state → model `set_failures(FailureState(engine, signal_pickup, brake))`
   4. model *(self)* `_refresh_discrete_outputs()`
   5. state *(self)* `_refresh()`
   6. state → Main.qml *(async)* `snapshotChanged`
   7. state → Main.qml *(async)* `failuresChanged`
   8. Main.qml *(self)* `active failure's button turns red and reads Clear`

   `end`
4. ref: Advance one simulation step (spanning `state` and `model`)

**Note:** "From the next step, the failure takes effect:
- Engine: traction is zeroed.
- Brake: the service brake is blocked; the emergency brake still works.
- Signal pickup: the commanded speed and authority passed to the Train Controller are
  zeroed.

Failures are not reported to the Train Controller. This use case extends *Compute train
motion* and *Report state to Train Controller*."

#### Report state to Train Controller

**Lifelines:** central harness · state · model · Train Controller

1. central harness → state `step(dt, inputs)`
2. state → model `step(dt, inputs)`
3. model *(self)* `_build_outputs(inputs, block_changed)`
4. `alt [signal pickup failed]`
   1. model *(self)* `commanded_speed_mps = 0, authority_blocks = 0`

   `else`

   2. model *(self)* `pass commanded speed and authority through`

   `end`
5. model → state *(reply)* `TrainModelOutputs`
6. state → central harness *(reply)* `TrainModelOutputs`
7. central harness → Train Controller *(async)* `ControllerOutputs: actual speed, brake
   states, doors, lights, cabin temperature, commanded speed, authority, speed limit,
   beacon`

**Note:** "Brake states report what is engaged, not what was commanded. Active failures
are never sent."

#### Apply controller commands

**Lifelines:** Train Controller · central harness · state · model

1. Train Controller → central harness *(async)* `ControllerCommands`
2. central harness *(self)* `map to the Train Model's ControllerCommands`
3. central harness → state `step(dt, inputs)`
4. state → model `step(dt, inputs)`
5. model *(self)* `doors follow door_left_open, door_right_open`
6. model *(self)* `_integrate(): traction from power_cmd_w; service and emergency brakes`
7. model *(self)* `_update_cabin_temp(dt, temp_setpoint_c)`
8. model *(self)* `_build_outputs(): lights and brake states`
9. model → state *(reply)* `TrainModelOutputs`
10. state → central harness *(reply)* `TrainModelOutputs`

**Note:** "The announcement is kept with the step's inputs for the window (see *View
announcement*). The Train Model does not police commands: no speed governing, no
70 km/h cap, no traction cut under braking, no door interlock (D009)."

#### Receive track data

**Lifelines:** Track Model · central harness · state · model

1. Track Model → central harness *(async)* `TrackInfo, TrackSignal, Beacon [0..1],
   passengers_boarded`
2. central harness *(self)* `map to the Train Model's TrackInputs`
3. central harness → state `step(dt, inputs)`
4. state → model `step(dt, inputs)`
5. model *(self)* `validate_inputs(dt, inputs)`
6. model *(self)* `_update_passengers(…, passengers_boarded, …)`
7. model *(self)* `_detect_block_change(polarity)`
8. model *(self)* `_integrate(): grade_deg sets the grade force`
9. model *(self)* `_build_outputs(): speed limit, track signal and beacon pass through`
10. model → state *(reply)* `TrainModelOutputs`
11. state → central harness *(reply)* `TrainModelOutputs`

**Note:** "A beacon is present only near stations. Under a signal pickup failure, the
commanded speed and authority passed on are zeroed."

#### Report position to Track Model

**Lifelines:** central harness · state · model · Track Model

1. central harness → state `step(dt, inputs)`
2. state → model `step(dt, inputs)`
3. model *(self)* `_build_outputs(inputs, block_changed)`
4. model → state *(reply)* `TrainModelOutputs`
5. state → central harness *(reply)* `TrainModelOutputs`
6. central harness → Track Model *(async)* `TrackOutputs: block_id, offset_m,
   actual_speed_mps, block_changed, passenger_capacity`

**Note:** "`actual_speed_mps` is negative while the train rolls back. `block_changed` is
true only on the step where a polarity flip is seen."

### 5.2 Included use cases (the stages of every step)

None of these has an actor. Each begins with the step reaching `model`. Use these
lifelines: central harness · state · model.

#### Validate step inputs

1. central harness → state `step(dt, inputs)`
2. state → model `step(dt, inputs)`
3. model *(self)* `validate_inputs(dt, inputs)  «static»`
4. `alt [dt not finite, ≤ 0, or > 60 s]`
   1. model → state *(reply)* `raise InvalidTimeStepError`

   `else [an input is invalid]`

   2. model → state *(reply)* `raise InvalidInputError`

   `else [all valid]`

   3. model *(self)* `continue the step`

   `end`
5. `opt [raised]`
   1. state → central harness *(reply)* `exception propagates; nothing changed`

   `end`

**Note,** listing what is checked: "On/off inputs must be booleans. Numbers must be
finite. Power, speed limit, commanded speed, authority and the boarding count must not
be negative. Grade must be strictly between −90° and 90°. Authority and the boarding
count must be at most 2^31 − 1. A beacon's platform side must be L, R or LR, and its
station name at most 128 characters. Every check runs before any state changes."

#### Compute train motion

1. state → model `step(dt, inputs)`
2. model *(self)* `_integrate(dt, inputs, grade_rad)`
3. model *(self)* `_mass_kg()`
4. model *(self)* `_brake_n(service, emergency)`
5. `opt [brake failure]` model *(self)* `service brake blocked; emergency still applies`
   `end`
6. model *(self)* `grade force m·g·sin θ; rolling resistance 0.002·m·g·cos θ`
7. `alt [engine failure]`
   1. model *(self)* `traction = 0`

   `else`

   2. model *(self)* `power = min(power_cmd_w, 480 kW)`

   `end`
8. `loop [time left in dt]`
   1. model *(self)* `_traction_n(power, v): P/|v|, capped at 25,717 N`
   2. model *(self)* `trapezoidal substep of velocity and offset`
   3. `opt [velocity reaches 0]` model *(self)* `stop there; hold or roll back` `end`

   `end`
9. model *(self)* `set velocity, acceleration, offset`

**Note:** "Brakes and rolling resistance oppose motion and hold the train at rest; they
never reverse it. Rollback is allowed, and the motors push forward against it. No speed
cap (D009)."

#### Update passengers

1. state → model `step(dt, inputs)`
2. model *(self)* `_update_passengers(door_left, door_right, boarded, stopped)`
3. `opt [stopped and a door open and no draw yet this stop]`
   1. model *(self)* `n_passengers −= random 0..n_passengers`
   2. model *(self)* `_stop_drawn = True`

   `end`
4. `opt [stopped and a door open]`
   1. model *(self)* `n_passengers += min(boarded, 222 − n_passengers)`

   `end`

**Note:** "The draw uses the random generator seeded by `TrainConfig.seed`."

#### Detect block change

1. state → model `step(dt, inputs)`
2. model *(self)* `_detect_block_change(polarity)`
3. `alt [a previous polarity exists and differs]`
   1. model *(self)* `block_changed = true; offset_m = 0`

   `else`

   2. model *(self)* `block_changed = false`

   `end`
4. model *(self)* `_last_polarity = polarity`

**Note:** "The first step has no previous polarity, so it never reports a change."

#### Update cabin temperature

1. state → model `step(dt, inputs)`
2. model *(self)* `_update_cabin_temp(dt, temp_setpoint_c)`
3. model *(self)* `decay = exp(−dt / 300)`
4. model *(self)* `cabin_temp_c = setpoint + (cabin_temp_c − setpoint) × decay`

**Note:** "The cabin starts at 20 °C and approaches the setpoint exponentially, at a
rate of 1/300 per second."

#### Publish outputs

1. state → model `step(dt, inputs)`
2. model *(self)* `_add_elapsed(dt)`
3. model *(self)* `_build_outputs(inputs, block_changed)`
4. model *(self)* `brake states from what is engaged`
5. `alt [signal pickup failed]`
   1. model *(self)* `commanded speed 0, authority 0`

   `else`

   2. model *(self)* `pass them through`

   `end`
6. model *(self)* `ControllerOutputs + TrackOutputs → TrainModelOutputs`
7. model → state *(reply)* `TrainModelOutputs`
8. state *(self)* `_refresh()`
9. state → central harness *(reply)* `TrainModelOutputs`

**Note:** "`outputs()` returns these until the next step. They feed *Report state to
Train Controller* and *Report position to Track Model*."

## 6. Check your work before reporting

1. **Pages.** The file has exactly 15 new pages, named as in section 1, in the order of
   section 5, and every existing page is unchanged.
2. **XML.** The XML is well-formed. Every new `id` is unique, and every `parent`,
   `source` and `target` points at an existing cell.
3. **Look at each new page.** Export each to PNG with the draw.io CLI if it's already
   installed; don't install anything to get it. If it isn't available, render the cells
   with a small script. Then check:
   - Every message is horizontal and in order.
   - No label is wider than its arrow, and no label overlaps another label.
   - Fragments nest without sharing edges.
   - Nothing spills outside the `sd` frame.
4. **Fix the layout, not the content.** If a label doesn't fit, widen the lifeline
   spacing. Don't shorten a label without reporting it.

**Report back:** the pages you added, whether they exported, and any place you
departed from this prompt.
