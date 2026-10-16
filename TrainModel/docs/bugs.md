# Known bugs

Open bugs in the Train Model and its test UI, found by the stress tests of
2026-10-05, 2026-10-06 and 2026-10-07. Each has a way to reproduce it, its cause where
known, and a suggested fix. Fixed bugs are removed from this list; git holds
their history.

Severity:

- **Medium**: reachable in normal use, or on a real line.
- **Low**: needs a value no real producer sends, or is cosmetic.

Area is the **model** (`train_model/model.py`, the module itself), the
**test UI** (its harness, limiter, dwell and track stand-ins, removed at
integration), the **link** between the two processes, or the **UI** (QML).

| ID | Area | Severity | Summary |
|---|---|---|---|
| [B1](#b1) | Test UI | Medium | A brake failure during a station dwell lets the train roll away |
| [B3](#b3) | Test UI | Low | The limiter never uses the emergency brake |
| [B4](#b4) | Test UI | Medium | Nothing in the test UI holds a rollback |
| [B5](#b5) | Model, UI | Low | Finite but absurd inputs have no upper bound |
| [B6](#b6) | UI | Low | Long block or station names run off the Train Model window |
| [B7](#b7) | UI | Low | A field shows "Enter a number." after accepting a value of 10²¹ or more |
| [B8](#b8) | UI | Low | Integer fields call a too-large whole number "not a whole number" |
| [B12](#b12) | Model | Low | A station name of spaces counts as a station |
| [B13](#b13) | Test UI | Low | The Blue Line never ends |
| [B14](#b14) | Test UI | Low | The track stub moves at most one block per tick |
| [B15](#b15) | Test UI | Low | A malformed layout file silently falls back to Manual |
| [B16](#b16) | Test UI | Low | A very small speed cap overshoots about sixfold |
| [B17](#b17) | Tooling | Low | mypy reports a type error in `app.py` |
| [B24](#b24) | UI | Low | Tab reaches `announcement` before `polarity` |

## Bugs

### B1

**A brake failure during a station dwell lets the train roll away.** Test UI,
Medium.

- **Reproduce:** manual track, grade −4°, station `S`. Stop, open a door so
  the dwell starts, then induce a brake failure in the Train Model window.
  Within 10 s the train is at 14.9 mph with the doors still open, and the
  dwell is still counting down.
- **Cause:** the dwell holds the train with the service brake only, and a
  brake failure blocks the service brake.
- **Reach:** a downhill station on the Green Line (grades to −5%) is enough;
  gravity there beats rolling resistance.
- **Fix:** if the train moves during a dwell, command the emergency brake,
  which still works under a brake failure.
- **Decision:** left as it is (Kevin, 2026-10-07). The fix was tried in a
  scratch copy and held the train under 1 m/s.

### B3

**The limiter never uses the emergency brake.** Test UI, Low.

- **Reproduce:** manual track, grade −10°, full power, Blue Line speed limit.
  Gravity beats the service brake and the train passes 80 mph, still
  accelerating.
- **Cause:** the stand-in limiter only knows the service brake.
- **Reach:** needs a grade steeper than about −8.9° (15.6%) at empty load.
  The real lines reach ±5%, so only a typed grade gets there.
- **Fix:** apply the emergency brake when the service brake cannot slow the
  train back under the cap.

### B4

**Nothing in the test UI holds a rollback.** Test UI, Medium.

- **Reproduce:** manual track, grade 5°, full power. The motors push against
  the rollback but cannot hold that grade, and after 2 minutes the train is
  rolling back at 65 mph.
- **Cause:** the limiter caps forward speed only.
- **Reach:** a real line is enough when the train is heavily loaded. Empty,
  full power starts the train up any grade to 6.16% (3.53°), above the
  Green Line's 5%. On a 5% uphill, full power cannot start a train with 120
  or more passengers aboard; it holds one with up to 173 at rest, but with
  174 or more the train rolls back. A full train stopped on a 5% uphill,
  brakes released, full power, was rolling back at 8.0 mph after 120 s and
  still speeding up (probe, 2026-10-07). Severity raised from Low on that
  finding.
- **Fix:** brake when the train rolls back faster than a small margin.

### B5

**Finite but absurd inputs have no upper bound.** Model and UI, Low.

- **Reproduce:**
  - A temperature setpoint of −500 °C or 10³⁰⁸ °C is accepted, and the cabin
    follows it.
  - A speed limit of 10³⁰⁸ m/s is accepted and shows as *Infinity mph* in
    both windows; an elevation of −10³⁰⁸ m shows *-Infinity ft*.
  - A commanded speed of 10³⁰⁰ m/s prints unformatted
    (`2.2369360000000003e+300`).
  - 10²⁴ kW typed as power is accepted and silently capped at 480 kW.
- **Cause:** validation checks that numbers are finite and, for some, not
  negative; nothing sets a ceiling.
- **Fix (needs limits):** bound the setpoint to an HVAC range and the speeds to
  something physical; reject power above a sane multiple of the maximum.

### B6

**Long block or station names run off the Train Model window.** UI, Low.

- **Reproduce:** send a beacon whose station name is 128 characters, the
  most the beacon contract allows, or a block ID of 128 characters. The
  Position card's rows run past the window's right edge. 64 characters fit.
- **Cause:** the shared `ui/KeyValueRow.qml` elides its label but not its
  value, so a long value widens the row and the card around it.
- **Fix:** elide the value in `KeyValueRow`, with the full text on hover.
  The component is shared, so the change reaches every module's UI.
- **Decision:** not to be fixed (Kevin, 2026-10-07).

### B7

**A field shows "Enter a number." after accepting a value of 10²¹ or more.**
UI, Low.

- **Reproduce:** type 24 nines into `power_command` and press Return. The
  value is staged (10²⁷ W, capped at 480 kW when sent), but the field shows
  `1e+24` with *Enter a number.* under it.
- **Cause:** `ui/ValueField.qml` shows the value with `String()`, which uses
  exponent notation from 10²¹; the field's own validator rejects the `e`.
- **Fix:** format large values without an exponent, or let the validator
  accept one.

### B8

**Integer fields call a too-large whole number "not a whole number".** UI,
Low.

- **Reproduce:** type 24 nines into `authority`. It is refused with *Enter a
  whole number.*
- **Cause:** the integer validator's range is 32 bits; the message assumes
  any refusal is a format error.
- **Fix:** say the number is too large.

### B12

**A station name of spaces counts as a station.** Model, Low.

- **Reproduce:** step with `station_name=" "`, a door open and a boarding
  count. Passengers board.
- **Cause:** the station test is `bool(station_name)`.
- **Fix:** strip the name, or reject a blank one.

### B13

**The Blue Line never ends.** Test UI, Low.

- **Reproduce:** full power on the Blue Line. The train passes Station B at
  block 10 at the speed limit unless the tester brakes, then runs on forever
  in block 10: 27 km into a 50 m block after 20,000 ticks.
- **Cause:** the track stub keeps the train on the last block of its route.
- **Fix:** stop the train at the end of the route, or loop the route.

### B14

**The track stub moves at most one block per tick.** Test UI, Low.

- **Reproduce:** a route of 1 m blocks, offset 3.5 m: `follow` moves one
  block, not three, and flips the polarity once.
- **Cause:** `follow` checks only the current block's length.
- **Reach:** needs blocks shorter than a tick's travel, about 2 m at full
  speed; the Blue Line's are 50 m.
- **Fix:** advance through every block the offset has passed.
- Found by Qwen's review and confirmed by probe.

### B15

**A malformed layout file silently falls back to Manual.** Test UI, Low.

- **Reproduce:** point `load_blue_line` at a layout missing a block's fields.
  It returns `None`, and Run Control reads *Manual* with no reason given.
- **Cause:** the loader swallows every error and returns `None`.
- **Reach:** `test_ui.py` loads every line, the Blue Line included, with
  `load_line`, which exits with the reason. Only a `TestHarnessState`
  built with its default track, as the tests do, can still fall back
  silently.
- **Fix:** show why the layout did not load.
- Found by Qwen's review and confirmed by probe.

### B16

**A very small speed cap overshoots about sixfold.** Test UI, Low.

- **Reproduce:** manual track, speed limit 0.01 m/s, full power. The train
  reaches 0.058 m/s before settling near the cap.
- **Cause:** at full power the train covers the cap in one tick, before the
  limiter's first correction lands.
- **Fix:** none needed for real limits; noted for completeness.

### B17

**mypy reports a type error in `app.py`.** Tooling, Low.

- **Reproduce:** `python -m mypy train_model/` reports
  `app.py:61: Argument 1 to "install_window_scaling" has incompatible type
  "QObject"; expected "QWindow"`.
- **Cause:** `engine.rootObjects()` is typed as returning `QObject`.
- **Fix:** cast the root object to `QWindow`.

### B24

**Tab reaches `announcement` before `polarity`.** UI, Low.

- **Reproduce:** Tab down the input rows from `speed_limit`.
- **Cause:** the item view creates the off-screen rows in its own order, and
  Tab follows creation order.
- **Fix:** none planned; every row is still reached, in sight.

## Behaviour to decide, not bugs today

These follow the current rules but came up in testing:

- **A train can drive off with its doors open.** At rest, with power on, a
  door open and a boarding count, it boards and moves in the same tick, and
  the door stays open as it moves. The door interlock is commented out of the
  Train Model pending the course instructor (open-issues.md), so nothing keeps
  a door shut while moving. Which module should is not settled.
