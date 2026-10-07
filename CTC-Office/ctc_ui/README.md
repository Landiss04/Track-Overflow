# CTC Office UI (skeleton)

PySide6 + QML front-end for the CTC Office dispatcher console. This is a
**blank UI with no backend**: every panel shows its empty state, and
actions emit QML signals that nothing handles yet.

QML owns all visuals; Python owns startup and the design tokens. The
structure follows the Train Model UI on the `Train-Model-UI-experimental`
branch so the modules share one component vocabulary.

## Run

From the `CTC-Office` directory:

```bash
pip install -r ../requirements.txt
python -m ctc_ui
```

### Test UI

The test harness is a separate process with its own window. It stands
in for the Track Controller and the Track Model (the two modules the CTC
exchanges data with) and for dispatcher actions the CTC UI does not have
yet. Start the CTC Office first, then from a second terminal, also in
`CTC-Office`:

```bash
python ctc_ui/test_ui.py        # or: python -m ctc_ui.test_ui
```

It connects to the running CTC Office over a local socket, so both
windows act on the one live CTC module; the badge reads **Connected**
(the status says "Connecting…" until then, and "not running" if no CTC
Office answers). Only one CTC Office runs at a time: a second one prints
"A CTC Office is already running" and exits. The two windows drive each
other:

- **Send** replaces the Track Controller and Track Model inputs. The CTC
  window's simulation clock steps the module with them on every tick
  while it runs (Run / Pause, 1× / 10×). While the clock is paused they
  are staged: nothing changes until it runs, the CTC window keeps showing
  the last applied reports with a "staged" notice, but the safety checks
  already use them. Once applied the CTC window shows them: trains,
  closed and failed blocks and active crossings on the track map, trains
  in the occupancy window, reported switch positions in Maintenance.
  Ticket sales are per line: enter the count and pick Green or Red in the
  row's **Line** dropdown. They count tickets sold since the previous
  tick, so each Send's sales are counted once (a second Send before the
  next tick replaces the first).
- Send is all or nothing: if any part is rejected (an unknown block, two
  trains in one block, an unsafe order, a switch outside maintenance
  mode), nothing of it is applied and the status line says why. The
  inputs are applied before the dispatcher rows, so an order into a
  block failed in the same Send is refused.
- The **dispatcher rows** (orders, closed blocks, switch commands)
  follow what the CTC window does until you edit one; Send then makes
  the module match every edited row, so either window can override the
  other.
- If the CTC window restarts, the test UI reconnects by itself and sends
  its inputs again (not the dispatcher rows).
- **Outputs** update live from the module, in display units (mph, ft).
  Maintenance mode and clock speedup are owned by the CTC window (its
  operating mode and clock speed), so the test UI shows them in Outputs
  only; with `--standalone` both are dispatcher rows and Send steps one
  0.1 s tick.
- Errors (an unknown block, a switch outside maintenance mode) show in
  the status line of the window where the action was taken.

List rows (occupied blocks, train reports, switch and crossing states,
failures, dispatch orders, closed blocks, switch commands) are small
tables: **+ Add** an entry, edit it in place, × to remove it. Each entry
picks its line first, then a block, switch or crossing on that line from
the track layout, so there are no IDs to type; block numbers repeat
across lines, and a switch or crossing is named by the block the layout
file lists it on. Positions, states and failure kinds are dropdowns; only
train IDs, offsets, speeds and arrival times are typed.

To test the CTC module without the window, run the test UI with its own
in-process module instead:

```bash
python ctc_ui/test_ui.py --standalone
```

The **simulation clock** also belongs to the running CTC Office window,
over its own link, and the test UI's title bar has the same clock
controls as the CTC header. Run / Pause and 1× / 10× in either window
control the one clock, and both windows show it; see [Clock link](#clock-link). With no CTC Office running, the test UI
shows `--:--:--`, greys out its clock controls, and keeps retrying.

## What is interactive

The panels read and act on the live CTC module (a stub with no routing
yet) through `ctc_ui/ctc_host.py`:

- The **Simulation clock** in the header is live. It starts paused at
  05:00:00 (24-hour). **Run** / **Pause** start and hold it, and the
  **1× / 10×** toggle sets its speed: at 1× one simulated second lasts one
  real second. The CTC owns the one shared clock until the central harness
  takes it over. The speed is also the CTC's `clock_speedup` output (true
  at 10×), the command the central harness will relay to every module so
  they all run at one speed.
