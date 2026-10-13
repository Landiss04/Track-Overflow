# Track Model

The simulated physical track: blocks, switches, crossings, signal lights,
heaters, track temperature, stations and the passengers waiting at them.
Every input reaches its output, and failures have fail-safe effects.

New to the code? Start with
[`knowledge/CODE_OVERVIEW.md`](knowledge/CODE_OVERVIEW.md): what each
file does, and where to look for each behaviour.

## Run

From the repository root, two processes, started in either order:

```bash
TrackModel/.venv/Scripts/python TrackModel/main.py          # Track Model + its UI
TrackModel/.venv/Scripts/python TrackModel/test_ui/main.py  # test UI
```

The test UI stands in for the Track Controller, the Train Model and the
clock. It reaches the module only through the test link, so it can be
removed at integration with no change to `track_model/`. With **Act as the
Train Model** ticked, it moves its trains: add a train, give it a speed,
press Run.

## Test

`run_tests.py` prints every automated test grouped by area, with what it
checks and PASS/FAIL; extra arguments go to pytest (e.g. `-k switch`).
`MANUAL_TESTS.md` is the step-by-step script for checking both windows by
hand.

```bash
cd TrackModel
.venv/Scripts/python run_tests.py
.venv/Scripts/python -m pytest
.venv/Scripts/python -m mypy --strict --follow-imports=silent -p track_model -p tests -p test_link -p test_ui -m common.harness.track_model_edges -m main -m run_tests
.venv/Scripts/python -m flake8 --max-line-length=79 track_model tests test_link test_ui main.py run_tests.py ../common/harness
```

## Setup (if `.venv` is missing)

```bash
cd TrackModel
python -m venv .venv
.venv/Scripts/python -m pip install "PySide6>=6.11" "pyinstaller>=6.22.2" pytest mypy flake8
```

## Layout

```
track_model/interface.py   boundary types and the TrackModel protocol
track_model/layout.py      layout JSON loader and the track graph
track_model/model.py       the module: step(dt, inputs) -> outputs
track_model/state.py       Track Model UI state, in display units
ui/                        Track Model UI (QML)
test_link/                 test scaffolding: JSON codec and local-socket link
test_ui/                   test UI process (removed at integration)
tests/                     pytest suite
*_line.json                course track layouts
../common/harness/track_model_edges.py   the helpers other modules call
```

## How other modules reach the Track Model

Through the central harness (D005), never by importing `track_model`.
`common/harness/track_model_edges.py` has one pure function per edge,
mapping through the catalog types in `common/interfaces.py` (D008):

| Edge | Function |
|---|---|
| Track Controller → Track Model | `track_controller_to_track_model` |
| Train Model → Track Model | `train_model_to_track_model` |
| Track Model → Track Controller | `track_model_to_track_controller` |
| Track Model → Train Model | `track_model_to_train_model` |
| Track Model → Train Controller | `track_model_to_train_controller` |
| Track Model → CTC Office | `track_model_to_ctc_office` |

Ticket sales go to the CTC Office directly, as `(count, line)` pairs: the
tickets sold this tick. The Track Model keeps no running total and
sends none. The CTC Office reads everything else (occupancy, device state)
through the Track Controller.

## Behaviour

- **The Track Model never routes.** It applies the Track Controller's
  switch commands, and a train follows the rails as the switches are set.
- **Occupancy** comes from `offset_m` in each train's report. At or past
  the block length the train moves to the next block; below zero it rolls
  back to the block it came from. The new block reaches the Train Model in
  Track Info, with polarity reversed. `block_changed` is recorded, not
  used, because it follows the Track Model's own move.
- **Signals** stand on the block before each switch. A train sees a light
  once, on the tick it enters that block (`signal_seen`); the Train
  Controller keeps it, and later changes do not reach the train.
- **Commanded speed and authority are per block**, like the signal on
  the rails: the Track Controller knows which blocks are occupied, not
  which train is in them. A train receives the values of the block it is
  in. Commanded speed is a whole number of m/s (`int`). Authority is a
  count of blocks (`int`, D013, pending in truth): how many blocks past
  its current one the train may still enter; 0 means stop. A block that
  was never commanded, or whose circuit is dead, carries 0 and 0.
- **Offsets restart at 0 in each block.** The Train Model resets its
  offset when it sees a new block. The Track Model keeps what that reset
  throws away: the overshoot when a train moves forward, or the new
  block's length when it rolls back into it (it enters at the far end).
  Tested against the real Train Model: the two agree on position to the
  nanometre over a full 19.8 km Green loop and while rolling back.
- **Boarding needs a door open.** The Train Model reports door state;
  passengers board only when a train is stopped in a station block with
  a door open, the same rule the Train Model accepts them by, so none
  are lost.
- **A train that reports no block (`""`) is not on the track yet** and is
  skipped, rather than rejecting the whole tick.
- **Direction of travel** is in the layout file as `next_blocks` on each
  block: the blocks a train may move on to. One entry is one way; the
  blocks before and after is two-way; at a switch, both exits (`"yard"`
  for the yard). Green is annotated from the course map's arrows: two-way
  on 13–28 and 77–85, one way everywhere else, with A–C running downward
  (12 → 1) and 1 → 13. The loader checks it against the switch entries
  and refuses a partial or inconsistent annotation. Direction decides
  which way a newly placed train goes on a one-way block; it does not
  stop the Track Model following the rails as switched. Red and Blue are
  annotated too: the course map draws every section two-way, so every
  block lists each neighbour.
