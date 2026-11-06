# Track Model

The simulated physical track: blocks, switches, crossings, signal lights,
heaters, track temperature, stations and the passengers waiting at them.
Every input reaches its output, and failures have fail-safe effects.

New to the code? Start with
[`knowledge/CODE_OVERVIEW.md`](knowledge/CODE_OVERVIEW.md): what each
file does, and where to look for each behaviour.

Wiring it into the full system: [`INTEGRATION.md`](INTEGRATION.md).

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

Through the central harness (D005), never by importing `track_model`. The
harness runs the Track Model as a process of its own
(`track_model/module_process.py`, `track_overflow.py --module track-model`) and
maps its inputs and outputs, in their JSON form (`track_model/wire.py`), with the
direct edges in `common/harness/track_edges.py` (Phase 2).

`common/harness/track_model_edges.py` contains legacy one-sided helpers that
still convert through stale `common/interfaces.py` types. D008 supersedes that
catalog: intended integration maps producer types directly to consumer types,
without a catalog intermediate. These helper names describe existing code, not
completed process integration:

| Edge | Function |
|---|---|
| Track Controller → Track Model | `track_controller_to_track_model` |
| Train Model → Track Model | `train_model_to_track_model` |
| Track Model → Track Controller | `track_model_to_track_controller` |
| Track Model → Train Model | `track_model_to_train_model` |
| Track Model → Train Controller | `track_model_to_train_controller` |
| Track Model → CTC Office | `track_model_to_ctc_office` |

Ticket sales go to the CTC Office directly, as `(count, station)` pairs: the
tickets sold this tick. The Track Model keeps no running total and
sends none. Sales are time-based: about 12 tickets per simulated minute
per station (`TrackConfig.tickets_per_minute`), the chance of a sale each
tick being derived from the tick length so the rate holds at any tick. The CTC Office reads everything else (occupancy, device state)
through the Track Controller.

## Behaviour

- **The Track Model never routes.** It applies the Track Controller's
  switch commands, and a train follows the rails as the switches are set.
- **Occupancy** comes from `offset_m` in each train's report. At or past
  the block length the train moves to the next block; below zero it rolls
  back to the block it came from. The new block reaches the Train Model in
  Track Info, with polarity reversed. `block_changed` is recorded, not
  used, because it follows the Track Model's own move.
- **Signals sit at switches** (TM-2): one per switch, at its point, named
  by the switch's ID (`GREEN D-13`). A light faces a train coming onto
  the point from its fixed side. Every tick each train is sent the light
  ahead of it (`signal_seen`): the first switch along its way, with the
  switches as set, that it will come onto from the fixed side. A train
  trailing through a switch from a leg does not see that switch's light.
  `None` only when the yard or a dead end comes first.
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
  The Track Model switches the heaters itself (D026): every section's
  heater is on while ambient is at or below 0 °C and off above it, with
  no hysteresis; a tick with no ambient keeps them as they were. A
  Track Controller heater command is accepted but not applied. Each
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
- **Commanded speed and authority last one tick** (truth
  `signals/track-signal.md`). Each tick's values replace the last: a
  block not commanded on the latest tick reads zero, so a value is
  delivered on the tick it is commanded and is gone the tick after.
  The Track Controller sends them again on every tick. Commanded speed
  is a float in m/s; authority is a whole count of blocks.
- **Device commands persist:** a switch, crossing or signal key absent
  from a tick's commands keeps its last value. Devices start safe:
  switches NORMAL, gates up, lights RED, heaters off.
- **Invalid input is rejected whole**, before any state changes.
- **The window shows each block's track circuit** (commanded speed in mph
  and authority in blocks): the **Cmd mph** and **Auth** columns, and the
  Selected panel. A failed circuit shows 0 and 0, as the train gets.
- **Ambient temperature is set in the Track Model window** (Conditions,
  in °F). Once set it replaces the temperature the test UI sends, until
  the module restarts (Reset module or Load track…). Until then the test
  UI's `ambient` row applies. The input is optional: the central harness
  sends none, so there the window is the only source.
- **Load track…** (Track Model window) loads a layout JSON. The file
  replaces the loaded line of the same name, or adds a new line, and the
  module restarts (no trains, devices at rest). A bad file changes
  nothing. Press **Reset module** in the test UI afterwards so it learns
  the new devices.

## Integrating with the Train Model

The October 20 SDD review supersedes the older October 7 integration assumptions.
See the [Train Model integration guide](../TrainModel/docs/integration.md).
The current working tree was inspected for this documentation update; no new
runtime verification is claimed.

- Train Model accepts platform sides `"L"`, `"R"`, `"LR"`. The complete canonical
  ASCII JSON logical payload `[station_name, platform_side, underground]` must fit
  128 characters including syntax/escapes. Reject without truncation; keep typed
  beacon values and named outer fields. The current shared codec checks full length.
  Send `None` between beacons; Train Controller retains information when needed.
- Track Model sends boarding events only at stations. Train Model checks rest,
  open doors, count bounds and capacity without a station-presence gate.
- Offset references the front of the train. This adds no rollback/block-crossing
  rule. Pickup failure zeroes commanded speed and authority; terrain is unaffected.
- Intended integration uses separate module processes and one harness-owned clock.
  The harness maps module-owned boundary types directly (D005/D008), with previous
  tick outputs forming each tick’s input snapshot. `common/interfaces.py` is stale.
- Phase 2 runs the Track Model as its own process under the harness, with direct
  edges to and from the Train Model and the Train Controller
  (`common/harness/track_edges.py`). Since Phase 3 the Track Controller SW sends its
  commands on the Green Line, and reads back occupancy and device states
  (`common/harness/wayside_edges.py`). The harness maps a switch from the Track
  Controller's name (the block it is listed on) to this module's (its point), and a
  light through its switch (`common/harness/track_devices.py`). It sends no heater
  commands (D026). The legacy `track_model_edges.py` catalog conversions are not on
  that path; they remain for this module's own tests.
- The CTC Office creates/retires trains; the harness routes the roster and identity.
  Avoid treating legacy yard/no-feed handling as the current lifecycle contract.
- D013 already defines authority as a count of blocks. Train Model’s controller
  outputs contain door state; adding the Track Model consumer/direct edge remains
  distinct integration work, not an implemented `TrackOutputs` field.

## Known bugs

[`BUGS.md`](BUGS.md) lists them.

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