- The **Operating mode** toggle switches the right-hand column between the
  Automatic, Manual, and Maintenance views. Maintenance lets the
  dispatcher close blocks and set switches; leaving it releases every
  switch command. The mode itself is not sent to the Track Controller:
  it gets `closed_blocks`, every block closed (or closing) in
  maintenance mode, and may not override a listed block until the
  dispatcher reopens it.
- **Notices** under the header tell the dispatcher about a Track
  Controller update staged while the clock is paused, and about orders
  the CTC cancelled itself (a block closed, closing or failed).
  **Dismiss** clears the cancellations.
- The **Track view** colors each line (`--line-green`, `--line-red`) and
  draws each train as a small `--info` car on the track at its reported
  position, turned to follow the track and tagged with its ID; a block
  reported occupied with no train on it gets an untagged car. Closed
  (`--warning`) and failed (`--danger`) blocks are drawn heavy, with a
  halo (style guide 4.6, 6.4). An active crossing fills `--warning`.
  **+** and **−** zoom in steps of 1.25× (up to 4×); zoomed in, drag the
  map to pan. **Fit** shows the whole map again.
- **Train occupancy** lists every train the Track Controller reports or
  the dispatcher has ordered, with block, speed (mph), authority (blocks
  ahead, and the block it ends at), destination and requested arrival. Filter by line, status or train ID;
  click a row and **Select train** to load it into Selected train.
  "Keep open at bottom" or the minimize button docks it over the track
  view. Escape, the close button, or clicking the scrim closes it.
- **Dispatch train** (Manual): pick a line, a train (or a new one) and a
  destination station, with an optional arrival time (`HH:MM`). Picking a
  train that already has an order reroutes it. **Set authority** sends
  the train straight to a block instead; the CTC turns it into a count
  of blocks. The readouts show the suggested speed and authority the CTC
  sends to the Track Controller.
- **Selected train** shows the train's live readouts, including why its
  authority ends where it does; in Manual mode it also reroutes the
  train or cancels its order.
- **Close block** and **Active closures** (Maintenance only) close a
  block (with a confirmation step, style guide 7) and reopen it. A block
  with a train in it is listed as "Closing — train in block" and closes
  by itself once the train has left; **Cancel closing** withdraws it.
  Failed blocks are listed too; they clear when the Track Controller
  stops reporting them.
- Dropdowns show only what the dispatcher picked: choosing a line never
  pre-selects a block, station or switch, so no action is enabled with a
  value nobody chose.
- **Safety rules** the CTC enforces (refused with a message): no
  authority into a closed, closing or failed block; no train sent to a
  block on another line than the one it is on; no switch moved while its
  block is occupied; one train per block. Orders into a block that
  closes, starts closing or fails are cancelled, with a notice.
- **Authority** is the number of blocks ahead of the train's current
  block it may still enter (0: stop before leaving it), recomputed every
  step. It runs toward the destination and stops before the first
  occupied, closed, closing or failed block, and before any switch the
  Track Controller has not reported set for the route.
- **Set switch position** (Maintenance) shows each switch's two
  connections (normal is the first listed in the layout file), the
  position the Track Controller reports and the one the CTC commands, and
  sends or releases a command.
- **Throughput metrics** show tickets per hour on each line (Red line,
  Green line) since the simulation started, from Track Model ticket
  sales, in the tiles and the per-line table. **Throughput, last 12
  hours** charts the tickets sold on each line in each simulated clock
  hour, one small chart per line on a shared scale; hover a bar for its
  value. The window starts at the simulation's start hour and follows
  the current hour once 12 hours have passed. The charts use `--accent`,
  not the line colors: the style guide keeps those to track strokes, and
  red and green bars are not distinguishable with deuteranopia.
- **Load schedule** (Automatic view) loads a schedule JSON in the
  `utils/schedule_v4.json` format (see `tools/schedule_to_json.py`). Its
  runs appear under **Next departures** as Queued, with due times counted
  from the schedule start. They stay queued until a scheduling algorithm
  exists; until then **Pause dispatch** is unavailable and the panel says
  so. A malformed file, or one naming a block or line that is not on the
  track layout, shows an error and keeps the current schedule.
- Trains per hour and the per-line trains and dwell columns stay empty:
  nothing reports that data yet.

## Where things go

