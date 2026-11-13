# Track Model: integration guide

How to plug the Track Model into the full system and wire it to the other
four modules. Written for whoever builds the central harness (D005) and
for the owners of the modules on the other side of each edge.

For how the module works inside, see
[`knowledge/CODE_OVERVIEW.md`](knowledge/CODE_OVERVIEW.md). For its
behaviour rules, see the [README](README.md).

The code in section 5 was run against the current code on `track-model`.

---

## 0. Under the central harness (Phases 2 and 3)

The harness built on `claude/quirky-fermi-sickg4` runs each module as a process of its
own (R4), not in the harness's process as sections 4 to 6 describe. Those sections
still hold for the module's Python API; this one says how the harness actually drives
it. Section 5's in-process loop and the catalog edges in `track_model_edges.py` are not
on that path.

- **The process.** `track_overflow.py --module track-model --harness <server>` runs
  `track_model/module_process.py`. It loads the Green and Red Lines only (D023), shows
  the Track Model window, and steps the model once per `STEP`. Invalid inputs refuse the
  whole tick, and the model is unchanged. The step's simulation time goes to the window
  as the time of day. The window redraws at most every 100 ms, after the reply.
  Closing it hides it; only the harness ends the process.
- **The form.** Inputs and outputs travel as JSON, field for field as in
  `track_model/interface.py`, with enumerated values by name (`track_model/wire.py`).
  The harness sends no ambient temperature: the window is its source.
- **The edges.** `common/harness/track_edges.py` maps the Train Model's outputs to each
  train's report (`doors_open` is either door open) and each train's feed to the Train
  Model's track inputs. It translates the Track Model's block names (`GREEN K-63`) to
  line and number (`Green`, `63`) for every other module. A released train is placed at
  its line's yard exit block (D022) by a first report the harness sends for it, until
  its Train Model reports it. The light a train saw on entering a signal block goes to
  its Train Controller.
- **Commands.** Since Phase 3 the Track Controller SW commands the Green Line through
  `common/harness/wayside_edges.py`: commanded speed and authority per block, every
  tick, which last one tick (section 3.1); switches, lights and crossings. A scripted
  CTC Office in the harness (`common/harness/ctc_script.py`) gives it suggestions for
  the occupied block and the next one until the CTC Office joins (Phase 4). The Track
  Controller names a switch by the block it is listed on (truth `identifiers`); this
  module names it by its point (`GREEN D-13`). The harness maps the one to the other,
  and each light through its switch, from the layout files
  (`common/harness/track_devices.py`). No heater commands are sent (D026), so heaters
  never run while this module runs them only when commanded.
- **Read-back.** `controller.block_occupancy`, `switch_states`, `crossing_states` and
  `signal_states` go back to the Track Controller, with the names mapped the same way.
  A failed block reads as occupied (R33).

---

## 1. The rules that shape everything

| Rule | Source | Consequence for you |
|---|---|---|
| A central harness sits between modules. | D005 | Modules never import each other. Only the harness imports the Track Model. |
| `common/interfaces.py` is the harness-side signal catalog. | D008 | The edge functions translate Track Model types to and from catalog types. Modules never import the catalog. |
| One shared clock, run by the harness, 1x or 10x. | D017 | The harness owns `SystemClock`. The Track Model has no clock of its own. |
| Fixed time step. Speed changes tick rate, never `dt`. | D006 | Call `step(dt, ...)` with the clock's `tick_s` (0.1 s) every time. |
| Backend units everywhere across a boundary. | D002 | m, m/s, degrees, °C, seconds. The Track Model UI converts for display only. |

```
 CTC Office ──(through Track Controller)──┐
     ▲                                    ▼
     │ tickets            ┌──────────────────────────┐
     └────────────────────┤        HARNESS           │
                          │  clock + tick loop +     │
 Track Controller ◄──────►│  common/harness/         │◄──────► Train Model(s)
                          │  track_model_edges.py    │
 Train Controller ◄───────┤                          │
   (signal seen)          └────────────┬─────────────┘
                                       │ step(dt, inputs)
                                 ┌─────▼──────┐
                                 │ Track Model│
                                 └────────────┘
```

---

## 2. What you need

