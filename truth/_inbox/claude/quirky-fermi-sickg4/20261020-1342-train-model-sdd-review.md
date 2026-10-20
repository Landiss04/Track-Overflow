**Target:** truth/modules/train-model.md
**Action:** replace
**Proposed by:** Codex on claude/quirky-fermi-sickg4
**Provenance:** ownership asserted by Kevin Schillinger 2026-09-30; `Train_Model_Backend_Design.pdf` §1, §5.1 to §5.95 (Locked) and Constants table; Train Model `interface.py` boundary contract as amended by Kevin 2026-09-30; separate Train Model and test UI processes asserted by Kevin Schillinger 2026-10-01 (D010); brake failure blocking only the service brake, brake forces of 61,720 N and 140,413 N from a 51,433 kg reference load, and maximum speed not enforced by the Train Model, clarified by the course instructor and relayed by Kevin Schillinger 2026-10-02; reference mass of 51,433 kg as 2/3 of the datasheet load (empty 40.9 t, loaded 56.7 t at 4 pass./m²), used for traction as well as braking, asserted by Kevin Schillinger 2026-10-02; failure status no longer sent to the Train Controller, asserted by Kevin Schillinger 2026-10-05; the current Train Model UI and test UI superseding the wireframes, asserted by Kevin Schillinger 2026-10-05; failure injection from the Train Model UI only, the test UI's failure controls removed as redundant, asserted by Kevin Schillinger 2026-10-05; traction while rolling back, the Power command readout, and rejecting track inputs with no physical meaning, asserted by Kevin Schillinger 2026-10-06; rejecting a negative boarding count, asserted by Kevin Schillinger 2026-10-06; one disembark draw per stop, and counts bounded to 2³¹ − 1, asserted by Kevin Schillinger 2026-10-06; a 60 s ceiling on dt and on/off inputs that must be booleans, accepted by Kevin Schillinger 2026-10-06; the door interlock not the Train Model's, pending the course instructor, the announcement popup and the red active-failure button, a Train Model exception to the style guide, asserted by Kevin Schillinger 2026-10-06; per-train rejection in a fleet proposed in the design doc's per-module questions and accepted by Kevin Schillinger 2026-10-20 ("good"), and the passenger-brake-release command ("add"), 2026-10-20; Kevin Schillinger’s October 20, 2026 SDD review; documents/Railway_Sim_SDD_Train_Model.md v0.2 §4.9; direct documentation request 2026-10-20

---

# train-model

**Status:** current
**Owner:** Kevin Schillinger
**Provenance:** ownership asserted by Kevin Schillinger 2026-09-30; `Train_Model_Backend_Design.pdf` §1, §5.1 to §5.95 (Locked) and Constants table; Train Model `interface.py` boundary contract as amended by Kevin 2026-09-30; separate Train Model and test UI processes asserted by Kevin Schillinger 2026-10-01 (D010); brake failure blocking only the service brake, brake forces of 61,720 N and 140,413 N from a 51,433 kg reference load, and maximum speed not enforced by the Train Model, clarified by the course instructor and relayed by Kevin Schillinger 2026-10-02; reference mass of 51,433 kg as 2/3 of the datasheet load (empty 40.9 t, loaded 56.7 t at 4 pass./m²), used for traction as well as braking, asserted by Kevin Schillinger 2026-10-02; failure status no longer sent to the Train Controller, asserted by Kevin Schillinger 2026-10-05; the current Train Model UI and test UI superseding the wireframes, asserted by Kevin Schillinger 2026-10-05; failure injection from the Train Model UI only, the test UI's failure controls removed as redundant, asserted by Kevin Schillinger 2026-10-05; traction while rolling back, the Power command readout, and rejecting track inputs with no physical meaning, asserted by Kevin Schillinger 2026-10-06; rejecting a negative boarding count, asserted by Kevin Schillinger 2026-10-06; one disembark draw per stop, and counts bounded to 2³¹ − 1, asserted by Kevin Schillinger 2026-10-06; a 60 s ceiling on dt and on/off inputs that must be booleans, accepted by Kevin Schillinger 2026-10-06; the door interlock not the Train Model's, pending the course instructor, the announcement popup and the red active-failure button, a Train Model exception to the style guide, asserted by Kevin Schillinger 2026-10-06; per-train rejection in a fleet proposed in the design doc's per-module questions and accepted by Kevin Schillinger 2026-10-20 ("good"), and the passenger-brake-release command ("add"), 2026-10-20; Kevin Schillinger’s October 20, 2026 SDD review; documents/Railway_Sim_SDD_Train_Model.md v0.2 §4.9; direct documentation request 2026-10-20
**Aliases:** Train Model, train model module
**Last updated:** 2026-10-20

## Purpose

