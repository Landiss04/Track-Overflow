# train-model

**Status:** current
**Owner:** Kevin Schillinger
**Provenance:** ownership asserted by Kevin Schillinger 2026-09-30; `Train_Model_Backend_Design.pdf` §1, §5.1 to §5.95 (Locked) and Constants table; Train Model `interface.py` boundary contract as amended by Kevin 2026-09-30; brake failure disabling both brakes asserted by Kevin Schillinger 2026-09-30; separate Train Model and test UI processes, and failure injection from the test UI, asserted by Kevin Schillinger 2026-10-01 (D010)
**Aliases:** Train Model, train model module
**Last updated:** 2026-10-01

## Purpose

A simulated physical model of one train: its longitudinal dynamics on graded track, its
passengers, and its onboard systems. It turns Train Controller commands and Track Model
data into the train's motion and reported state.

## Protocol methods

- `step(dt, inputs) -> outputs`: advance one tick. dt is fixed; see D006.
- `snapshot() -> snapshot`: the full observable state, for the Train Model UI. It has
  no side effects.
- `set_failures(failures)`: Murphy's fault injection, from the Train Model UI or, as a
  test-only command, the test UI.
- `pull_passenger_emergency_brake()`: a passenger pull, from the Train Model UI.

The last two are UI actions, not cross-module inputs.

## User interfaces

- The Train Model UI and the test UI are independent windows, each its own process.
  The test UI drives the module only through its interface and is removed at
  integration (D010).

## Owns

- The train's physical state: operating mass, acceleration, velocity (signed), and
  position.
- The passenger count and the disembark draw.
- The passenger emergency brake (`arbitration/passenger-emergency-brake.md`).
- Signals it produces: `actual-speed`, `train-position`, `block-change-event`,
  `passenger-capacity`, `brake-state`, `door-state`, `light-state`,
  `cabin-temperature`, and `failure-status`. It also passes through `track-signal`,
  `beacon`, and the speed limit from `track-info` to the Train Controller.

## Consumes

- From the Train Controller: `power-command`, `service-brake-command`,
  `emergency-brake-command`, `light-command`, `door-command`, `temperature-setpoint`,
  and `announcement`.
- From the Track Model: `track-info` (every tick), `track-signal`, `beacon`, and
  `passengers-boarded`.

## Enforced parameters

Vehicle: a Bombardier FLEXITY 2 (Blackpool), fixed 5-module consist. The consist is not
configurable.

| Parameter | Value | Source |
|---|---|---|
| Length, width, height | 32.2 m, 2.65 m, 3.42 m | Datasheet |
| Empty mass | 40,900 kg | Datasheet |
| Crew | 5 (1 per car); counts toward mass | Design §5.2 |
| Passenger capacity | 222 (74 seated + 148 standing) | Datasheet |
| Mass per person | 77.1107 kg (170 lb) | Customer Q&A |
| Maximum power | 480,000 W (4 × 120 kW) | Provisional, pending instructor |
| Maximum speed | 19.444 m/s (70 km/h) | Datasheet |
| Rated acceleration | 0.5 m/s² at 2/3 load | Datasheet |
| Service deceleration | 1.2 m/s² at 2/3 load | Datasheet |
| Emergency deceleration | 2.73 m/s² at 2/3 load | Datasheet |
| Rolling resistance C_rr | 0.002 | Assumed textbook value |
| g | 9.81 m/s² | |

- Derived values (reference mass, traction and brake forces) are computed from these
  primitives, not entered by hand.
- The reference mass is empty mass plus 2/3 of capacity in passengers, with no crew.
  Brake and traction forces are derived from it.
- Operating mass is empty mass plus crew and passengers times mass per person. It is
  recomputed on every boarding event.
- Traction is P/v saturated at the traction limit, and the motors drive forward only.
  Integration is trapezoidal for both velocity and position; closed-form kinematics are
  not used.
- Rollback is allowed. Brakes and rolling resistance oppose motion and act as a static
  holding force at rest. They stop the train but never reverse it.
- Station dwell is 45 s (D007).

## Failure modes

- Three independent failures, all injected by Murphy from the Train Model UI or the
  test UI: engine, signal pickup, and brake. Any combination is valid.
- Engine failure zeroes traction. Signal pickup failure affects the Track Signal only.
  Brake failure disables both the service and the emergency brake, including a
  passenger pull.
- Active failures are reported in `failure-status`.

## Does not own

- Lighting logic: dusk/dawn and tunnel lighting belong to the Train Controller
  (`light-command`).
- Suggested speed, which goes from the CTC Office to the Track Controller and never
  reaches the train.
- Track circuit polarity and grade, which the Track Model supplies.
- Throughput accounting. Disembark counts are not reported; the Track Model and the CTC
  Office handle throughput.

## Supersedes

- UI layout: previously one window with buttons switching between the Train Model
  and test views; now two independent processes (D010, 2026-10-01).
- Previously a placeholder that asserted nothing, with owner unassigned. Now populated
  from the backend design with Kevin Schillinger as owner (2026-09-30). The placeholder
  listed a "tunnel light controller" under this module; tunnel lighting belongs to the
  Train Controller (design §5.5).