| Area | Hook |
| --- | --- |
| CTC module | `ctc` context property, a `CtcHost` (`ctc_host.py`). Views and panels take it as `host`. Read `trains`, `blockStates`, `crossingStates`, `closures`, `throughput`; call `trainDetail`, `switchDetail` and the `*Options` slots; act with `dispatchTrain`, `setAuthority`, `cancelDispatch`, `closeBlock`, `reopenBlock`, `setSwitch`, `releaseSwitch`, which return an error message or `""`. Bindings that call a slot read `host.revision` so they refresh when the module changes. |
| Track map | `panels/TrackViewPanel.qml` → `mapCanvas`; `blockStates` and `crossingStates` style the blocks. Set `mapAvailable` to enable zoom and fit. |
| Selected train | `SelectedTrainPanel.trainId` and `host`; `canReroute` adds the reroute controls. |
| Schedule file | `AutoDispatchPanel.scheduleFileSelected(fileUrl)` → `ctc.loadSchedule`; `scheduleFile`, `scheduleError`, `departures` come back from `ctc`. |
| Tables | `DataTable.rows`: an array of objects keyed by each column's `key`. |
| Test harness | `ui/test/TestHarnessView.qml` in the test UI process. `inputs` / `outputs`: arrays of `{ name, kind, value, unit }`, where `kind` is `bool`, `int`, `float`, or `string`. Handle `inputEdited`, `sendInputsRequested`, and `resetInputsRequested`, and set `connected` once linked to a running CTC. |
| Header | `CtcHeader.clock`, `.paused` and `.speed` are bound to `simClock` (see below); `.operatorName`. |
| Simulation clock | `simClock` context property, a `SimulationClockBridge` (`sim_clock.py`) that owns the shared `utils.system_clock.SystemClock` and drives it in real time. Read `timeText`, `paused`, `speed`; call `pause()`, `resume()`, `setSpeed(1 or 10)`. Use `simClock.clock` from Python to add tick listeners. |

## Layout

```
__main__.py             CTC Office entry point: builds theme, loads QML
test_ui.py              test UI entry point (separate process)
sim_clock.py            SimulationClockBridge: the shared clock for QML
clock_link.py           clock link between the CTC and the test UI
ui/Main.qml             window, fixed 1440×900 canvas, mode + window state
ui/views/*.qml          Automatic / Manual / Maintenance right-hand columns
ui/panels/*.qml         track view, dispatch, schedule, throughput,
                        closures, switch, close block, occupancy window/dock
ui/components/*.qml     CTC-only building blocks (see below)
ui/test/TestMain.qml    test UI window
ui/test/TestHarnessView.qml  inputs / outputs tables and run controls
```

### Shared components

Buttons, fields, badges, readouts, tables and the theme tokens come from
the repository-level [`ui/`](../../ui/README.md) folder shared by every
module. `__main__.py` puts the repository root on `sys.path` to import
`ui.theme`. QML files import the folder relatively: `import
"../../../../ui"` from `ui/panels/`, `ui/views/` and `ui/components/`.
Do not copy shared components into this module; change them in `ui/`.

`ui/components/` holds only what the shared library does not provide:

| Component | Why it is CTC-only |
| --- | --- |
| `CtcHeader` | Window buttons, mode toggle and clock; shared `ModuleHeader` has navigation tabs instead |
| `ClockControls` | Simulation clock readout, Run / Pause and 1× / 10×; shared by `CtcHeader` and the test UI |

#### Moved to the shared library

These started here and were promoted to `ui/` on 2026-09-30 so other
modules can use them. They are catalogued in the shared
[`ui/README.md`](../../ui/README.md) and shown in `ui/gallery/`.

| Component | Was | Now |
| --- | --- | --- |
| `Panel` | `ctc_ui/ui/components/Panel.qml` | `ui/Panel.qml` |
| `EmptyState` | `ctc_ui/ui/components/EmptyState.qml` | `ui/EmptyState.qml` |
| `FormField` | `ctc_ui/ui/components/FormField.qml` | `ui/FormField.qml` |
| `LabeledDivider` | `ctc_ui/ui/components/LabeledDivider.qml` | `ui/LabeledDivider.qml` |
| `ModeCallout` | `ctc_ui/ui/components/ModeCallout.qml` | merged into `ui/Callout.qml` (file name kept); use `Callout { variant: "warning" }` |

## Checks