A simulated physical model of one train: its longitudinal dynamics on graded track, its
passengers, and its onboard systems. It turns Train Controller commands and Track Model
data into the train's motion and reported state.

## Protocol methods

- `step(dt, inputs) -> outputs`: advance one tick. dt is fixed; see D006.
- `snapshot() -> snapshot`: the full observable state, for the Train Model UI. It has
  no side effects.
- `set_failures(failures)`: Murphy's fault injection, from the Train Model UI.
- `pull_passenger_emergency_brake()`: a passenger pull, from the Train Model UI.

The last two are UI actions, not cross-module inputs.

## User interfaces

- The Train Model UI and the test UI are independent windows, each its own process.
  The test UI drives the module only through its interface and is removed at
  integration (D010).
- SDD v0.2 incorporates the October 20 review decisions and supersedes older
  wireframe assumptions in `TrainModel/refrence-docs/`. The developer utility is not
  a product actor or product use case.
- The Train Model UI's power readout shows the commanded power and is titled Power
  command. It is not a measurement of the power consumed.
- The Train Model UI shows each new announcement as a popup with its text.
- In the Train Model UI an active failure's button is red. This is a Train Model
  exception to `ui/style-guide.md` §6.1, which gives a clear-fault action the success
  fill; §6.1 itself is unchanged.

## Owns

- The train's physical state: operating mass, acceleration, velocity (signed), and
  position.
- The passenger count and the disembark draw. Passengers disembark once per stop: one
  uniform draw, made once the train is at rest with a door open. Opening the other
  door, or reopening one, draws nobody more; the next stop begins once the train has
  moved.
- The passenger emergency brake (`arbitration/passenger-emergency-brake.md`).
- Signals it produces: `actual-speed`, `train-position`, `block-change-event`,
  `passenger-capacity`, `brake-state`, `door-state`, `light-state`, and
  `cabin-temperature`. It also passes through `track-signal`, `beacon`, and the speed
  limit from `track-info` to the Train Controller.

## Consumes

- From the Train Controller: `power-command`, `service-brake-command`,
  `emergency-brake-command`, `light-command`, `door-command`, `temperature-setpoint`,
  `announcement`, and `passenger-brake-release`.
- From the Track Model: `track-info` (every tick), `track-signal`, `beacon`, and
  `passengers-boarded`.
- A step is rejected, before any state changes, if its grade is not strictly between
  −90° and 90°, its speed limit or commanded speed is negative, or its boarding count
  is negative. These values have no physical meaning. The test UI rejects a negative
  boarding count too.
- A step is also rejected if its authority or boarding count exceeds 2³¹ − 1, the
  largest count the UIs carry.
