# Track Model — code overview

A map of the Track Model's code: what each file is for, what happens on
every tick, and where to look when you want to understand or change a
behaviour. File paths are relative to `TrackModel/` unless they start
with `../`.

---

## 1. The big picture

Two programs run side by side and talk over a local connection:

```
 ┌───────────────────────────────┐        ┌──────────────────────────────┐
 │  Track Model process          │        │  Test UI process             │
 │  main.py                      │        │  test_ui/main.py             │
 │                               │ link   │                              │
 │  track_model/model.py  ◄──────┼────────┤  test_ui/harness.py          │
 │   (the actual module)         │ JSON   │   (pretends to be the Track  │
 │  track_model/state.py         │        │    Controller, Train Model   │
 │  ui/MainView.qml (window)     │        │    and the clock)            │
 └───────────────────────────────┘        └──────────────────────────────┘
```

- **The module** is `track_model/`. It has no idea a test UI exists. Every
  tick it is called as `step(dt, inputs)` and returns outputs. That one
  function is the whole interface.
- **The Track Model window** (`ui/`, fed by `track_model/state.py`) shows
  the module's state in display units (ft, mph, °F). Its one action is
  Murphy's failure injection.
- **The test UI** (`test_ui/`) stands in for every other module. It builds
  the inputs a real Track Controller and Train Model would send, ticks
  the clock, and shows the outputs. At integration it is deleted, and the
  real modules call the module through the harness instead (section 6).
- **The link** (`test_link/`) carries `step` calls and replies between the
  two programs as JSON. It is test scaffolding and is deleted at
  integration too.

---

## 2. File map

| File | What it does | Open it when you want to… |
|---|---|---|
| `track_model/interface.py` | The **data shapes**: what goes in (`TrackModelInputs`), what comes out (`TrackModelOutputs`), a `Block`, a `Switch`, the enums (`SwitchPosition`, `SignalAspect`, `TrackFailure`), and the `TrackModel` protocol that lists the module's functions. No logic. | see exactly what a signal contains, or add a new one |
| `track_model/layout.py` | **Loads the line files** (`*_line.json`), converts units (grade % → degrees, km/h → m/s), works out switches, signal locations and beacons, and builds the **track graph**: which block leads to which. `Layout.next_block` answers "where does the train go next?". | change how layout data is read, or how blocks connect |
| `track_model/model.py` | **The module itself.** `TrackModel.step` runs one tick. All the behaviour is here: commands, failures, heaters, train movement, occupancy, tickets, boarding, outputs. | understand or change any behaviour |
| `track_model/state.py` | Turns the module's state into rows and text for the **Track Model window**, converting to ft/mph/°F. Holds Murphy's failure action. | change what the Track Model window shows |
| `ui/Main.qml`, `ui/MainView.qml` | The **Track Model window's** layout: tables, the selected-block panel, the failure toggle. | move or restyle things in that window |
| `main.py` | Starts the Track Model process: loads the layout, creates the module, the window and the link server. | change how the program starts |
| `test_ui/harness.py` | The **test UI's brain**: holds the fake inputs, the fake trains, the block filter and the clock, and sends ticks over the link. "Act as the Train Model" lives here. | change what the test UI can drive or display |
| `test_ui/block_filter.py` | Line / section / range filtering for the test UI's block pickers. | change the filter |
| `test_ui/TestView.qml`, `test_ui/Main.qml`, `test_ui/main.py` | The test UI window and its start-up. | move or restyle things in the test UI |
| `test_link/codec.py` | Converts inputs and outputs **to and from JSON** for the link. | you added a field and it must cross the link |
| `test_link/link.py` | The **local connection**: `LinkServer` (inside the Track Model process) and `LinkClient` (inside the test UI). | the two windows don't talk |
| `../common/harness/track_model_edges.py` | The **functions other modules call** at integration, one per connection: Track Controller ↔ Track Model, Train Model ↔ Track Model, Track Model → Train Controller. | see what another module receives from you |
| `../common/interfaces.py` (last section) | The team-wide **catalog types** those functions translate to and from. Kevin owns this file. | check the shared shape of a signal |
| `green_line.json`, `red_line.json`, `blue_line.json` | The **track layouts**. Green also carries `next_blocks` (direction of travel). | fix layout data |
| `tests/` | The automated tests (section 7). `run_tests.py` prints them readably. | check what is covered |
| `README.md`, `MANUAL_TESTS.md` | How to run things, the behaviour rules, open questions, and the hand-test script. | — |

---

## 3. What happens in one tick

`TrackModel.step(dt, inputs)` in `track_model/model.py` runs these in
order. Each step is a small method you can read on its own.