- **Out of the yard:** a train placed on a block where the yard joins
  the line (`Yard-63`) counts as having come from the yard, so it heads
  onto the line (63 → 64) and does not roll back into the yard.
- **Heaters and track temperature are per section** (e.g. `GREEN B`).
  The Track Controller turns a section's heaters on or off. Each
  section's track temperature eases toward ambient, or ambient + 10 °C
  while its heaters run; ambient itself is only ever the input value.
  The Track Controller reads back which heaters actually run and each
  section's track temperature.
- **Failures act fail-safe.** Any failure (broken rail, track circuit,
  power) makes its block read as occupied and cuts its track circuit, so
  a train in it gets 0 m/s and no authority. A power failure also holds
  the block's switch where it is, shows its light RED, drops its
  crossing gates, and stops its section's heaters. Commands sent during
  a power failure are kept and take effect when power returns.
- **Commands persist:** a key absent from a tick's commands keeps its last
  value. Devices start safe: switches NORMAL, gates up, lights RED,
  heaters off.
- **Invalid input is rejected whole**, before any state changes.
- **The window shows each block's track circuit** (commanded speed in mph
  and authority in blocks): the **Cmd mph** and **Auth** columns, and the
  Selected panel. A failed circuit shows 0 and 0, as the train gets.
- **Ambient temperature is set in the Track Model window** (Conditions,
  in °F). Once set it replaces the temperature the test UI sends, until
  the module restarts (Reset module or Load track…). Until then the test
  UI's `ambient` row applies.
- **Load track…** (Track Model window) loads a layout JSON. The file
  replaces the loaded line of the same name, or adds a new line, and the
  module restarts (no trains, devices at rest). A bad file changes
  nothing. Press **Reset module** in the test UI afterwards so it learns
  the new devices.

## Integrating with the Train Model

Checked against Kevin's Train Model on `Train-model-Interface`
(2026-10-07), running both modules together through the harness edges:
the full Green course loop, rollback, boarding with doors open and shut,
and speed/authority pass-through all work. What is still needed:

**On the Train Model side (Kevin):**

1. **Platform side `"LR"`.** The layouts have two-sided stations (8 Red,
   3 Green, e.g. MT LEBANON), sent as `"LR"`; the Train Model accepts only
   `"L"` or `"R"` and fails the tick, at GREEN M-76 on the course route.
   Blue's stations have no side in the layout and are sent as `""`.
2. **The Train Model's harness edges**: catalog `TrainTrackFeed` → its
   `TrackInputs`, and its outputs → catalog `TrainTrackReport`, including
   `doors_open = door_left_open or door_right_open`.

**In the harness (whoever writes the tick loop):**

- Each tick: Track Model steps on last tick's train reports, then each
  Train Model steps on this tick's feed. Other orders work too: a report
  still naming the block a train just left is recognised as stale.
- **Dispatch:** a new train has no block yet, so the harness sends the
  Track Model the train's first report itself, at its starting block
  (offset 0), to get the first feed.
- **Yard:** when a train runs into the yard it gets no feed
  (`track_model_to_train_model` returns `None`); the harness stops
  stepping that Train Model.

**In truth (proposals still to write):** D013 (authority as a block
count) to promote; the Train Model's door state gaining the Track Model
as a consumer; the offset-restarts-at-0 convention (open question 13
below); `"LR"` in the beacon entry.

## Provisional, pending decisions

1. Block ID format `"<LINE> <section>-<number>"`, e.g. `GREEN D-13`.
2. Waiting passengers are pooled by station name, so the two DORMONT,
   GLENBURY, OVERBROOK, INGLEWOOD and CENTRAL platforms on the Green line
   share one queue each.
3. Boarding draws on the passengers waiting when the train stops; if the
   doors close on the same tick, the Train Model refuses that count.
4. Beacons sit on every neighbour of a station block.
5. Polarity reverses per train at each block change, so every boundary
   is detectable even where switches join odd and even numbers.
6. Failure effects are a fail-safe reading, not agreed with the Track
   Controller yet. Every section is assumed to have heaters; the layout
   files don't say. The heater rise (`HEATER_RISE_C`, 10 °C) and warm-up
   (`TRACK_TIME_CONSTANT_S`, 300 s) in `model.py` are placeholders.
7. Signal placement. The source spreadsheet marks "Light" on the Blue line
   at blocks 6 and 11; the JSON conversion turned those into
   `"beacon": true`, and the Green and Red files mark no lights.
8. Which switch leg is NORMAL: the first listed. Yard switches: `N-yard`
   leaves N for the yard instead of N+1; `Yard-N` enters N from the yard
   instead of from N-1.
9. Red's `"75-yard"` is on block 9's row in the file but is parsed as a
   switch at block 75.
10. Branch ends not joined by rail on Red and Blue are Blue 10|11, Red 66|67
    and 71|72, read off the track map.
11. A new train on a two-way block, or on Red or Blue, heads toward the
    next higher block number. On a one-way Green block it follows the
    block's direction.
12. Platform side `"LR"` (both sides) appears in the files; truth's beacon
    entry names only L and R.
13. Which point on the train `offset_m` measures (one block is occupied
    at a time). The offset restarting at 0 in each block follows the
    Train Model's code; not yet recorded in truth.