| Piece | Where | Notes |
|---|---|---|
| The module | `TrackModel/track_model/` | `TrackModel(TrackConfig(paths))` |
| Layout files | `TrackModel/{green,red,blue}_line.json` | Pass every path in `TrackConfig.layout_paths`. |
| Edge functions | `common/harness/track_model_edges.py` | One pure function per edge. |
| Catalog types | `common/interfaces.py` (last section) | `WaysideCommands`, `TrainTrackReport`, `TrackReadback`, `TrainTrackFeed`, `TicketSales`. |
| Clock | `utils/system_clock.py`, `utils/clock_driver.py` | `ClockDriver` ticks it from the Qt event loop. |
| Track Model window (optional) | `track_model/state.py`, `TrackModel/ui/` | See section 6. |

**Import paths.** The edge file imports both `common.*` and
`track_model.*`. Put **both** the repository root and `TrackModel/` on
`sys.path` before importing it:

```python
for path in (str(REPO_ROOT), str(REPO_ROOT / "TrackModel")):
    sys.path.insert(0, path)
```

`TrackModel/main.py` and `TrackModel/pytest.ini` already do this.

**Environment.** Python ≥ 3.10, PySide6 ≥ 6.11, from a virtual environment
only (`truth/conventions/toolchain.md`). The module itself needs no Qt;
the clock driver and the Track Model window do.

---

## 3. The six edges

All translation happens in `track_model_edges.py`. Call these; do not
reach into the module's types from outside the harness.

| # | Edge | Function | In → out | Direction |
|---|---|---|---|---|
| 1 | Track Controller → Track Model | `track_controller_to_track_model` | `WaysideCommands` → `TrackControllerCommands` | into the module |
| 2 | Train Model → Track Model | `train_model_to_track_model` | `{train_id: TrainTrackReport}` → `{train_id: TrainReport}` | into the module |
| 3 | Track Model → Track Controller | `track_model_to_track_controller` | `TrackModelOutputs` → `TrackReadback` | out |
| 4 | Track Model → Train Model | `track_model_to_train_model(outputs, train_id)` | → `TrainTrackFeed` or `None` | out, per train |
| 5 | Track Model → Train Controller | `track_model_to_train_controller(outputs, train_id)` | → `SignalAspect` or `None` | out, per train |
| 6 | Track Model → CTC Office | `track_model_to_ctc_office` | → `TicketSales` | out, direct |

`build_track_model_inputs(commands, reports, ambient_temp_c, sim_time_s)`
runs edges 1 and 2 and returns one `TrackModelInputs`. Use it instead of assembling
the input by hand.

### 3.1 Into the Track Model

**From the Track Controller** (`WaysideCommands`). All maps are keyed by
**block ID** (`"GREEN D-13"`) except heaters, which are keyed by
**section ID** (`"GREEN D"`).

| Field | Meaning |
|---|---|
| `commanded_speed_mps` | m/s (a float), per block. |
| `authority_blocks` | Blocks the train may still enter past its own; 0 = stop (D013). |
| `switch_positions` | Keyed by the switch's point block. |
| `crossing_gates_closed` | Keyed by the crossing's block. |
| `signal_aspects` | Keyed by the block the light stands on. |
| `heaters_on` | Keyed by section. |

Commanded speed and authority **last one tick** (truth
`signals/track-signal.md`): a block not commanded on the latest tick reads
zero, so the Track Model delivers each value once and then clears it.
Send them for every block that needs them, on every tick. For the device
commands, a key you leave out **keeps its last value**. Devices start
safe: switches NORMAL, gates up, lights RED, heaters off. So for those,
send only what changed, or resend everything; both work.

Speed and authority are **per block**, not per train: the Track
Controller knows which blocks are occupied, not which train is in them.
The Track Model gives each train the values of the block it is in.

**From the Train Model** (`TrainTrackReport`, one per train, every tick).

| Field | Meaning |
|---|---|
| `position.block_id` | Block the train believes it is in. `""` = not on the track yet; the Track Model skips it. |
| `position.offset_m` | Distance since entering this block. **Restarts at 0 on each block change.** Negative while rolling back. |
| `actual_speed_mps` | Signed. |
| `block_changed` | Recorded only. |
| `passenger_capacity` | Used for boarding. |
| `doors_open` | Left **or** right open. Boarding needs one open. |

A train missing from the map has **left the track**. Do not drop a train
from the map to mean "no report this tick"; send its last report.

**Ambient temperature** (°C) is set by a person in the Track Model
window (Conditions, in °F). That value is the source and replaces whatever
a sender gives until the module is reset (**Reset module** or **Load
track…**). `ambient_temp_c` is optional: `None` leaves the temperature as
it is, and the central harness sends none. A sender that gives one, such
as the test UI, sets it until someone sets it in the window.

### 3.2 Out of the Track Model

**To the Track Controller** (`TrackReadback`). Actual device state, which
a failure can make differ from what was commanded.