| # | Method | What it does |
|---|---|---|
| 1 | `_validate` | Checks the whole input first: real block, switch, signal, crossing and section IDs; whole non-negative speeds; finite numbers. If anything is wrong it raises, and **nothing changes**. |
| 2 | `_apply_commands` | Stores the Track Controller's commands: speed and authority per block, switch, light, gate and heater commands. A switch moves to its command unless its block has lost power. |
| 3 | `_update_track_temps` | Moves each section's track temperature a little toward its target: ambient, or ambient + 10 °C while that section's heaters run. |
| 4 | `_move_trains` → `_advance` | For each train report: places a new train, ignores a stale report, or moves the train across a block boundary when its `offset_m` passes the block's length (forward) or goes below 0 (rollback). The next block comes from `Layout.next_block`, following the switches as set. |
| 5 | `_sell_tickets` | Each station rolls for a new ticket. |
| 6 | `_feed` (per train) | Builds what each train receives: Track Info for its block, the track circuit (speed and authority of its block, or nothing if the circuit is dead), the beacon if any, and passengers boarded (`_board`). |
| 7 | `_signal_seen` (per train) | If the train just entered a block with a light, the light's colour; otherwise nothing. |
| 8 | `_controller_outputs` | Builds what the Track Controller reads back: occupancy, switch, gate, light and heater **actual** states, failures, ticket sales and track temperatures. |

Between ticks, `set_block_failure` (Murphy) changes a failure and rebuilds
step 8 straight away, so the Track Controller sees it at once.

---

## 4. Where is…? (behaviour → code)

All in `track_model/model.py` unless noted.

| Behaviour | Look at |
|---|---|
| **Block occupancy** | `_controller_outputs`: a block is occupied if a train is in it **or** its circuit is dead (`_circuit_dead`). |
| **A train moving to the next block** | `_advance`; the "which block" answer is `Layout.next_block` in `layout.py`. |
| **Rollback** | `_advance` (the `offset_m < 0` branch) and `_behind`. |
| **Out of the yard / into the yard** | `_move_trains` (a new train at `Yard-63` is marked as come from the yard); `_advance` deletes a train whose next block is the yard. |
| **Switch positions** | `_apply_commands` (commanded → actual, unless power is out). Switch legs come from `_read_switches` / `_parse_switch_text` in `layout.py`. |
| **Signal lights** | `_signal_state` (RED without power); placement in `_signal_blocks` in `layout.py`. |
| **Signal a train sees** | `_signal_seen`. |
| **Crossing gates** | `_gate_closed` (down without power). |
| **Heaters** | `_heater_on`: commanded **and** no block in the section has lost power. |
| **Track temperature** | `_update_track_temps`, with `HEATER_RISE_C` and `TRACK_TIME_CONSTANT_S` at the top of the file. |
| **Failures and their effects** | The module docstring at the top lists them. `CIRCUIT_DEAD`, `_circuit_dead` and `_powered_off` decide; the effects are in `_feed`, `_controller_outputs`, `_signal_state`, `_gate_closed`, `_heater_on` and `_apply_commands`. |
| **Commanded speed and authority to a train** | `_feed` (the `TrackSignal` part): per block, or 0/none on a dead circuit. |
| **Beacons** | Placed by `_beacons` in `layout.py` (on every neighbour of a station block); sent in `_feed`. |
| **Ticket sales and waiting passengers** | `_sell_tickets`. |
| **Boarding** | `_board`: only while stopped in a station block. |
| **Direction of travel** | `next_blocks` in `green_line.json`, read and checked by `_read_next_blocks`, `_resolve_exits` and `_check_directions` in `layout.py`. Used by `Layout.next_block` and `previous_block` when a train's direction is unknown. |
| **Unit conversion from the layout files** | `_read_block` in `layout.py`. |
| **Display units (ft, mph, °F)** | `track_model/state.py` (`FT_PER_M`, `MPH_PER_MPS`, `c_to_f`). |
| **Test UI acting as the Train Model** | `stepOnce` and `_follow_feeds` in `test_ui/harness.py`. |

---

## 5. The data that goes in and out

Defined in `track_model/interface.py`. Every value is in backend units
(m, m/s, degrees, °C), and every ID is a string such as `"GREEN D-13"`.

**In (`TrackModelInputs`), every tick:**

- `controller` (`TrackControllerCommands`), keyed by block unless noted:
  - commanded speed (whole m/s) and authority (a block ID), per block;
  - switch positions, signal colours and crossing gates, each keyed by
    the block the device is on;
  - heaters on/off, keyed by section (`"GREEN B"`).