- A step is also rejected if dt exceeds 60 s, or if an on/off input (the brake, light
  and door commands, polarity, or the beacon's underground flag) is not a boolean.
- With several trains, a rejected step affects only the train whose input was invalid.
  The other trains step, and the rejection names that train.

## Enforced parameters

Vehicle: a Bombardier FLEXITY 2 (Blackpool), fixed 5-module consist. The consist is not
configurable.

| Parameter | Value | Source |
|---|---|---|
| Length, width, height | 32.2 m, 2.65 m, 3.42 m | Datasheet |
| Empty mass | 40,900 kg | Datasheet |
| Loaded mass (4 pass./m²) | 56,700 kg | Datasheet |
| Crew | 5 (1 per car); counts toward mass | Design §5.2 |
| Passenger capacity | 222 (74 seated + 148 standing) | Datasheet |
| Mass per person | 77.1107 kg (170 lb) | Customer Q&A |
| Maximum power | 480,000 W (4 × 120 kW) | Confirmed by Kevin Schillinger, SDD review 2026-10-20 |
| Maximum speed | 19.444 m/s (70 km/h); not enforced by the Train Model (D009) | Datasheet; instructor 2026-10-02 |
| Rated acceleration | 0.5 m/s² at 2/3 load | Datasheet |
| Service deceleration | 1.2 m/s² at 2/3 load | Datasheet |
| Emergency deceleration | 2.73 m/s² at 2/3 load | Datasheet |
| Reference mass | 51,433 kg = 40,900 + 2/3 × (56,700 − 40,900) | Derived; instructor 2026-10-02 |
| Traction limit | 25,717 N (51,433 kg × 0.5 m/s²) | Derived |
| Service brake force | 61,720 N (51,433 kg × 1.2 m/s²) | Derived; instructor 2026-10-02 |
| Emergency brake force | 140,413 N (51,433 kg × 2.73 m/s²) | Derived; instructor 2026-10-02 |
| Rolling resistance C_rr | 0.002 | Assumed textbook value |
| g | 9.81 m/s² | |

- Derived values (reference mass, traction and brake forces) are computed from these
  primitives, not entered by hand.
- The reference mass is empty mass plus 2/3 of the datasheet load, the difference
  between loaded and empty mass. Traction and brake forces are the reference mass
  times the rated acceleration and decelerations.
- Operating mass is empty mass plus crew and passengers times mass per person. It is
  recomputed on every boarding event.
- Traction is P/v saturated at the traction limit, and the motors drive forward only.
  They do so while the train rolls back too: under power they push against a
  rollback, slow it, and where traction allows, stop it and drive the train forward.
  Retain exact constant-force segments and midpoint power-limited integration
  with internal boundaries at stops and traction-regime transitions (D006). Segment
  durations total the fixed external dt; midpoint commanded-work accounting prevents
  artificial energy gain and internal limits maintain stability.
- Rollback is allowed. Brakes and rolling resistance oppose motion and act as a static
  holding force at rest. They stop the train but never reverse it.
- Rolling resistance is the only passive resistance term in scope, using the existing
  configured coefficient 0.002. Grade is gravitational force and braking commanded
  force. Aerodynamic drag, wheel slip and brake build-up are outside this scope;
  this is not a claim of real-world calibration.
- Service and emergency engage independently and their configured forces sum when
  both engage (arbitration/brakes-apply-together.md). Service failure blocks service
  only. Emergency follows the controller command or passenger latch.
- Track Model sends boarding events only at stations. Train Model checks rest, open
  doors, count bounds and remaining capacity without a station-presence gate.
- Offset references the front of the train. This adds no rollback crossing rule.
- Station dwell is 45 s, owned by the Train Controller (D007).

## Failure modes

- Three independent failures, all injected by Murphy from the Train Model UI: engine,
  signal pickup, and brake. Any combination is valid.
- Engine failure zeroes traction. Signal pickup failure outputs commanded speed
  0 m/s and authority 0 blocks; Track Info terrain is unaffected.
  Brake failure blocks the service brake only. The emergency brake still works,
  whether commanded by the Train Controller or pulled by a passenger.
- Active failures are not sent to the Train Controller. The `failure-status` signal
  is withdrawn.

## Does not own

- Lighting logic: dusk/dawn and tunnel lighting belong to the Train Controller
  (`light-command`).
- Suggested speed, which goes from the CTC Office to the Track Controller and never
  reaches the train.
- Track circuit polarity and grade, which the Track Model supplies.
- The door interlock. The doors follow Door Command at any speed, and nothing in the
  Train Model keeps a door shut while the train moves (`signals/door-command.md`).
  The Train Controller ensures doors remain closed when required.
- Throughput accounting. Disembark counts are not reported; the Track Model and the CTC
  Office handle throughput.

## Beacon boundary

Use typed Beacon values and named harness fields. The bounded logical payload is
the canonical compact ASCII-escaped JSON array `[station_name, platform_side,
underground]`, with at most 128 characters including syntax and escapes; reject
overlength payloads without truncation. See signals/beacon.md for serialization.
Output None between beacon ticks; Train Controller retains information when needed.

## Identity and window metadata

Use the fleet-provided train ID and line; the CTC Office owns train creation and
identity, routed through the harness roster. Retain next-station and platform data.
Arrival time is removed from the intended Train Model window for now.
The window offers no passenger-brake release action. The controller’s one-shot
passenger_brake_release clears the passenger latch without canceling an independently
held controller emergency command.

## Integrated clock

Supplied simulation time is the unwrapped end-of-tick timestamp. Each train’s epoch
is its first timestamp minus dt, established at its first roster appearance.
After stepping, on harness tick numbers divisible by 15, compare epoch plus accepted
model elapsed time with supplied time, including retained elapsed time for rejected
trains. Use absolute tolerance 1e-6 s. Display follows harness time independently.
Never reset physics elapsed time or the epoch to conceal discrepancies. The
developer utility’s older standalone 30-tick drift check is a separate path.

## Integration and verification

Modules own their boundary types; harness edge functions map directly between them
(D005/D008). Modules run in separate processes with one shared harness-owned clock.
Existing tests are local developer verification utilities. No enforcement policy
or plan to introduce one is specified here.

## Supersedes

- Previously described trapezoidal integration without closed-form segments; the reviewed design retains the existing event-aware segmented algorithm (D006).
- Previously called 480 kW provisional and door ownership pending; Kevin confirms power and Train Controller ownership.
- Previously lacked explicit combined-brake forces, boarding responsibility, front offset, canonical beacon encoding, and integrated display/clock rules; the October 20 SDD review supplies these.
- Previously used UI/wireframe metadata assumptions; the reviewed design uses fleet identity/line, retains station/platform, removes arrival, and separates development utilities from product use cases.