`block_occupancy`, `switch_positions`, `crossing_gates_closed`,
`signal_aspects`, `failures` (`FailureMode`), `heaters_on` (by section),
`track_temp_c` (by section).

The CTC Office reads occupancy and device state **through the Track
Controller**. There is no Track Model → CTC edge for those.

**To the Train Model** (`TrainTrackFeed`, per train).
`track_info` (grade, elevation, speed limit, polarity, station name),
`commanded_speed_mps` and `authority_blocks` of the occupied block,
`beacon` (or `None`), `passengers_boarded`.

`None` means the train is not on the track. That happens in two cases:
before dispatch (section 4.1), and after the train ran into the yard
(section 4.2).

**To the Train Controller** (an optional `SignalAspect`). Not `None` only
on the one tick a train enters a block that has a light. The Train
Controller must keep it; later changes do not reach the train. This edge
is **provisional**, not yet agreed with the Train Controller owner.

**To the CTC Office** (`TicketSales.sold_now`): a list of
`(count, station)` pairs, tickets sold **this tick** only. No running
total is kept or sent.

---

## 4. Order of work, dispatch and the yard

### 4.1 Tick order

Each clock tick, in this order:

1. Collect the Track Controller's commands.
2. Collect every Train Model's **last tick's** report.
3. `outputs = track.step(dt, build_track_model_inputs(...))`.
4. Send the readback to the Track Controller, tickets to the CTC Office.
5. For each train, send its feed to its Train Model and its signal-seen
   colour to its Train Controller.
6. Step each Train Model on its feed; keep its new report for next tick.

Other orders work: a report that still names the block a train just left
is recognised as stale and used only to correct position. But pick one
order and keep it.

`dt` is `clock.tick_s` (0.1 s). Never scale it with speed (D006). At 10x
the harness simply ticks ten times as often.

**Simulation time.** The central clock owns time. Pass
`clock.sim_time_s` as the `sim_time_s` argument of
`build_track_model_inputs` every tick. The Track Model uses it only for
the time of day in its window (24-hour `HH:MM:SS`, wrapping at midnight,
D017). Its behaviour is driven by `dt`, never by this value. If you send
none (`None`), the window shows the sum of the `dt` values it has been
stepped by. A negative or non-finite value rejects the tick.

---

## 5. Minimal wiring

A complete tick loop with the edge functions. Replace the three
`...` lines with calls into the real modules (through their own
harness-side adapters).

```python
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (str(REPO_ROOT), str(REPO_ROOT / "TrackModel")):
    sys.path.insert(0, path)

from common.harness.track_model_edges import (
    build_track_model_inputs,
    track_model_to_ctc_office,
    track_model_to_track_controller,
    track_model_to_train_controller,
    track_model_to_train_model,
)
from common.interfaces import (
    TrainPosition, TrainTrackReport, WaysideCommands,
)
from track_model.interface import TrackConfig, TrackModelError
from track_model.model import TrackModel
from utils.system_clock import SystemClock

LAYOUTS = tuple(
    str(p) for p in sorted((REPO_ROOT / "TrackModel").glob("*_line.json"))
)

track = TrackModel(TrackConfig(LAYOUTS))
clock = SystemClock()                    # starts paused at 05:00:00
reports: dict[str, TrainTrackReport] = {}
ambient_c = 15.0


def dispatch(train_id: str, block_id: str) -> None:
    # A new train: give the Track Model its first report at offset 0.
    reports[train_id] = TrainTrackReport(
        position=TrainPosition(block_id, 0.0),
        actual_speed_mps=0.0,
        block_changed=False,
        passenger_capacity=222,
        doors_open=False,
    )


def on_tick(sim_time_s: float, dt: float) -> None:
    commands: WaysideCommands = ...      # Track Controller, via harness
    try:
        outputs = track.step(
            dt, build_track_model_inputs(
                commands, reports, ambient_c, sim_time_s
            )
        )
    except TrackModelError as error:
        print(f"Track Model rejected tick: {error}")
        return

    ...  # send track_model_to_track_controller(outputs) to Track Controller
    ...  # send track_model_to_ctc_office(outputs) to CTC Office

    for train_id in list(reports):
        feed = track_model_to_train_model(outputs, train_id)
        if feed is None:                 # in the yard or not dispatched
            continue
        aspect = track_model_to_train_controller(outputs, train_id)
        # ... give feed to the Train Model, aspect to the Train Controller
        # ... reports[train_id] = <that Train Model's new report, as a
        #     TrainTrackReport via its own edge>


clock.add_tick_listener(on_tick)
```

