# Train Model physics

What `train_model/model.py` computes, exactly, on every call to
`step(dt, inputs)`. Numbers are for the default `TrainConfig` (Bombardier
FLEXITY 2, Blackpool, 5-module consist). Everything is SI internally; the
only boundary units that are not SI base units are grade (degrees) and
temperature (°C).

Contents: [constants](#1-constants) · [masses](#2-masses) ·
[forces](#3-forces) · [brakes](#4-brakes) · [integration](#5-integration) ·
[stops, holding and rollback](#6-stops-holding-and-rollback) ·
[order of one step](#7-order-of-one-step) · [doors](#8-doors-and-the-interlock) ·
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
| `p_max_w` | 480,000 W (4 × 120 kW) | Provisional |
| `v_max_mps` | 19.444 m/s (70 km/h) | Datasheet; **not enforced** |
| `ref_load_fraction` | 2/3 | Datasheet test condition |
| `accel_ref_mps2` | 0.5 m/s² | Datasheet, at 2/3 load |
| `decel_service_mps2` | 1.2 m/s² | Datasheet, at 2/3 load |
| `decel_emergency_mps2` | 2.73 m/s² | Datasheet, at 2/3 load |
| `c_rr` | 0.002 | Assumed |
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
| Brake F_b | 0, `f_service_n` or `f_emergency_n` (section 4) | against motion; static at rest |

**Traction.** Effective power P = min(`power_cmd_w`, `p_max_w`), and P = 0
under an engine failure. Then

- moving forward (v > 0): F_t = min(P / v, F_max);
- at rest (v = 0): F_t = F_max if P > 0, else 0 (P/v saturates);
- rolling backward (v < 0): F_t = 0. The motors drive forward only.

The speed where the two limits meet is the **base speed**
v_b = P / F_max: at full power 18.66 m/s (67.2 km/h). Below v_b traction is
force-limited (constant F_max); above it, power-limited (P/v).

Traction is **not** cut while a brake is applied: commanded power still
acts. Cutting power when braking is the Train Controller's decision.

## 4. Brakes

Which brakes are engaged comes from one function, `_brakes_engaged`, used for
both the force and the reported Brake State:

- **Emergency** is engaged if the Train Controller commands it **or** the
  passenger emergency brake is pulled.
- **Service** is engaged if commanded, **and** the emergency brake is not
  engaged, **and** there is no brake failure.

So the emergency brake supersedes the service brake (forces never add), and a
brake failure blocks the service brake only. The brake force is
`f_emergency_n` if emergency is engaged, else `f_service_n` if service is
engaged, else 0.

The passenger pull latches. It stays engaged until cleared; only the test-only
`clear_passenger_brake_for_test` clears it today (see
[integration.md](integration.md#passenger-brake-release)).

## 5. Integration

Commands and track inputs are **held constant for the whole tick** of length
dt. The tick is integrated in one or more internal substeps; the harness
still sees exactly one step of dt.

Within a substep the net force on a moving train is

  F = F_t − F_g − sign(v) · (F_b + F_r)

and the substep is solved according to the regime:

1. **No traction** (P = 0, or v < 0): all forces are constant, so the update
   is exact: v' = v + a·h, x' = x + h·(v + v')/2.
2. **Force-limited** (0 ≤ v < v_b): traction is the constant F_max, so the
   update is exact as above. If the train would pass v_b inside the substep,
   the substep ends exactly at v_b and the rest of the tick continues
   power-limited.
3. **Power-limited** (v ≥ v_b): traction is evaluated at the **midpoint
   velocity** v_m = (v + v')/2, giving
   m·(v' − v) = h·(P / v_m − R) with R = F_g + F_b + F_r. This is a quadratic
   in v', solved in closed form. Its key property: the traction work in the
   substep, (P / v_m)·(h·v_m), is exactly P·h, so traction never delivers
   more energy than was commanded. If the train slows through v_b inside the
   substep, the substep ends at v_b and continues force-limited.

Substep length is capped at the traction relaxation time m·s²/P, with
s = max(v, v_b), which keeps the midpoint solution stable. At floating-point
equilibrium (P/v = R) the rest of the tick is covered at constant speed.

The scheme is second-order: halving dt cuts the error about fourfold. At
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
- Brakes and rolling resistance stop a train but never reverse it.

## 7. Order of one step

`step(dt, inputs)` does, in order:

1. Validate dt and inputs (section 14). On rejection, nothing changes.
2. Door interlock and passengers, from the speed at the **start** of the tick
   (sections 8 and 9).
3. Block change: if polarity differs from the previous tick, offset resets
   to 0 (section 10).
4. Integrate motion over dt (sections 5 and 6).
5. If the train is now moving, force both doors closed.
6. Update cabin temperature (section 11).
7. Store the inputs, add dt to elapsed time, and build the outputs
   (section 13).

## 8. Doors and the interlock

A door can only open at 0 mph. For each side,
door_open = command_open AND (speed at the start of the tick = 0).

- An open command while moving is refused; if it is held, the door opens on
  the first tick that starts at rest.
- An open door closes as soon as the train moves (step 5 above), so a door is
  never reported open at nonzero speed.
- A close command closes the door immediately.

Door State reports these actual doors, which can differ from Door Command.

## 9. Passengers

Evaluated before motion, using the interlocked door states:

1. **Disembark.** On a door-open rising edge (either side goes from closed to
   open) at rest, a uniform random integer from 0 to the number aboard
   alights. The generator is `random.Random(config.seed)`, one per train, so
   runs are reproducible.
2. **Board.** Only if the train is **at a station** (`TrackInfo.station_name`
   is a non-empty string) **and** a door is open:
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
Each is reported at once in Failure Status; its physical effect starts on
the next step.

| Failure | Effect |
|---|---|
| Engine | Traction is 0 (P treated as 0). |
| Signal pickup | Commanded speed and authority are both reported as 0. Track Info (block, grade, speed limit) is unaffected. |
| Brake | The service brake is blocked. The emergency brake, commanded or pulled, still works. |

## 13. Outputs

To the **Train Controller** (`ControllerOutputs`): actual speed; Brake State
as engaged emergency and service (section 4, not the commands); door and
light states; cabin temperature; commanded speed, authority, speed limit and
beacon, passed through (beacon only on the tick it is received); Failure
Status.

To the **Track Model** (`TrackOutputs`): block ID, offset, actual speed
(negative in rollback), block-change flag, remaining passenger capacity.

`set_failures`, `pull_passenger_emergency_brake` and
`clear_passenger_brake_for_test` rebuild these outputs immediately, without
advancing time.

## 14. Input validation

Before any state changes, `step` rejects:

- dt that is not finite or not positive (`InvalidTimeStepError`);
- any non-finite numeric input: power, setpoint, grade, elevation, speed
  limit, commanded speed, boarding count (`InvalidInputError`);
- negative power (`InvalidInputError`);
- a boarding count that is not an `int` (`InvalidInputError`);
- an authority that is not an `int` or is negative (`InvalidInputError`).

A rejected step leaves the model exactly as it was, including the random
generator. `validate_inputs` is static, so a caller can check a step without
the model.

## 15. Reference figures

Default configuration, flat track unless stated.

| | Crew only (41,286 kg) | Full (58,404 kg) |
|---|---|---|
| Launch acceleration (F_max − F_r)/m | 0.603 m/s² | 0.421 m/s² |
| Steepest grade full power can start on | 6.16 % | 4.29 % |
| Steepest grade the service brake holds | 15.4 % | 10.8 % |
| Steepest grade the emergency brake holds | 37.0 % | 25.3 % |
| Service deceleration incl. rolling | 1.515 m/s² | 1.076 m/s² |
| Emergency deceleration incl. rolling | 3.421 m/s² | 2.424 m/s² |
| Service stop from 70 km/h, d = v²/2a | 124.8 m | 175.6 m |
| Emergency stop from 70 km/h | 55.3 m | 78.0 m |
| Coasting deceleration (c_rr·g) | 0.0196 m/s² | 0.0196 m/s² |

## 16. Not modelled

- Speed governing: `v_max_mps` is not enforced; speed regulation belongs to
  the Train Controller (D009). With no aerodynamic drag, sustained full power
  on flat track would approach P / F_r (hundreds of m/s).
- Aerodynamic drag, curve resistance, wheel slip, jerk limits and brake
  build-up time.
- Load-weighed brakes: brake force does not scale with load.
- Traction cut on braking (Train Controller's decision).
- Traction while rolling backward.
- Electrical power, losses and regeneration (see
  [open-issues.md](open-issues.md)).

## 17. Relation to the truth branch

Two statements on `truth` describe the integration differently from this
code and should be reconciled by their owner:

- `decisions/D006-fixed-time-step.md` and `modules/train-model.md` say
  integration is trapezoidal and that the Train Model does not sub-step. The
  code holds dt fixed, as D006 requires, but integrates each tick in internal
  substeps (exact for constant forces, midpoint for power-limited traction).
- At the time of writing, the brake-failure scope (service only) and the
  51,433 kg reference mass are inbox proposals awaiting promotion; the
  promoted entries still say brake failure disables both brakes.
