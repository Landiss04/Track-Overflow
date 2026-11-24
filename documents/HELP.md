# Track Overflow — User Help (All Modules)

Consolidated Help File for the whole system, combining each module's own
Help File into one document, per the strategy in
[user-help-strategy.md](user-help-strategy.md). Each section below is one
module's help, written by that module's owner; only heading levels and
internal links were adjusted so the sections nest under one document.

**Status notes** (flagged, not silently fixed):

- The Train Controller section's screenshots
  (`user-help-figures/train-controller/*.png`) are not yet committed to the
  repo — the links below point to where they're expected
  (`Train-Ctrl_HW/docs/user-help-figures/`), but will 404 until added.
- The Track Controller (software) section references
  `TrackCtrlSW/programs/green/` starter files and `TrackCtrlSW/samples/`;
  these were not found in the repo at consolidation time and are left as
  plain text, not links, until they're committed.
- The Track Model section's "Get help" contact is still a placeholder
  (`[name, email]`) in the source file.
- The Train Controller section's "Help and contact" is still a placeholder.

## Contents

1. [CTC Office](#ctc-office--help)
2. [Track Model](#track-model--help)
3. [Track Controller (Hardware)](#track-controller-hardware--help)
4. [Track Controller (Software)](#track-controller-software--help)
5. [Train Model](#train-model--help)
6. [Train Controller](#train-controller--user-help)

---

## CTC Office — Help

For dispatchers and testers: how to run the CTC Office, read its window,
dispatch trains by hand or from a schedule, close blocks and set switches,
and drive it from the test UI. For the module boundary and how the CTC
works out authority, see
[CTC-Office/ctc_ui/README.md](../CTC-Office/ctc_ui/README.md).

### The two windows

| Window | What it does | Who uses it |
| --- | --- | --- |
| CTC Office | The dispatcher console. Shows the track, the trains and their routes. Dispatches trains, loads the schedule, closes blocks, sets switches, and runs the simulation clock. | Dispatchers, testers, the demo |
| CTC Office Test Harness | Stands in for the Track Controller. Sends wayside status, occupied blocks, switch, crossing and signal states. Reads back what the CTC sends. | Testers only |

Each window is its own program. Close the test UI and the CTC Office keeps
running. Only one CTC Office runs at a time.

### Start

1. Open a terminal in `CTC-Office/` and activate the virtual environment.
2. Start the CTC Office: `python -m ctc_ui`
3. In a second terminal, also in `CTC-Office/`, start the test UI:
   `python ctc_ui/test_ui.py`

Start the CTC Office first. The test UI connects by itself. Its badge reads
**Connected** once it does.

The clock starts paused at 05:00:00. Nothing moves until you click **Run**.

### Read the CTC Office window

The header shows the **Operating mode** (Automatic, Manual or Maintenance),
the **Simulation clock** with **Run** / **Pause** and **1×** / **10×**, and
the **Train occupancy** button with the number of trains.

The left side is the **Track view**. The right side changes with the mode.

| Panel | Shows |
| --- | --- |
| Track view | Both lines. A train is a small car in its block, tagged with its ID. An untagged car is an occupied block no train explains: a failure. Closed blocks are drawn heavy with a halo. An active crossing is filled amber. Each switch's signal is a marker beside it: red square, yellow triangle, green circle, super green diamond. A hollow circle with **?** is a signal not reported. Point at a block for its line, number, section, speed limit, length, station and state. |
| Throughput metrics | Tickets sold per hour on each line since the simulation started. |
| Signals | Every signal light by line: its block, aspect and switch. **N of M reported**. Display only: aspects never change a train's speed or authority. |
| Selected train | The train you picked: current block, destination, next station, suggested speed, authority and where it ends (**Limited by**), arrival times and deviation. Its route is highlighted on the track view. |
| Notice | Warnings under the header: a line whose Track Controller is not ready, inputs waiting for the clock, or an order the CTC cancelled itself. Click **Dismiss** to clear cancellations. |

Use **+** and **−** to zoom (up to 4×). Drag to pan while zoomed in. Click
**Fit** to see the whole map.

The route highlight has two styles, shown in the legend: **Route, within
authority** is the blocks the train may enter now. **Route, beyond
authority** is the rest of its way.

### Operating modes

Pick a mode in the header. You can switch at any time.

| Mode | You can | Notes |
| --- | --- | --- |
| Automatic | Load a schedule. Pause or resume dispatch. | Trains dispatch themselves from the schedule. |
| Manual | Dispatch trains, queue stops, reroute, send a train back to the yard. | Schedule dispatch is paused while you are here. Scheduled runs are held. |
| Maintenance | Close and reopen blocks. Set and release switches. | Closures and switch commands stay when you leave, until you undo them here. |

### Find a train

1. Click **Train occupancy** in the header.
2. Filter by line, status, or type a train ID in **Search train**.
3. Click a row and click **Select train**. The train loads into **Selected
   train** and its route highlights.

Click **Keep open at bottom** or **Minimize** to dock the list under the
track view. Press Escape or click outside the window to close it.

| Status | Meaning |
| --- | --- |
| En route | The CTC sees the train on the track and is sending it speed and authority. |
| In yard | Dispatched, waiting in the yard to be released. |
| Not located | Its blocks all cleared outside the yard. The CTC has lost it. Its order stays. |
| No order | On the track, with nowhere to go. |

### Run a schedule (Automatic)

1. Set the mode to **Automatic**.
2. In **Auto dispatch**, click **Load schedule**. Pick a schedule file, such as
   [utils/schedule_v4.json](../utils/schedule_v4.json).
3. Click **Run** in the header.

The schedule starts (T = 0) when the clock runs with it loaded. Each run is a
train named for its line and run number: Green run 1 is **G1**. It leaves
the yard when due, stops 45 s at each of its scheduled stations, runs
through every other station, then returns to the yard.

**Departures** lists every run's due time and status:

| Status | Meaning |
| --- | --- |
| Queued | Not due yet. |
| In yard | Due, waiting to be released from the yard. |
| Held | Waiting for two-way track ahead to clear. |
| To *station* / At *station* | Heading for, or dwelling at, that stop. |
| To yard | Heading back to the yard. |
| Done | Back in the yard and retired. |

To hold every run, click **Pause dispatch**. No run leaves the yard or a stop
until you click **Resume dispatch**. Leaving Automatic mode holds them too.

A closed station is skipped. If a schedule file is malformed or names a
block that does not exist, it is refused and the current schedule stays.

### Dispatch a train by hand (Manual)

1. Set the mode to **Manual**.
2. In **Dispatch train**, pick the **Line** and the **Train** (or a new one).
3. Under **Stop at**, pick a **Station**, or type or pick any **Block** on
   that line.
4. Optional: enter an **Arrival** time as `HH:MM`.
5. Click **Dispatch train**.

The readouts show the speed and authority the CTC will send. A new train
waits in the yard until the line's yard exit block is clear, then enters
the track.

For a train that already has an order, the button reads **Queue stop**. The
stop goes after its last one. The train's stops show as cards, the one it is
heading for first. It dwells 45 s at each, then heads for the next. It stays
at the last.

- To remove a stop, click **×** on its card. You cannot remove a train's only
  stop.
- To reorder stops, use **▲ ▼** or drag a card by its handle. A new first
  stop takes effect at once.
- A train can have up to 20 stops.

To change where a train is going right now, select it and use **Reroute** in
**Selected train**. Stops queued after it stay.

To send a train back to the yard, select it and click **Return to yard**. It
goes there after its other stops and is retired. Only a train on the track
can be sent back. You cannot cancel an order.

### Close a block (Maintenance)

1. Set the mode to **Maintenance**.
2. In **Close block for maintenance**, pick the **Line** and **Block**.
3. Click **Close block**, then **Yes, close block**.

The block closes at once, even with a train in it. No train is given
authority into it. Orders into it are cancelled and listed in the notice.
Scheduled runs that use it are rerouted.

To reopen it, pick it in **Active closures** and click **Reopen block**.

### Set a switch (Maintenance)

1. In **Set switch position**, pick the **Line** and **Switch**. Each switch
   is listed by its two routes, normal first: `12 (12-13; 1-13)`.
2. Pick **Normal** or **Reverse**.
3. Click **Send to track controller**.

The panel shows what the CTC commanded and what the Track Controller
reports. They differ until the switch has moved.

A switch cannot be moved while its block is occupied. The command stays until
you click **Release**, which hands the switch back to the Track Controller.

### Drive the CTC from the test UI

The test UI is the Track Controller. Everything the dispatcher decides
(dispatching, closures, switches, mode, clock) is done in the CTC Office
window, never here.

| Input | What it stands for |
| --- | --- |
| `waysides` | Each wayside's startup: its ID, line, **Ready** or **Not ready**, and why not. |
| `occupied_blocks` | Blocks the Track Controller reports occupied. |
| `switch_states` | Each switch's actual position. |
| `crossing_states` | Each crossing, **Active** or **Inactive**. |
| `signal_states` | Each signal's aspect, picked by the block its light stands on. |

Each list starts empty. Click **+ Add** to add an entry, pick the line and
then the block, switch, crossing or signal. Click **×** to remove it.
Nothing is typed.

1. Add a ready wayside for each line you will use. A line is ready only once
   a wayside on it has reported and every wayside on it is ready.
2. Edit the other lists.
3. Click **Send inputs to CTC**.

While the CTC clock is paused, sent inputs wait until it runs. To start
over, click **Reset inputs**.

**Outputs** show what the CTC sends, updated live: each train's block,
suggested speed and authority, the next block on its route, closed blocks,
switch commands, and the clock speed and pause sent to the central harness.

To move a train: with the clock running, add its next block to
`occupied_blocks` and send, then remove the block behind it and send.

### Messages

| Message | Meaning | What to do |
| --- | --- | --- |
| Track Controller not ready on *line* | A wayside on that line has no PLC program, or none has reported. The CTC sends that line nothing and dispatches no train on it. | Load a PLC program on every wayside of that line. In the test UI, mark each wayside Ready and send. |
| Track Controller update staged | Inputs arrived while the clock is paused. | Click **Run**. |
| Order for *train* to *line* block *N* cancelled: *reason* | The CTC cancelled an order itself, usually because the block closed. | Dispatch the train somewhere else. Click **Dismiss**. |
| Reversal needed | A train cannot reach its stop without reversing, and the CTC does not reverse trains. It is waiting. | Reroute it, clear the way, or reverse it by hand. |
| *Line* block *N* is closed; no train can be sent into it. | The stop you picked is closed. | Pick another stop, or reopen the block in Maintenance. |
| *Line* block *N* is occupied; its switch cannot be moved under a train. | A train is on the switch. | Wait for the train to clear, then try again. |
| Blocks can be closed or reopened only in maintenance mode. | You are not in Maintenance. | Switch to **Maintenance**. |
| *Train* is going too fast to stop short of … | The new stop is too close for the train to stop in time. | Try again once it has slowed or gone on. |
| *Train* is a run of the loaded schedule … | Scheduled runs take their stops from the schedule. | Pause dispatch, or dispatch a different train. |
| That is *train*'s only stop … | You tried to remove its last stop. | Add another stop first, or send it back to the yard. |
| *Train*'s stops have changed since they were shown … | The train moved on while you were editing. Nothing changed. | Try again. |
| Schedule not loaded: *reason* | The file is malformed or names a block not on the track. The current schedule stays. | Fix the file and load it again. |
| A CTC Office is already running. | A second CTC Office was started. | Close the other one first. |
| The CTC Office is not running. (test UI) | The test UI cannot reach the CTC Office. | Start it with `python -m ctc_ui`. The test UI connects by itself. |

### Units

The CTC Office window shows speed in mph, length in feet, and authority in
blocks ahead of the train. Times are 24-hour simulation time. Authority 0
means the train must stop before leaving its block.

---

## Track Model — Help

The Track Model window shows the simulated track. You can watch every block,
switch, light, heater and train on the Green or Red Line. You can also break
the track on purpose to test how the system reacts.

**Product:** Track Overflow train control system — Track Model module
**Lines:** Green and Red

> **Read this first**
>
> - **Load track…** restarts the Track Model. Every train leaves the track.
> - A failure you set stops any train on that block. The train gets 0 mph
>   and no authority until you clear the failure.
> - This is a simulation for coursework. It is not certified for use on a
>   real railway.

### Start the window

1. Start the train control system. The Track Model window opens with the
   other module windows.
2. Check the header. It shows the line, **RUNNING** or **PAUSED**, and the
   simulation clock.

The clock is shared by the whole system. You start, stop and speed it up
from the system's clock controls, not from this window.

### What the screen shows

```
┌ Track Model ─ GREEN ─ RUNNING ─ 00:04:12 ─ [Blocks] [Switches & Lights] ┐
│                                            │                            │
│  Main table                                │  Selected block            │
│  (Blocks, or Switches & Lights)            │  Conditions                │
│                                            │  Trains on track           │
│                                            │  Waiting at stations       │
└────────────────────────────────────────────┴────────────────────────────┘
```

| Area | What it tells you |
|---|---|
| **Header** | Line, clock state, sim time. `GREEN · 2 FAILED` means two blocks have a failure. |
| **Blocks** tab | One row per block. |
| **Switches & Lights** tab | Every switch, signal light and section heater. |
| **Selected block** | Full details of the row you clicked. Also where you set a failure. |
| **Conditions** | Outdoor (ambient) temperature. |
| **Trains on track** | Each train's block, distance into the block, and speed. |
| **Waiting at stations** | Passengers waiting at each station. |

**Units:** feet (ft), miles per hour (mph) and degrees Fahrenheit (°F).

### Tasks

#### Switch between lines

- Under **Line**, click **GREEN** or **RED**.

All tables and the header change to that line.

#### Find a block or station

1. Type a block or station name in **Find block or station**. Examples:
   `D-13`, `GLENBURY`.
2. Press **Enter**.

To show every block again, clear the box and press **Enter**.

#### See everything about one block

1. Click a row in any table.
2. Read the **Selected** panel on the right.

It shows the signal light colour at the top. Below that it lists length,
grade, speed limit, commanded speed, authority, station, beacon, heater,
crossing gates, switch position and occupancy.

> **Note:** Clicking a train in **Trains on track** selects the block that train
> is in.

#### Follow a train

- Watch **Trains on track**. **Off ft** is how far the train is into its
  current block. It starts at 0 in each new block.
- On the **Blocks** tab, the **Occupied** column shows **TRUE** on the
  train's block.

#### Check switches, lights and heaters

1. Click **Switches & Lights** in the header.
2. Read the three tables:
   - **Switches** — where each switch leads when NORMAL and when REVERSE,
     and its current position.
   - **Signal lights** — the colour each light shows: RED, YELLOW, GREEN or
     SUPER GREEN.
   - **Heaters** — ON or OFF for each section, and its track temperature.

> **Note:** You cannot move a switch or change a light here. The Track Controller
> sets them. This window shows what is on the track.

#### Break the track (failure test)

Use this to test how the system handles a fault.

1. Click the block you want to break.
2. Under **Failure (Murphy)**, click one option:

   | Option | What happens on that block |
   |---|---|
   | **Rail** | Broken rail. |
   | **Circuit** | Track circuit fails. |
   | **Power** | Power is lost. The switch freezes in place, the light turns RED, crossing gates go down and the section heater stops. |

3. To fix it, click **None**.

Every failure has two effects. The block reads as **occupied**, and any
train on it gets 0 mph and 0 authority. The rest of the system sees the
failure at once, even while the clock is paused.

> **Note:** During a power failure, the Track Model keeps any new switch or light
> commands. They take effect when you click **None**.

#### Set the outdoor temperature

1. In **Conditions**, type a value in **Ambient temperature (°F)**.
2. Press **Enter**.

At 32 °F or below, every heater turns on by itself. Above 32 °F, every
heater turns off. The track temperature then moves slowly toward the new
value. Watch it on the **Switches & Lights** tab.

#### Load a different track

1. Click **Load track…**.
2. Choose a track layout file (`.json`), such as
   [green_line.json](../TrackModel/green_line.json).

The file replaces the line with the same name. The Track Model then
restarts with no trains on the track.

> **Warning:** Only load a track when no test is running. Loading removes every
> train.

### Read the Blocks table

| Column | Meaning |
|---|---|
| **Block** | Section and number, e.g. `D-13`. |
| **Dir** | Direction of travel. `↔` = both ways. `→ C-9` = one way, toward C-9. |
| **Len ft** | Block length. |
| **Grade °** | Slope of the block. |
| **Limit mph** | Speed limit. |
| **Cmd mph** | Speed the Track Controller allows on this block right now. |
| **Auth** | Authority: how many more blocks a train here may enter. 0 means stop. |
| **Station** | Station on this block, if any. |
| **Beacon** | Station a beacon on this block announces. Beacons sit next to stations. |
| **Heat** | ON when the section heater runs. |
| **Occupied** | TRUE when a train or a failure occupies the block. |
| **Signal** | Light colour, on blocks that hold a switch. |
| **Failure** | BROKEN_RAIL, TRACK_CIRCUIT or POWER, if set. |

### Common questions

**Why does Cmd mph show 0?**
The Track Controller has not sent a speed for this block, or the block has
a failure. Check the **Failure** column.

**Why is a block occupied with no train on it?**
It has a failure. A failed block always reads as occupied, so no train is
sent into it.

**Why do passengers not board?**
Passengers board only when a train is stopped at a station with a door
open.

**Why did all the trains disappear?**
Someone loaded a track. Loading restarts the Track Model.

### Messages

| Message | What it means | What to do |
|---|---|---|
| **Track not loaded** | The file you chose is not a valid track layout. The reason is shown below the heading. | Nothing changed. Choose a different layout file. |
| **No block selected** | You have not clicked a row yet. | Click any row in a table. |

### Maintain and repair

- **Track data** lives in the layout files
  [green_line.json](../TrackModel/green_line.json) and
  [red_line.json](../TrackModel/red_line.json), in the `TrackModel` folder.
- If a line looks wrong, reload its original layout file with
  **Load track…**.
- If the window stops updating, close the train control system and start
  it again.

### Get help

Contact the Track Model owner on the Track Overflow team:
**[name, email]** *(placeholder in the source file — fill in before final
submission)*

---

## Track Controller (Hardware) — Help

Covers the hardware Track Controller window's panels, the PLC language a
wayside runs, and how to read the two against each other. For install/run
instructions and the module's internal architecture, see
[TrackCtrlHw/README.md](../TrackCtrlHw/README.md).

### 1. What this module is

The hardware Track Controller runs every wayside of one line (the software
variant runs the other). Each wayside owns a contiguous run of blocks, loaded
from a database file, and runs its own Boolean PLC program loaded from a
`.plc` file. The module knows the blocks it governs, never the trains on
them — it reports occupancy, switch, signal and crossing state upward to the
CTC Office, keyed by block.

### 2. Reading the window

| Panel / control | What it shows |
|---|---|
| Header **Ready** / **Not ready** badge | Whether every wayside on this *line* is ready. Until all are, this wayside holds its fail-safe outputs and reports not ready to the CTC Office. |
| Header **Channel fault** badge | The running program's two independently compiled forms disagreed on this scan; every output is held fail-safe until a new program loads. Not a wiring problem — a program-verification failure. |
| **Wayside** selector | Switches which wayside on this line you're viewing. Each wayside runs its own program and territory. |
| **Wayside territory** | The schematic of this wayside's blocks, switches, signals and crossings. See the legend under the diagram for block-state coloring. |
| **Block occupancy** table | Per-block occupancy as the wayside has it, plus the CTC Office's most recent speed/authority suggestion for an occupied block (**Track circuit** column). |
| **NOT READY** / **CTC MAINTENANCE** banners | NOT READY explains what startup still needs. CTC MAINTENANCE lists blocks the CTC Office has closed or switches it has commanded here — the PLC program decides what to do with them; a closed block is not automatically treated as occupied. |
| **Wayside PLC** strip | The loaded program's file and load time. **New PLC** loads a replacement (takes effect at the next scan). The **i** button opens full program details (§4 below). |
| **CTC uplink** strip | The report last sent to the CTC Office; **View** opens it in full. |
| **From the office** table | Speed/authority the CTC Office suggested for this wayside's blocks — an input to the program, not a command it must obey. |
| **Switches** table | **Commanded** (`SW_n` output) vs. **Reported** (physical/simulated position); **CTC asks** is the office's request only, the program decides whether to honor it; **Agreement** flags a commanded/reported mismatch — usually a switch that hasn't finished moving, or has failed to. |
| **Signals & crossings** table | Same commanded/reported/set-by pattern as switches. **Set by** shows whether the last output change came from the running program or the wayside's fail-safe default (not ready / channel fault). |

### 3. The PLC language a wayside runs

The language is the one the software Track Controller variant also runs
(REQ-INTF-009) — same syntax, independently implemented, so the two
implementations are diverse rather than sharing a bug.

```
// a comment runs to the end of the line
VAR_IN   OCC_1..20          declares names the wayside feeds the program
VAR_OUT  SW_12 AUTH_1..20   declares names the program drives
NAME := expression           one assignment per line
```

- Every value is a single bit — `0`/`1`, nothing else.
- Operators: `AND`, `OR`, `XOR`, `NOT`, and parentheses, in that precedence
  (`NOT` binds tightest, `OR` loosest).
- A scan runs top to bottom, once. A name that's neither an input nor
  assigned earlier in the scan reads as `0` — the compiler warns about this
  in advance; check the **warnings** list in the PLC program details dialog
  before trusting a scan result.
- A full annotated example:
  [TrackCtrlHw/data/plc/green_wayside_1.plc](../TrackCtrlHw/data/plc/green_wayside_1.plc).
  The formal grammar is the module docstring in
  [TrackCtrlHw/track_ctrl_hw/plc.py](../TrackCtrlHw/track_ctrl_hw/plc.py).

### 4. PLC program details dialog

Opened from the **i** button beside **New PLC**.

| Field | Meaning |
|---|---|
| Checksum (CRC-32) | For confirming two waysides run the identical program file — not for diagnosing program behavior. |
| Scan overruns since load | Should stay `0`. Nonzero means a scan took longer than the scan interval. |
| Boolean variables / Statements | Size of the compiled program. |
| Scan interval / Last scan / Scan time | Timing of the two-channel scan described in §5. |

### 5. How a scan is checked (the diverse-channel guarantee)

Every statement compiles twice, by two different algorithms — recursive
descent (Channel A) and shunting-yard (Channel B) — run independently on
every scan. Any disagreement between them is a **channel fault**: see the
header badge in §2.

### 6. Troubleshooting

- **Switch/signal shows a fault/mismatch badge** → check Agreement / Set by
  in §2; it's a commanded-vs-reported mismatch, not necessarily a program bug.
- **Header shows Channel fault** → the loaded program's two compiled forms
  disagree; load it again or check it for a non-determinism bug (same
  inputs should always produce the same two results).
- **Header shows Not ready** → read the NOT READY banner for what's missing;
  it clears once every wayside on the line has a running program.
- **A number in the PLC details dialog looks wrong** → see §4's table before
  assuming it's a bug; several of those fields (checksum, scan overruns) are
  diagnostic counters, not live telemetry.

---

## Track Controller (Software) — Help

Help for the software Track Controller, for:

- **Programmers**, who write and commit the PLC program for each wayside (sections 1 to 7).
- **Testers**, who drive the module from the test UI (section 8).
- **Track builders**, who prepare the layout files the module reads (section 9).

The words in **bold** are the labels on screen.

### 1. What the module does

The Track Controller runs the waysides of a line. A wayside owns a stretch of consecutive
blocks with their switches, signals and crossings. Every tick it reads what the Track Model and
the CTC Office tell it, runs its PLC program, and sends the results to the track.

- Each wayside runs its **own** PLC program. The Green Line has six waysides, GTC-01 to GTC-06.
- After your program, every wayside runs **vital code**. You cannot edit it. It can only make an
  output safer: stop a block, turn a signal red, arm a crossing, hold a switch. A wrong program
  stops trains; it cannot cause a collision.
- A wayside with no committed program sends nothing to the track, except that its crossings
  stay armed.

### 2. Starting the module

| To do this | Run, from the folder named |
|---|---|
| Run the whole system | `python track_overflow.py` from the repository root |
| Run the whole system with the starter programs already committed | `python track_overflow.py --load-starters` |
| Run only the Track Controller | `.venv/Scripts/python main.py` from `TrackCtrlSW` |
| Drive it by hand, as tester | `.venv/Scripts/python test_main.py` from `TrackCtrlSW`, in a second window |

Under the whole system the Green Line is loaded for you. Run on its own, the module starts
with no track and an empty editor.

### 3. Quick start: get the Green Line running

1. If no track is loaded, press **Load track…** and choose `green_line.json`. Check the summary
   and press **Load**.
2. Pick **GTC-01** in **Controller**, then open the **Program** tab.
3. Press **Load .plc file** and open `TrackCtrlSW/programs/green/gtc01_starter.plc`.
4. Press **Run**. The **Parser** pane shows no messages.
5. Press **Commit iteration**. The editor shows **Committed**.
6. Repeat steps 2 to 5 for GTC-02 to GTC-06, each with its own file.

The header's **NOT READY** clears once all six waysides have a program. Each wayside starts
working as soon as its own program is committed.

### 4. Tasks

#### Load a track layout
1. Press **Load track…** and choose the line's layout file.
2. Check the summary: blocks, switches, crossings and how many waysides the line is divided
   into. The number of waysides is fixed by the track.
3. Press **Load**.

Loading a line that is already loaded replaces its waysides **and every program they hold**.
The dialog says so before you confirm. This cannot be undone.

#### Write or load a program
- **New** empties the editor so you can write a program from scratch.
- **Load .plc file** puts a file from disk in the editor. To start from a working program, load
  the wayside's starter from `TrackCtrlSW/programs/green/` and edit it.

Nothing reaches the track until you commit.

#### Check a program: Run
Press **Run**. It compiles the editor's text, checks it against this wayside's inputs and
outputs, and scans it once on a copy of the wayside's current state.

- The **Parser** pane lists every error and warning with its line number.
- The watch panes show what the program would output.
- **VITAL OVERRIDES** lists every place the vital code changed your output, and why.

Run changes nothing on the track.

#### Put a program on the track: Commit iteration
**Commit iteration** is enabled only after a clean **Run** of exactly the text in the editor. A
warning blocks it as much as an error. If you edit after running, run again.

The wayside keeps its last five committed iterations. Open one from the **File explorer** to
read it; it opens read-only. The vital code can be read there too, as `vital.plc`.

#### Watch a wayside: the View tab
Pick a wayside in **Track controllers**. The tab shows its block occupancy, the commands it is
sending (track circuits, switches, signals, crossings), the CTC Office's suggestions and any
vital overrides. **Open in Program tab** jumps to that wayside's program.

#### Set a switch by hand
Only while the CTC Office has the system in maintenance mode.

1. In the **Program** tab press **Set switch manually**.
2. Pick the **Switch** and the **Position**, then press **Apply**.

The switch stays where you put it until you press **Release** or the CTC Office ends
maintenance mode. While the CTC Office itself commands that switch, its command wins.

### 5. Reading the screen

| On screen | Meaning |
|---|---|
| **NOT READY** in the header | A wayside has no committed program, or no track is loaded. Hover for what is missing. |
| **Maintenance · CTC** | The CTC Office has switched maintenance mode on. You cannot change it here. |
| **Test link** | A test UI is connected and driving the module. |
| **Paused**, **10×** | The shared clock is held, or running at ten times real speed. |
| **Running iteration #n** | The iteration executing on this wayside. The wayside runs the committed program, not the editor. |
| **Verified** | The editor's text ran clean and can be committed. |
| Block tiles: filled, hatched | Filled is occupied; hatched is closed by the CTC Office. |
| **READ ONLY** on the editor | You are looking at a committed iteration or `vital.plc`. |

### 6. PLC language reference

The full specification is in
[documents/sdd/track_ctrl_sw_plc_language.md](sdd/track_ctrl_sw_plc_language.md).
Summary below.

#### Syntax

| Element | Rule |
|---|---|
| Comment | `//` to the end of the line |
| Statement | one per line |
| Declarations | `VAR_IN NAME ...` for bits you read, `VAR_OUT NAME ...` for bits you drive |
| Range | `OCC_1..25` declares `OCC_1` to `OCC_25`. Declarations only; it cannot run backwards. |
| Assignment | `TARGET := expression` |
| Values | `0` and `1` only |
| Operators | `NOT`, then `AND`, then `XOR`, then `OR`, from tightest to loosest; parentheses group |
| Names | case-sensitive; a letter or `_`, then letters, digits or `_`. Keywords may be any case. |

`A OR B AND C` means `A OR (B AND C)`. When in doubt, use parentheses.

#### How a scan runs
- Once per tick the program runs top to bottom, exactly once.
- A name assigned on one line can be read on later lines only.
- A name you assign without declaring it is an intermediate. It lasts for the current scan only.
- Nothing is remembered between scans. To know where a switch is, read `SWREV_s`.
- An output you declare but never assign holds at 0. So an undriven `AUTH_n` stops its block.

#### Inputs a program can read

The names carry the block number, or the switch or crossing ID. A switch, its signal and a
crossing are each named by the block they are listed on. A wayside accepts only the names
for its own blocks and devices.

| Name | 1 when | From |
|---|---|---|
| `OCC_n` | block *n* is occupied. A train and a track failure read the same. | Track Model |
| `CLOSED_n` | the CTC Office has closed block *n* | CTC Office |
| `FAIL_n` | never; always 0. Kept so a hardware program that names it still loads. | — |
| `MAINT` | the CTC Office has maintenance mode on | CTC Office |
| `SWREV_s` | switch *s* reports reverse | Track Model |
| `CTCSW_s` | the CTC Office is commanding switch *s* (maintenance) | CTC Office |
| `CTCREV_s` | that command is reverse | CTC Office |
| `REQSW_s` | the CTC Office requests a position for switch *s* for a routed train | CTC Office |
| `REQREV_s` | that request is reverse | CTC Office |
| `PEER_OCC_n` | block *n* of another wayside is occupied. Only on waysides that guard a loop (GTC-01, GTC-02, GTC-06). | another wayside |
| `PEER_CNT_GTC04_0..4` | the number of GTC-04's occupied blocks, as five bits, least significant first. GTC-03 only. | GTC-04 |

#### Outputs a program drives

| Name | Meaning |
|---|---|
| `AUTH_n` | 1 passes the CTC Office's speed and authority to the train in block *n*. 0 sends speed 0 and authority 0. |
| `SW_s` | switch *s*: 1 reverse, 0 normal |
| `SIG_s_R`, `SIG_s_Y`, `SIG_s_G`, `SIG_s_SG` | the red, yellow, green and super green lights of signal *s*. Light exactly one. |
| `XING_c` | crossing *c*: 1 lights on and gates down |

A program never sees a speed or an authority number. It only decides whether each block passes
the CTC Office's values or stops.

#### What the vital code does after your program

Each rule below shows in **VITAL OVERRIDES** by the name given when it changes an output.

| Override | What it does |
|---|---|
| `closed_block` | A block the CTC Office closed gets speed 0 and authority 0. |
| `switch_moving` | A block whose switch is not yet where it was commanded is stopped. |
| `manual_switch` | A switch set by hand follows the hand-set position, not the program. |
| `switch_locked_under_train` | A switch with a train on its points block does not move. Nor does one with a train on its listed block, unless that train is commanded speed 0. |
| `signal_aspect` | A signal lighting no aspect, or more than one, shows red. |
| `signal_protects_block` | A signal whose own block is occupied or closed shows red. |
| `crossing_armed` | A crossing with a train on its approach is armed, whatever the program says. |
| `aspect_speed_cap` | A yellow signal halves the speed in its block. |
| `speed_clamped` | A suggested speed above the block's posted limit is cut to the limit. |

#### The starter programs
The generated starters (the files in `programs/green/`) set each switch in this
order: the CTC Office's maintenance command, a loop guard, the CTC Office's route request, then
their own rule. They hold a train whose next block is occupied.
[TrackCtrlSW/STARTER_LOG.md](../TrackCtrlSW/STARTER_LOG.md) records what they
do and how they have changed.

### 7. Messages and how to fix them

#### Parser messages

| Message | Fix |
|---|---|
| statement is not a declaration or an assignment | Use `:=` to assign, or start the line with `VAR_IN` or `VAR_OUT`. |
| *X* is an input and cannot be assigned | Assign to an output or a new name. Inputs come from the track. |
| missing closing parenthesis | Add the missing `)`. |
| *X* cannot be used as a value / unexpected *X* / cannot read *X* | Remove the stray word or character. Values are `0`, `1` or names. |
| VAR_IN declares nothing | List at least one name after `VAR_IN` or `VAR_OUT`. |
| range *a..b* runs backwards | Write the lower name first. |
| *X* is not an input of GTC-nn / is not an output of GTC-nn | Use only this wayside's own blocks and devices. Check the block range in the header. |
| *X* is declared more than once | Delete the second declaration. |
| *X* is assigned more than once; the last assignment in the scan wins | Combine the assignments into one. |
| *X* is read before it is assigned and is not a VAR_IN; it reads as 0 | Declare it as `VAR_IN`, or move the line that assigns it above the line that reads it. |
| output *X* is declared but never assigned; it will hold at 0 | Assign it, or remove it from `VAR_OUT`. |
| AUTH is not driven for block(s) … | Declare and assign `AUTH_n` for every block of the wayside. |
| *X* is not driven by this program | Declare and assign every output the wayside owns. |

#### Screen messages

| Message | What to do |
|---|---|
| COMMIT is blocked: *n* error(s), *m* warning(s) | Fix every message in the **Parser** pane, then press **Run** again. |
| Run this exact buffer first | You edited after the last run. Press **Run**. |
| No program is running on this wayside, so it transmits nothing | Run, then commit a program on this wayside. |
| No track is loaded | Press **Load track…** |
| Available while the CTC Office has maintenance mode on | Hand-setting a switch needs maintenance mode, which only the CTC Office can turn on. |

### 8. Testing with the test UI

Start the module, then `test_main.py`. The test UI connects over the **Test link** and plays the
CTC Office, the Track Model and the programmer. Only one test UI can connect at a time.

- **Target controller**: the wayside you are driving.
- **TRACK MODEL INPUTS**: set **Train present** on a block and the **Switch state** read-back.
- **CTC INPUTS**: **Close block**, the **Suggested speed** in MPH (sent as whole m/s, rounded
  down) and **Suggested authority** for a block, and **Maintenance mode**.
- **Controller outputs — live**: the commands the wayside sends, and its vital overrides.

A wayside sends a block's suggestion down its track circuit only once the wayside has a
committed program, and only while the program's `AUTH_n` for that block is 1.

### 9. Layout files: what the module reads

The module reads the same layout JSON as the Track Model
([green_line.json](../TrackModel/green_line.json),
[red_line.json](../TrackModel/red_line.json)). From each line it uses
`line` and `blocks`, and from each block:

| Field | Used for |
|---|---|
| `block_number` | the block ID in every PLC name |
| `section` | the section letter shown on the block tile |
| `length_m`, `grade_percent` | display |
| `speed_limit_kmh` | the posted limit the vital code clamps to |
| `next_blocks` | the direction of travel, used by the starters' separation and switch rules |
| `infrastructure.switch` | a switch listed on this block, written as its two connections, for example `"12-13; 1-13"` |
| `infrastructure.railway_crossing` | `true` for a crossing on this block |
| `infrastructure.station` | the station name, for display |

A file the module cannot read is refused with a message naming the file, the block and the
field.

### 10. Files

| Path | What it is |
|---|---|
| `TrackCtrlSW/programs/green/gtc0n_starter.plc` | the Green starter program for each wayside |
| `TrackCtrlSW/samples/gtc01_valid.plc`, `gtc01_invalid.plc` | a valid and an invalid program for GTC-01, for demonstrations |
| [TrackCtrlSW/STARTER_LOG.md](../TrackCtrlSW/STARTER_LOG.md) | what the starters do and how they changed |
| [documents/sdd/track_ctrl_sw_plc_language.md](sdd/track_ctrl_sw_plc_language.md) | the full language specification |

---

## Train Model — Help

For testers and Murphy: how to run the Train Model, read its window, inject
failures, and drive it from the test UI. For what each step computes, see
[TrainModel/docs/physics.md](../TrainModel/docs/physics.md). For the module
boundary, see
[TrainModel/docs/module-interface.md](../TrainModel/docs/module-interface.md).

### The two windows

| Window | What it does | Who uses it |
|---|---|---|
| Train Model | Shows one train's state. Holds the failure buttons and the passenger emergency brake. | Murphy, testers, the demo |
| Train Model Test UI | Stands in for the Track Model, the Train Controller and the clock. Sends inputs and reads outputs. | Testers only. Removed at integration. |

Each window is its own program. Close one and the other keeps running.

### Start

1. Open a terminal in `TrainModel/` and activate the virtual environment.
2. Start the Train Model: `python main.py`
3. In a second terminal, start the test UI: `python test_ui.py`

The test UI loads the Blue Line by default. To load another line, add
`--line red` or `--line green`. To pick the blocks to travel, add
`--route 9-1,16-66`. Run `python test_ui.py --help` for every option.

From a build, run `main.exe` and `test_ui.exe` instead.

### Read the Train Model window

The header shows the train selector, Running or Paused, the line and the
clock. Running means steps are arriving. Paused means they stopped.

| Card | Shows |
|---|---|
| Lights | Interior and exterior lights, On or Off. |
| Speed & Authority | Actual speed, commanded speed and speed limit in mph. Authority in blocks. Acceleration in ft/s². Grade in degrees. |
| Cabin & Load | Passengers out of capacity (222). Loaded mass in tons. Cabin temperature in °F. Crew, train size, empty mass. Power command is the power the train was told to use, out of 480 kW. It is not the power consumed. |
| Brakes & Doors | Emergency brake status, the Apply emergency brake button, left and right doors, service brake. |
| Position | Direction and the last block change, current block, offset into the block in ft, the station in this block, and the next station with its platform side. |
| Failure Modes | One button per failure. The card header reads Clear or N active. |

A dash (—) under Commanded or Authority means the train has no valid reading.
This is what a signal pickup failure looks like.

Announcements from the Train Controller open a popup. Click Dismiss or press
Escape to close it. The same announcement does not reopen it.

### Inject a failure

1. In the Train Model window, find Failure Modes.
2. Click Induce Engine failure, Induce Brake failure or Induce Signal
   pickup failure. The button turns red and reads Clear.
3. To end the failure, click the red Clear button.

Any combination of failures can be active. A failure stays set until you
clear it or reset the module. Failures are set only in the Train Model
window. The test UI shows their effect, not which ones are set.

| Failure | What happens | What you see |
|---|---|---|
| Engine | The motors give no traction. The train coasts and slows. | Power command reads 0 kW. |
| Brake | The service brake does nothing. The emergency brake still works. | The train does not slow when the service brake is applied. |
| Signal pickup | No new commanded speed or authority reaches the train. Grade, speed limit and other track data still arrive. | Commanded and Authority show —. |

### Pull the passenger emergency brake

1. Click Apply emergency brake.
2. Click CONFIRM. The emergency brake applies at full rate.

The button is disabled while any emergency brake is applied. A passenger
cannot release the brake. The Train Controller releases it by sending
emergency brake on, then off.

In the test UI, to release it yourself: set `emergency_brake_command` to
off, even if it is already off, and click Send inputs to train model.

### Drive the train from the test UI

The test UI starts with a train at rest, lights on, doors closed and the
cabin set to 70 °F. You can send the first tick without typing anything.

1. Edit an input row. The row is marked pending.
2. Click Send inputs to train model. This sends every pending edit and
   advances one tick.
3. To keep running, set Clock to Run. Each tick reuses the last sent inputs.
   Set it to Hold to stop.
4. To step one tick at a time, click Advance one tick.
5. To run ten times faster, set Speed to 10x.
6. To start over, click Reset module. This clears the train, failures,
   pending edits and elapsed time.

Rows that are not pending show the train's live values. Brakes, lights,
doors, commanded speed and authority read back from the train.

Run control also shows:

- Track: the line loaded for the stand-in track, or Manual when you type
  the track rows yourself.
- Speed limiter: the speed cap, and limiting when it is cutting power. The
  test UI keeps the train under the speed limit, as the Train Controller
  will.
- Station dwell: seconds left of the 45 s stop. During dwell the test UI
  holds the train with doors open, whatever you enter.
- Tick, dt and Elapsed: the clock.

### Board passengers

1. Bring the train to rest at a station.
2. Open a door: set `left_door_command` or `right_door_command` on and
   send.
3. Enter a count in `passengers_boarded` and send.

The count boards once and the row returns to 0. If the train is moving or
the doors are closed, the count waits in its row until it can board.
Passengers leave once per stop, when the train first stops with a door
open.

### Run several trains

- Click Add train in the test UI header to put a new train in service. It
  becomes the selected train.
- Pick a train in the Train selector to see and edit its rows. Every train
  steps each tick, shown or not.
- Click Remove train to take the selected train out of service. You cannot
  remove the last train.
- The Train Model window has its own Train selector.

### Messages

| Message | Meaning | What to do |
|---|---|---|
| Not connected | The test UI cannot reach the Train Model. | Start main.py. The test UI reconnects on its own. |
| Another test UI open | A second test UI is already driving this Train Model. | Close the other test UI. This one takes over. |
| Inputs not sent: followed by a reason | An input has no physical meaning, such as negative power or a negative boarding count. Nothing changed and the clock paused. | Fix the row the reason names and send again. Your other edits are kept. |
| Clock drift (either window) | The Train Model is behind the shared clock. | Standalone: click Reset module in the test UI. Integrated: report it to the Train Model owner. |
| Paused in the Train Model header | No steps are arriving. | Set Clock to Run in the test UI, or check that the test UI is connected. |

### Units

Both windows show speed in mph, distance in feet, temperature in °F, mass
in tons, power in kW, and grade in degrees. Type test UI inputs in the same
units. The Train Model works in SI internally.

---

## Train Controller — User Help

Help for the Track Overflow Train Controller (HW and SW variants).

- **Who it is for:** the Train Driver and the Engineer. Testers should read
  §9 as well.
- **Same screen, two variants:** the SW Train Controller looks and works the
  same. It drives Green Line trains; the HW one drives Red Line trains.

### Quick reference

| To… | Do this |
|---|---|
| Start a new train | Engineer: sign in, check Kp and Ki, press **Set gains** (§3) |
| Drive it yourself | Sign in as **Driver**, pick **Manual**, drag the speed dial (§4) |
| Let the CTC drive | Pick **Automatic** (§5) |
| Slow down or stop | Press **Service brake**. Press again to release |
| Stop now | Press **Emergency brake**. Release it only when stopped (§6) |
| Open doors | Stop the train, then press **Open left** or **Open right** |
| Change cabin temperature | Drag the thermostat, 60–80 °F |
| See a fault | Read the red badges at the top (§7) |

### 1. Safety

- **The emergency brake latches.** Only the driver can release it, and only
  once the train has stopped.
- **Any fault stops the train.** The controller applies the emergency brake
  by itself. You cannot drive until the fault clears.
- **Doors open only when the train is stopped.** They close if the train
  starts moving.
- **The commanded speed is the limit.** Your target speed is capped at it,
  in both modes. Keeping trains under the track's speed limit is the
  wayside's job.
- **Authority 0 means stop.** When **Stop in** reads 0 blocks, the train
  brakes to a stand.

### 2. Start up

The Train Controller opens on its own when the Track Overflow system
starts. The HW variant runs its control core on a Raspberry Pi connected by
USB. Setting up the Pi is covered in
[pi-owner-setup.md](pi-owner-setup.md).

To run the Train Controller on its own, from `Train-Ctrl_HW/`:

```
python main.py --test
```

This opens the test bench (§9). Spawn a train there to open its console.

#### The screen

> Figure: console before sign-in, waiting for gains —
> `Train-Ctrl_HW/docs/user-help-figures/train-controller/01-signed-out.png`
> *(not yet committed to the repo at time of writing)*

The **top bar** always shows:

- the module name, the train number, and the mode badge
  (**AUTOMATIC** or **MANUAL**);
- fault badges, such as **E-BRAKE** or **BRAKE FAULT**, while they apply;
- the system clock, on the right.

The **operator bar** below it has the **Operator** switch, the
**Operating mode** switch, the gains badge, and **Current selected train**.

### 3. Engineer: set the control gains

A new train will not move until the engineer sets its gains. Until then the
console shows "*train* is waiting for its gains" and a **GAINS MISSING**
badge. The driver cannot sign in to that train.

> Figure: control gains dialog —
> `Train-Ctrl_HW/docs/user-help-figures/train-controller/02-gains.png`

1. Pick the train in **Current selected train**.
2. Under **Operator**, press **Engineer**. The **Control gains** dialog opens.
3. Check **Proportional gain, Kp** and **Integral gain, Ki**. The defaults
   are 400000 and 8000. Type a value, or use **−** and **+**.
4. Press **Set gains**. The badge turns to **GAINS SET**.
5. Press **Back to driver**.

Gains are set **once per train**. They cannot be changed afterwards.
Gains only change how quickly the train reaches its speed. They never
change whether it stops.

| Message | What to do |
|---|---|
| Kp and Ki must be numbers. | Type digits only, then press **Set gains**. |
| Kp and Ki cannot be negative. | Enter 0 or more. |
| The train did not confirm the gains. Press Set gains again. | Press **Set gains** again. If it keeps failing, check the Pi's USB link. |

### 4. Driver: drive in Manual

> Figure: driving in Manual —
> `Train-Ctrl_HW/docs/user-help-figures/train-controller/03-driving.png`

1. Under **Operator**, press **Driver**.
2. Under **Operating mode**, press **Manual**.
3. Drag the **Speed** dial to set your **target speed**. It moves in
   0.1 mph steps, up to 43.5 mph.
4. Watch the top row:
   - **Your speed** — how fast the train is going.
   - **Commanded speed** — the most the track allows now.
   - **Cabin temperature** — the temperature inside, in °F.
   - **Stop in** — blocks you may still travel.

If the commanded speed drops below your target, the train slows to it.
When it rises again, the train returns to your target, no higher.
A stop clears your target, so set a new one to move off again.

**Brakes**

- **Service brake** slows the train. Press **Release service brake** to
  let it go.
- **Emergency brake** stops the train fast. See §6.

**Cab controls**

- **Open left / Open right** — at a stand only. Greyed out while moving.
  The badge reads **DOORS FREE** or **DOORS LOCKED**.
- **Thermostat** — drag to set 60–80 °F. It reads **HEATING**, **COOLING**
  or **HOLDING**.
- **Interior on/off** and **Exterior on/off** — cabin lights and headlights.
  Lights also switch on by themselves underground and from 18:00 to 06:00.
  Your choice stands until the next of those changes.

**Announcements**

The controller sends "arriving soon", "arrived" and "departing"
announcements by itself. In Manual, **Repeat last announcement** plays the
last one again.

**Next signal** shows the light ahead (for example, **YELLOW — Slow down**)
when the train enters a signal block.

### 5. Automatic mode

In **Automatic**, the train follows the commanded speed from the CTC
Office. The dial reads "Set by the CTC. Switch to Manual to take control."

- Brakes, doors, lights and announcements are run by the controller.
- The **Emergency brake** stays available to the driver.
- You can switch to **Manual** at any time, even during a fault.

### 6. Emergency brake

> Figure: emergency brake engaged —
> `Train-Ctrl_HW/docs/user-help-figures/train-controller/04-ebrake.png`

1. Press **Emergency brake**. The **E-BRAKE** badge appears and the button
   turns into **Release emergency brake**.
2. Wait until **Your speed** reads 0.0.
3. Press **Release emergency brake**.
4. In Manual, set a new target speed.

A passenger can also pull the emergency brake from the train. Only you can
release it.

| Message | Meaning |
|---|---|
| Cannot release: the train is still moving. | Wait for a full stop. |
| Cannot release: waiting for a safe power command. | A vitality breach is still active (§7). Wait for it to clear. |
| Emergency brake engaged: rollback detected. | The train rolled backwards with no brake asked for. |
| Emergency brake engaged: runaway detected. | The train moved under a brake fault. |

### 7. Faults

The controller finds faults on its own. Each one shows a red badge in the
top bar and applies the emergency brake. There is no reset button: the
badge clears when the controller sees the fault is fixed.

> Figure: brake fault —
> `Train-Ctrl_HW/docs/user-help-figures/train-controller/06-failure.png`

| Badge | What happened | What you do |
|---|---|---|
| **BRAKE FAULT** | The service brake did not apply when commanded. | Press **Service brake** again. When it applies, the fault clears. Then release the emergency brake. |
| **ENGINE FAULT** | The train lost power. | Stop, then release the emergency brake. The controller tests the engine for about 2 s. If it still fails, the train is held and retested every 10 s. |
| **SIGNAL PICKUP FAULT** | The train lost the track signal. Speed and authority show "--". | Wait. It clears when the signal returns. Then release the emergency brake. |
| **VITALITY BREACH** | The three power calculations disagreed. 0 W was sent. | Wait. It clears on the next good calculation. Then release the emergency brake. |

The **Speed** panel says what is holding the train, for example "Brake
failure. Driving resumes once it clears."

### 8. Stations

> Figure: station dwell —
> `Train-Ctrl_HW/docs/user-help-figures/train-controller/11-station-dwell.png`

When the train stops at a station, with authority 0:

1. The platform-side doors open by themselves.
2. A **STATION DWELL** badge counts down 45 s. The train is held and the
   doors stay open.
3. The doors close by themselves.
4. When a new commanded speed and authority arrive, the train departs.
   In Manual, set a target speed.

After the dwell, in Manual, you may open and close the platform side until
the new commands arrive.

### 9. Test bench (testers)

The bench stands in for the rest of the system when the Train Controller
runs alone. It feeds the same inputs the Train Model and Track Model would.

> Figure: test bench —
> `Train-Ctrl_HW/docs/user-help-figures/train-controller/07-test.png`

1. Enter a **Number**, pick a **Line**, and press **Spawn train**.
   A Red Line train opens the HW console; a Green Line train opens the SW one.
2. Edit values under **Inputs**, then press **Send to controller**.
3. Toggle **Injected failures** to test fault handling (§7).
4. Press **Block change** to pass one block (authority goes down by 1).
5. Use **Pause**, **1x / 10x**, and **Set time** to control the clock.

**Outputs to Train Model** shows what the controller sends each tick.

### 10. Help and contact

- Requirements and rules:
  [Train-Ctrl_HW/REQUIREMENTS.md](../Train-Ctrl_HW/REQUIREMENTS.md)
- Known issues:
  [Train-Ctrl_HW/OPEN_ISSUES.md](../Train-Ctrl_HW/OPEN_ISSUES.md)
- Contact: **[placeholder — module owner name and contact]**