- `trains`: for each train ID, a `TrainReport` with block, offset into
  the block, speed, a block-changed flag and passenger capacity.
- `ambient_temp_c`.

**Out (`TrackModelOutputs`):**

- `controller` (`TrackControllerOutputs`), for the Track Controller:
  occupancy, switch / gate / light / heater **actual** states, failures,
  ticket sales and track temperature per section.
- `train_feeds`: for each train, a `TrainFeed` with Track Info, the
  track circuit (speed and authority), beacon and passengers boarded.
- `signal_seen`: for each train, the light colour on the tick it
  entered a signal block, else nothing.

Keyed by block: per-block data uses the block ID, a switch is keyed by
its point block, a light by the block it stands on, and a crossing by its
block.

---

## 6. How other modules will call you (integration)

Other modules never import `track_model`. Each connection between two
modules gets one translation function in
`../common/harness/track_model_edges.py`:

| Connection | Function |
|---|---|
| Track Controller → Track Model | `track_controller_to_track_model` |
| Train Model → Track Model | `train_model_to_track_model` |
| Track Model → Track Controller | `track_model_to_track_controller` |
| Track Model → Train Model | `track_model_to_train_model` |
| Track Model → Train Controller | `track_model_to_train_controller` |

At integration a central loop will do, each tick: gather the other
modules' outputs → translate them with these functions → call your
`step` → translate your outputs → hand them on. That's the job the test
UI does by hand today.

---

## 7. Tests

`run_tests.py` runs everything and prints it grouped by area:

| File | Covers |
|---|---|
| `tests/test_layout.py` | loading, unit conversion, switch parsing, the track graph |
| `tests/test_wiring.py` | every input reaching its output; movement; rollback; rejected input |
| `tests/test_green_line.py` | the Green line in detail, including the full course loop |
| `tests/test_green_direction.py` | `next_blocks`, and the loader rejecting bad direction data |
| `tests/test_heaters_and_failures.py` | heaters, track temperature, and every failure effect |
| `tests/test_contract.py` | the module matches its protocol |
| `tests/test_harness_edges.py` | the integration functions carry values unchanged |
| `tests/test_codec.py`, `tests/test_link.py` | the link between the two windows |
| `tests/test_end_to_end.py` | the real test UI driving the real module over the link |
| `tests/test_block_filter.py` | the test UI's block filter |

`tests/helpers.py` has `make_model`, `make_inputs` and `report`, which most
tests use to build a model and a tick's inputs in one line.

---

## 8. Changing things: a worked example

**Adding a new output to the Track Controller**, say a per-block "rail
temperature":

1. `track_model/interface.py`: add the field to `TrackControllerOutputs`.
2. `track_model/model.py`: fill it in `_controller_outputs`.
3. `test_link/codec.py`: add it to `encode_outputs` and `decode_outputs`,
   or it won't reach the test UI. `tests/test_codec.py` catches a miss.
4. `../common/interfaces.py` and `../common/harness/track_model_edges.py`:
   add it to `TrackReadback` and to `track_model_to_track_controller`.
5. `test_ui/harness.py`: show it in `controllerSummaryRows`.
6. A test in `tests/`, then `run_tests.py`.

**Adding a new input** is the same path backwards: `interface.py` → check
it in `_validate` → use it in `step` → `codec.py` → the edge function →
an input row in `test_ui/harness.py`.

**Tuning a placeholder value** (heater rise, warm-up time, ticket
probability): the constants at the top of `model.py`, or `TrackConfig`
in `interface.py`.

---

## 9. Words used in the code

| Term | Meaning |
|---|---|
| tick / `step` / `dt` | One simulation step; `dt` is always 0.1 s. |
| block ID | `"<LINE> <section>-<number>"`, e.g. `GREEN D-13`. |
| section ID | `"<LINE> <section>"`, e.g. `GREEN D`. Heaters and track temperature are per section. |
| point block | The block where a switch is; the switch is named after it. |
| leg | One of the two blocks a switch can send a train to. |
| fixed side | The side of a switch point away from its legs. |
| track circuit / track signal | What a block's rails carry to a train: commanded speed and authority. |
| commanded vs actual | `_switch_cmd` vs `_switches` and so on: what the Track Controller asked for vs what the device is doing (they differ during a power failure). |
| feed | Everything one train receives from the track in one tick. |
| snapshot | A read-only copy of the module's state, for the Track Model window. |
| stale report | A Train Model report still naming the block a train just left; ignored. |
| PROVISIONAL | A placeholder value or rule, listed in the README, until the team decides. |
