# Train Model physics

The retained numerical algorithm in `train_model/model.py` and the accepted
October 20, 2026 design from [SDD v0.2](../../documents/Railway_Sim_SDD_Train_Model.md).
Implementation descriptions below reflect the current working tree, including
concurrent backend changes inspected during this documentation review. Numbers are for the default `TrainConfig` (Bombardier
FLEXITY 2, Blackpool, 5-module consist). Everything is SI internally; the
only boundary units that are not SI base units are grade (degrees) and
temperature (°C).

Contents: [constants](#1-constants) · [masses](#2-masses) ·
[forces](#3-forces) · [brakes](#4-brakes) · [integration](#5-integration) ·
[stops, holding and rollback](#6-stops-holding-and-rollback) ·
[order of one step](#7-order-of-one-step) · [doors](#8-doors) ·
[passengers](#9-passengers) · [position and blocks](#10-position-and-block-changes) ·
[cabin temperature](#11-cabin-temperature) · [failures](#12-failures) ·
[outputs](#13-outputs) · [validation](#14-input-validation) ·
[reference figures](#15-reference-figures) · [not modelled](#16-not-modelled) ·
[relation to truth](#17-relation-to-the-truth-branch)

## 1. Constants

`TrainConfig` holds primitives; derived values are properties, so changing a
primitive keeps everything consistent.

| Primitive | Value | Source |
|---|---|---|
| `m_empty_kg` | 40,900 kg | Datasheet |
| `m_loaded_kg` | 56,700 kg (4 pass./m²) | Datasheet |
| `capacity` | 222 (74 seated + 148 standing) | Datasheet |
| `passenger_mass_kg` | 77.1107 kg (170 lb) | Customer Q&A |
| `n_crew` | 5 | Design §5.2 |
| `p_max_w` | 480,000 W (4 × 120 kW) | Confirmed by Kevin Schillinger, 2026-10-20 |
| `v_max_mps` | 19.444 m/s (70 km/h) | Datasheet; **not enforced** |
| `ref_load_fraction` | 2/3 | Datasheet test condition |
| `accel_ref_mps2` | 0.5 m/s² | Datasheet, at 2/3 load |
| `decel_service_mps2` | 1.2 m/s² | Datasheet, at 2/3 load |
| `decel_emergency_mps2` | 2.73 m/s² | Datasheet, at 2/3 load |
| `c_rr` | 0.002 | Existing configured coefficient; retained scope |
| `g_mps2` | 9.81 m/s² | |
| `seed` | 0 | Disembark random generator |

| Derived | Formula | Value |
|---|---|---|
| `m_ref_kg` | m_empty + ⅔ × (m_loaded − m_empty) | 51,433 kg |
| `f_max_n` | m_ref × 0.5 | 25,717 N |
| `f_service_n` | m_ref × 1.2 | 61,720 N |
| `f_emergency_n` | m_ref × 2.73 | 140,413 N |

## 2. Masses

- **Reference mass** `m_ref` is fixed and used only to size the three forces
  above, so the datasheet rates hold at ⅔ load.
- **Operating mass** is the *m* in every force balance:

  m = m_empty + (n_crew + n_passengers) × passenger_mass

  It runs from 41,286 kg (crew only) to 58,404 kg (full) and changes only when
  passengers board or alight (section 9). Because forces are fixed and mass is
  not, an empty train accelerates and brakes harder than a full one.

## 3. Forces

Sign convention: positive is the train's forward direction; a positive grade
is uphill in that direction. θ = radians(`grade_deg`).

| Force | Value | Acts |
|---|---|---|
| Traction F_t | see below | forward only |
| Grade F_g | m·g·sin θ | down the slope (opposes forward motion uphill) |
| Rolling resistance F_r | c_rr·m·g·cos θ | against motion; static at rest |
| Brake F_b | Sum of the configured forces of engaged brakes (accepted design; section 4) | against motion; static at rest |

**Traction.** Effective power P = min(`power_cmd_w`, `p_max_w`), and P = 0
under an engine failure. Then

- moving forward (v > 0): F_t = min(P / v, F_max);
- at rest (v = 0): F_t = F_max if P > 0, else 0 (P/v saturates);
- rolling backward (v < 0): F_t = min(P / |v|, F_max), still forward. The
  motors drive forward only, so under power they push against a rollback:
  they slow it and, where they can, stop it and drive the train forward.

The speed where the two limits meet is the **base speed**
v_b = P / F_max: at full power 18.66 m/s (67.2 km/h). Below v_b in speed
(either direction) traction is force-limited (constant F_max); above it,
power-limited (P/|v|).

Traction is **not** cut while a brake is applied: commanded power still
acts. Cutting power when braking is the Train Controller's decision
(`arbitration/traction-cut-under-braking.md` on `truth`).

## 4. Brakes

The accepted states are independent:

- **Emergency** engages for the controller command or the passenger latch.
- **Service** engages for its command unless service brake failure is active.
- Both may be active. Their configured forces sum:
  `F_b = service_active * f_service_n + emergency_active * f_emergency_n`.

Force summation is the realization selected in response to Kevin’s review and
recorded in SDD v0.2. In the inspected working tree, `_brakes_engaged` reports
independent states and `_brake_n` sums the engaged configured forces. These
concurrent backend edits were not made by this documentation task.

The passenger pull latches until the controller's emergency brake goes from
true to false (Kevin Schillinger 2026-10-28). A pull made after the
controller's last true is kept. The window has no release action. A separate test-only clear hook remains for
the developer utility.

## 5. Integration

Commands and track inputs are **held constant for the whole tick** of length
dt. The external dt stays fixed throughout the run; speed and pause change only
tick frequency. Each tick is integrated in internal segments/substeps whose
durations sum to dt. Stops and traction-regime transitions need internal
boundaries for accurate event handling; stability limits split segments further.

Within a substep the net force on a moving train is

  F = F_t − F_g − sign(v) · (F_b + F_r)

and the substep is solved according to the regime:

1. **No traction** (P = 0): all forces are constant, so the update is
   exact: v' = v + a·h, x' = x + h·(v + v')/2.
2. **Force-limited forward motion** (0 ≤ v < v_b): traction is the constant F_max, so the
   update is exact as above. If the train would pass v_b inside the substep,
   the substep ends exactly at v_b and the rest of the tick continues
   power-limited.
3. **Power-limited** (v ≥ v_b): traction is evaluated at the **midpoint
   velocity** v_m = (v + v')/2, giving
   m·(v' − v) = h·(P / v_m − R) with R = F_g + F_b + F_r. This is a quadratic
   in v', solved in closed form. Its key property: the traction work in the
   substep, (P / v_m)·(h·v_m), is exactly P·h, so traction never delivers
   more energy than was commanded or creates artificial energy gain. If the train slows through v_b inside the
   substep, the substep ends at v_b and continues force-limited.

Substep length is capped at the traction relaxation time m·s²/P, with
s = max(v, v_b), which keeps the midpoint solution stable. At floating-point
equilibrium (P/v = R) the rest of the tick is covered at constant speed.

**Rolling back under power** is solved the same way in the backward speed
w = −v, with R = F_g − F_b − F_r the net force driving the rollback:
force-limited below v_b (constant F_max against the rollback, exact), and
power-limited above it, where m·(w − w') = h·(P / w_m − R) with
w_m = (w + w')/2. Again the traction work in the substep is exactly P·h, now
taken out of the rollback. The substep is capped at m·s²/(8P), and at
m·w/|R| when R < 0, which keeps the quadratic's roots real; it ends at v_b
when the rollback slows through it. The balance P/w = R is unstable: a
slower rollback is stopped, a faster one keeps accelerating.

For numerical verification, halving the external dt cuts second-order error
about fourfold; production uses the same fixed dt throughout a run. At
dt = 0.1 s a 60 s full-power launch matches the closed-form solution to about
4e-9 in speed and 2e-7 in position (relative). Constant-force phases are exact.

**Reported acceleration** is the instantaneous value at the end-of-tick
velocity, from the same force balance: (F_t(v) − F_g − sign(v)(F_b + F_r))/m,
or the static rule of section 6 at v = 0.

## 6. Stops, holding and rollback

- **Stop event.** If a substep would carry v through zero, the substep is
  shortened to the exact stopping time (constant deceleration over the
  stopping interval) and v is set to exactly 0. Distance on that substep is
  h·v/2 ≥ 0, so a forward-braking train never moves backward.
- **At rest**, brakes and rolling resistance act as a static holding force
  H = F_b + F_r. With drive D = F_t(0) − F_g:
  - |D| ≤ H: the train stays at rest for the rest of the tick, acceleration 0;
  - |D| > H: it starts moving in the direction of D with
    a = (D − sign(D)·H)/m.
- **Rollback** is allowed. An unbraked train on a grade steeper than
  rolling resistance can hold rolls downhill, with negative speed and offset.
  Gravity can stop a train and reverse it within the same tick.
- **Power against a rollback.** Commanded power pushes forward while the
  train rolls back (section 3). Where F_max exceeds the grade force less
  rolling resistance it stops the rollback, and where F_max also exceeds the
  grade force plus rolling resistance the train then drives forward; in
  between it holds at rest. On a steeper grade it only slows the rollback.
- Brakes and rolling resistance stop a train but never reverse it.

## 7. Order of one step

`step(dt, inputs)` does, in order:

1. Validate dt and inputs (section 14). On rejection, nothing changes.
2. Clear the passenger latch if the controller's emergency brake was true on
   the last tick with the pull latched and is false now. Then update
   doors and passengers, from the speed at the **start** of the tick
   (sections 8 and 9).
3. Block change: if polarity differs from the previous tick, offset resets
   to 0 (section 10).
4. Integrate motion over dt (sections 5 and 6).
5. If the train is now moving, the stop ends, so the next stop draws its
   own disembark (section 9). The doors are left as commanded: the
   Train Controller owns the interlock (section 8).
6. Update cabin temperature (section 11).
7. Store the inputs, add dt to elapsed time (compensated summation, so the
   sum stays within an ulp of exact over any run), and build the outputs
   (section 13).

## 8. Doors

Each door follows its command: door_open = command_open, whatever the speed.

The Train Controller ensures doors remain closed when required. The Train
Model follows commands and reports matching Door State; it enforces no speed
interlock. Historical disabled interlock code is not an unresolved ownership
question. Rest remains a separate Train Model boarding condition.

## 9. Passengers

Evaluated before motion, from the door states and the speed at the start of
the tick:

1. **Disembark.** Once per stop, on the first tick at rest with a door open
   (either side, including one opened before the train stopped), a uniform
   random integer from 0 to the number aboard alights. A stop need not be at
   a station: with a door open, passengers can get off (Kevin, 2026-10-07). Opening the other door, or closing and
   reopening one, draws nobody more; the next stop begins once the train
   has moved. The generator is `random.Random(config.seed)`, one per train, so
   runs are reproducible.
2. **Board.** The Track Model sends boarding events only at stations. The
   Train Model checks **rest**, an open door, count bounds and capacity; it
   applies no station-presence gate (Kevin’s October 20 review):
   aboard += max(0, min(passengers_boarded, capacity − aboard)).
   A count received at any other time boards nobody and is not kept.

Operating mass (section 2) follows the new count immediately.
`passenger_capacity` in the outputs is capacity − aboard, after the draw.

## 10. Position and block changes

- `offset_m` integrates distance travelled since the last block change, for
  the front of the train. It is signed: it goes negative in rollback.
- A block change is detected when `TrackInfo.polarity` differs from the
  previous tick's. The first tick has no previous polarity, so it is never a
  change. On a change the offset resets to 0 before that tick's motion is
  added, and `block_changed` is true on that tick only.
- The block ID is passed through from `TrackInfo.block_id`.

## 11. Cabin temperature

A first-order lag toward the setpoint with time constant 300 s, starting at
20 °C, integrated exactly:

  T' = T_set + (T − T_set)·exp(−dt / 300)

It never overshoots and gives the same result for any dt.

## 12. Failures

Three independent flags, set with `set_failures`. Any combination is valid.
Each shows at once on the Train Model UI; its physical effect starts on the
next step. Failure status is not sent to the Train Controller.

| Failure | Effect |
|---|---|
| Engine | Traction is 0 (P treated as 0). |
| Signal pickup | Commanded speed and authority are both reported as 0. Track Info (block, grade, speed limit) is unaffected. |
| Brake | The service brake is blocked. The emergency brake, commanded or pulled, still works. |

## 13. Outputs

To the **Train Controller** (`ControllerOutputs`): actual speed; Brake State
as engaged emergency and service (section 4, not the commands); door and
light states; cabin temperature; commanded speed, authority, speed limit and
beacon, passed through (beacon only on the tick it is received). Failure
status is not an output.

To the **Track Model** (`TrackOutputs`): block ID, offset, actual speed
(negative in rollback), block-change flag, remaining passenger capacity.

`set_failures`, `pull_passenger_emergency_brake` and
`clear_passenger_brake_for_test` rebuild these outputs immediately, without
advancing time.

## 14. Input validation

Before any state changes, `step` rejects:

- dt that is not finite, not positive, or longer than 60 s
  (`InvalidTimeStepError`); the clock ticks 0.1 s;
- an on/off input (brake, light and door commands, polarity, beacon
  underground) that is not a `bool` (`InvalidInputError`);
- any numeric input that is not a finite number: power, setpoint, grade,
  elevation, speed limit, commanded speed, boarding count. A `bool`, text,
  or an integer too large for a float counts as not one
  (`InvalidInputError`);
- a block ID, station name, announcement or beacon station name that is not
  text, a beacon platform side other than `L`, `R` or `LR`, or a beacon
  payload exceeding 128 characters in its complete canonical ASCII JSON
  encoding (`InvalidInputError`). The inspected `utils/beacon_codec.py`
  includes syntax and escapes; see [encoding](module-interface.md#beacon-payload-encoding);
- negative power (`InvalidInputError`);
- a grade not strictly between −90° and 90°, a negative speed limit or a
  negative commanded speed: values with no physical meaning
  (`InvalidInputError`);
- a boarding count that is not an `int` (a `bool` is not), is negative or
  exceeds 2³¹ − 1 (`InvalidInputError`);
- an authority that is not an `int` (a `bool` is not), is negative or
  exceeds 2³¹ − 1 (`InvalidInputError`).

A rejected step leaves the model exactly as it was, including the random
generator. `validate_inputs` is static, so a caller can check a step without
the model.

## 15. Reference figures

Default configuration, flat track unless stated. Each brake column describes
that brake alone; the accepted simultaneous-brake design sums both forces.

| | Crew only (41,286 kg) | Full (58,404 kg) |
|---|---|---|
| Launch acceleration (F_max − F_r)/m | 0.603 m/s² | 0.421 m/s² |
| Steepest grade full power can start on | 6.16 % | 4.29 % |
| Steepest grade the service brake holds | 15.6 % | 11.0 % |
| Steepest grade the emergency brake holds | 37.2 % | 25.5 % |
| Service deceleration incl. rolling | 1.515 m/s² | 1.076 m/s² |
| Emergency deceleration incl. rolling | 3.421 m/s² | 2.424 m/s² |
| Service stop from 70 km/h, d = v²/2a | 124.8 m | 175.6 m |
| Emergency stop from 70 km/h | 55.3 m | 78.0 m |
| Coasting deceleration (c_rr·g) | 0.0196 m/s² | 0.0196 m/s² |

## 16. Not modelled

- Speed governing: `v_max_mps` is not enforced; speed regulation belongs to
  the Train Controller (D009). With no aerodynamic drag, sustained full power
  on flat track would approach P / F_r (hundreds of m/s).
- Rolling resistance with the existing coefficient is the only passive
  resistance term in scope. Grade remains gravitational force and braking
  commanded force. Aerodynamic drag, curve resistance, wheel slip, jerk
  limits and brake build-up are outside this model, not prerequisites.
  No real-world calibration study is claimed.
- Load-weighed brakes: brake force does not scale with load.
- Traction cut on braking (Train Controller's decision).
- Electrical power, losses and regeneration (see
  [open-issues.md](open-issues.md)).

## 17. Relation to the truth branch

The fetched truth branch remains authoritative until human promotion. New
full-entry proposals in `truth/_inbox/claude/quirky-fermi-sickg4/` capture Kevin’s
October 20 review: corrected D006, independent brakes and force summation,
boarding ownership, complete beacon encoding, pickup zeros, front offset,
confirmed power and scope, and integrated display/clock rules. These proposals
are not promoted facts. Implementation gaps belong in
[open issues](open-issues.md), not in the truth store.
