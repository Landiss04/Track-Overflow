# TrainModel — changes for review

Changes to the Train Model's code since the version on `development`
(`c8b41f8`, 2026-10-15), during Phase 5 integration, for review. Newest
first.

---

## 2026-11-04 — The window redraws at most 20 times a second

`0345b24` (10x headroom). The window only: every step's outputs are
unchanged.

- `train_model/state.py`: a tick tells the views of a new snapshot at
  most once per `view_interval_s`, and a trailing timer always tells
  them of the last change (`_notify`). Button presses and the test UI
  still tell them at once. The default, 0, tells them of every tick.
- `train_model/module_process.py`: the harness-driven fleet uses
  `VIEW_INTERVAL_S` = 0.05 s, 20 redraws a second, where at 10x a
  moving train changes 100 times a second (`TrainModelFleet`'s
  `view_interval_s`).

---

## 2026-11-02 — The traction cap holds a full train on the rated gradient

`fd90b4e`. The data sheet's 0.5 m/s² is the medium acceleration at 2/3
load, not the starting pull (Kevin Schillinger 2026-11-02).

- `train_model/interface.py`: `f_max_n` is the force that holds a full
  train (222 passengers and 5 crew, 58,404 kg) on the rated 6 % maximum
  gradient, rolling resistance included: 35,459 N (was 25,717 N). A
  full train now climbs the Green Line's 5 % blocks. Brake forces are
  unchanged. Train-Ctrl_HW's `MAX_FORCE_N` uses the same formula.

---

## 2026-10-28 — Pickup failure, passenger pull, speed limit and beacon

From Kevin Schillinger, 2026-10-28; Braden's request 9.

- Signal pickup failure (`661f249`): commanded speed and authority are
  sent as null, simulating invalid data, so a valid 0/0 cannot read as
  a failure. `ControllerOutputs` types are `float | None` and
  `int | None`; the overview shows "—", and the test UI keeps the
  entered rows while a readback is null. The harness edge passes null
  through (`a6c1eb3`).
- Passenger pull (`bd72876`): latched until the Train Controller's
  emergency brake command goes from true to false; a pull made after
  the last true is kept. The one-shot `passenger_brake_release` input
  added on 2026-10-20 is withdrawn.
- Speed limit (`a6c1eb3`): not sent to the Train Controller
  (`ControllerOutputs.speed_limit_mps` removed), on the Train Controller
  owner's word; commanded speed is the controller's limit. The window
  still shows the limit from Track Info.
- Beacon (`9105f6e`): the Train Model reports the beacon of the block
  the train is on. It keeps the beacon heard on the block before a
  station and reports it every tick the train is on that station's
  block (Track Info's station name matches), None elsewhere; a beacon
  heard leaving a station is never reported. The window's Next station
  comes from the beacon heard. The harness's beacon bridge is gone.

---

## 2026-10-21 — Windows sizing and presentation

`aa7776c`. Start-up windows fit the desktop's work area, fractional-DPI
minimum sizes hold while resizing, the bundled icons are installed
(`app.py`), and the test UI's emergency badge shows only for an active
brake (was also while disconnected). Tests: `tests/test_window_scaling.py`
and `tests/windows_startup_check.py` (192 scaling checks at 100–200 %).

---

## 2026-10-20 — The harness process and the October 20 review

`df9f3b6`, `b9e5671`, `4859971`.

- `train_model/module_process.py`, new: the process the central
  harness starts with `--module train-model`. It holds the fleet, shows
  the window, follows the harness's roster (a train joins when first
  named and leaves when no longer named, D022), and steps each train on
  its own: a train whose inputs are invalid misses the tick and is named
  in the reply while the others step. `train_model/wire.py`, new: the
  boundary types as JSON, field for field.
- Clock: the window shows the harness's time when integrated (wrapped
  at 24 h for display only), and the model's elapsed time standalone.
  Every 15 ticks each train's elapsed time is checked against the
  harness's; a drift over 1 µs shows a "Clock drift" warning in the
  window and is printed to stderr.
- Brakes: the service and emergency brakes can both be on, and their
  forces add (was: the emergency brake overrode the service brake). A
  brake failure still blocks only the service brake.
- Beacons are checked with the shared `utils/beacon_codec.py`
  (`encode_beacon`) in the model, the harness test UI and the track
  stub, replacing the model's own side and 128-character checks.
- Window: a service brake Applied/Released badge; Next station no
  longer shows an arrival time.
- Decisions recorded in comments and docs only: the Train Controller
  owns the door interlock, so the model follows door commands at any
  speed; boarding counts are checked for rest, doors, count and
  capacity with no station gate; 480 kW maximum power confirmed.