```bash
python -m flake8 --max-line-length=79 --max-doc-length=72 ctc_ui
python -m mypy --disallow-untyped-defs ctc_ui
pyside6-qmllint -I ctc_ui/ui -I ctc_ui/ui/components -I ctc_ui/ui/panels \
    -I ctc_ui/ui/test -I ../ui $(find ctc_ui/ui -name '*.qml')
```

flake8 and mypy are clean. qmllint's only remaining warnings are
`[unqualified]` access to the `theme` context property. That is inherent to
the context-property pattern shared with the Train Model UI.

## CTC module and link

- `ctc/interface.py` is the CTC's boundary (decision D005): inputs from
  the Track Controller and Track Model, outputs to the Track Controller
  (suggested speed and authority, closed blocks, switch commands,
  maintenance mode) and to the central harness (clock speedup), and the
  `CtcOffice` contract (`step(dt, inputs) -> outputs`, `validate_inputs`,
  dispatcher actions and `load_schedule`). Every block, switch and
  crossing reference carries its line.
- `ctc/model.py` is a stub implementation with no scheduling logic yet.
  It checks every reference and value against the track layout files
  and the boundary types, enforces the safety rules above, accepts
  switch commands and block closures only in maintenance mode, and gives
  each dispatched train on the track an authority counted in blocks
  (above) and a suggested speed 1 m/s under its current block's speed
  limit (whole m/s, rounded down). A train not yet on the track (the yard is a black
  box) gets neither until it is reported.
- `ctc/routing.py` reads how blocks connect from the layout files
  (neighbouring blocks, and each switch's normal and reverse
  connections; the yard is left out) and counts authority along the
  shortest route a train can run. Direction of travel is not modeled
  yet.
- `ctc/actions.py` runs dispatcher actions sent by name over a link,
  with strict argument types, and applies a test UI Send all or nothing
  (tried on a copy of the module first).
- The CTC window hosts the module (`ctc_ui/ctc_host.py`) and serves it
  over `ctc/socket_link.py`: a Qt local socket (a named pipe on Windows,
  never a network connection) carrying one JSON message per line. The
  test UI connects with `SocketLink`, or uses `ctc/link.py`'s `LocalLink`
  with `--standalone`. At integration the central harness calls the
  module directly and the links are not used.

## Clock link

`clock_link.py` lets the test UI, in its own process, control the CTC
Office's simulation clock. The CTC process listens with a `QLocalServer`
(`ClockLinkServer`) and the test UI connects with a `QLocalSocket`
(`ClockLinkClient`). That is a named pipe on Windows and a Unix socket
elsewhere, never a network connection. Messages are JSON, one per line:

| Direction | Message |
| --- | --- |
| CTC → test UI | `{"type": "clock", "time": "05:00:03", "paused": false, "speed": 1}`, on connect and whenever the shown time, pause state or speed changes |
| Test UI → CTC | `{"type": "pause"}`, `{"type": "resume"}`, `{"type": "set_speed", "speed": 10}` |

Anything malformed, of an unknown type, or with a speed other than 1 or 10
is ignored. The CTC Office runs normally whether or not a test UI is
connected, and if the link cannot start (for example, a second CTC Office
is already running) it prints a warning and carries on.

The module's inputs and outputs use the same approach on a separate
socket; see [CTC module and link](#ctc-module-and-link).

## Design notes

1. **No shadows.** QML has no cheap box-shadow, so `--shadow-1` is carried
   by `--border`, as in the Train Model UI.
2. **No dashed borders.** Empty states use a solid `--border-strong` frame.
3. **Scrim colour.** The style guide has no scrim token, so `Main.qml`
   derives it from `theme.text_primary` at 40 % alpha.
4. **The occupancy window is not a `Popup`.** A Popup reparents to the
   window overlay and would escape the canvas scale transform.
5. **No placeholders on text fields.** The shared `ValueField` does not
   expose `placeholderText` or `inputMask`, so the search hint and the
   `HH:MM` arrival-time mask were dropped when migrating to it.
6. **Window sizing is shared.** `ui/Main.qml` is a `ScaledWindow` and
   `__main__.py` installs `ui.aspect_lock.install_window_scaling`. The CTC
   used to correct the window size from a QML timer after each resize,
   which fought the window manager and snapped the window back to its large
   size; that code is gone. See `documents/SCALING_GUIDE.md`.