Run it in real time by attaching a `ClockDriver` (needs a Qt event loop):

```python
from utils.clock_driver import ClockDriver

driver = ClockDriver(clock)
driver.start()
clock.resume()           # the clock starts paused
clock.set_speed(10)      # CTC Office's clock-speedup signal: 1 or 10 only
```

In tests, skip the driver and call `clock.tick()` by hand; it advances
even while paused.

`TrackModel/tests/test_harness_edges.py` and `tests/test_green_line.py`
are working examples of driving the module only through the edges,
including a full Green-line loop.

---

## 6. Showing the Track Model window

The window reads the module through `TrackModelState`; it holds no logic.
To run it in the harness process instead of the standalone `main.py`:

```python
state = TrackModelState(track)           # track_model/state.py
# after every track.step(...):
state.refresh()
state.mark_step()                        # drives the Running/Paused badge
```

Then load `TrackModel/ui/Main.qml` into a `QQmlApplicationEngine` with the
context properties `theme` (`ui.theme.build_theme()`) and `trackModel`
(the state). Copy the set-up from `TrackModel/main.py` (the
`QQuickStyle.setStyle("Basic")` call matters), and put the repository
root on `sys.path` so `ui.theme` and `ui.aspect_lock` resolve.

The window's own actions (Murphy failure injection, ambient temperature,
Load track…, Reset module) act on the module directly. Pass
`on_ui_action=` if the harness needs to know when one happens.

---

## 7. Removing the test scaffolding

At integration, delete `TrackModel/test_ui/` and `TrackModel/test_link/`,
and the `LinkServer` lines in `TrackModel/main.py`. Nothing in
`track_model/` depends on them. `tests/test_codec.py`,
`tests/test_link.py`, `tests/test_end_to_end.py` and
`tests/test_block_filter.py` go with them.

`edit_block` and `reset` on the module are test-only commands. Do not
call them from the harness.

---

## 8. Integration checklist

- [ ] Repo root and `TrackModel/` both on `sys.path`.
- [ ] One `TrackModel` constructed with every `*_line.json`.
- [ ] One `SystemClock`; `dt = clock.tick_s` and
      `sim_time_s = clock.sim_time_s` in every `step` call.
- [ ] Commands and reports built only through the edge functions.
- [ ] Block IDs in the `"<LINE> <section>-<number>"` form everywhere
      (`GREEN D-13`); section IDs as `"<LINE> <section>"` (`GREEN D`).
- [ ] New trains dispatched with a first report at offset 0.
- [ ] Trains whose feed is `None` after having had one are dropped.
- [ ] Each train's signal-seen colour kept by its Train Controller.
- [ ] Ticket sales forwarded to the CTC Office each tick, not summed by
      the harness into a total the Track Model is expected to hold.
- [ ] `TrackModelError` caught per tick.
- [ ] `run_tests.py`, `mypy --strict`, and `flake8` pass (commands in
      the README).

---

## 9. Open items for the other teams

These block a clean end-to-end run or are not yet agreed. They are the
Track Model owner's reading as of this branch; none is a decision.

| Item | Who | Detail |
|---|---|---|
| Platform side `"LR"` | Train Model | Layouts have two-sided stations (8 on Red, 3 on Green). The Train Model accepts only `"L"` or `"R"` and fails the tick (first hit: GREEN M-76). Blue stations send `""`. |
| Train Model edges | Train Model / harness | Train Model's `TrackInputs` and outputs need mapping to catalog `TrainTrackFeed` / `TrainTrackReport`, with `doors_open = door_left_open or door_right_open`. These edges are not written yet. |
| Signal-seen edge | Train Controller | Provisional; the Train Controller owner has not agreed to receive it. |
| Failure effects | Track Controller | Fail-safe reading (failed block reads occupied, circuit cut, power failure holds switch and shows RED) is not yet agreed with the Track Controller. |
| Ticket sales shape | CTC Office | The module sends `(count, station)` pairs, this tick only. The `ticket-sales` entry on `truth` still says per line and leaves the total open; three proposals in `truth/_inbox/track-model/` correct it and await promotion. |
| Authority as block count | all | D013 is on `truth`; the module's boundary types follow it. |
| Offset restarts at 0 per block | Train Model | Holds in the Train Model's code but is not recorded in `truth`. |
| Clock speed command | CTC Office | `clock-speedup` is a boolean to the harness. The harness maps it to `SystemClock.set_speed(1 or 10)`. |
| Ambient temperature source | Track Model owner | Set in the Track Model window; the harness sends none. |
