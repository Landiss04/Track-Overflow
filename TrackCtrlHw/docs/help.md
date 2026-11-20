# Track Controller (hardware) — Help

Consolidated Help File for this module, per `documents/user-help-strategy.md`
§5. Covers the window's panels, the PLC language a wayside runs, and how to
read the two against each other. For install/run instructions and the
module's internal architecture, see `TrackCtrlHw/README.md`.

## 1. What this module is

The hardware Track Controller runs every wayside of one line (the software
variant runs the other). Each wayside owns a contiguous run of blocks, loaded
from a database file, and runs its own Boolean PLC program loaded from a
`.plc` file. The module knows the blocks it governs, never the trains on
them — it reports occupancy, switch, signal and crossing state upward to the
CTC Office, keyed by block.

## 2. Reading the window

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

## 3. The PLC language a wayside runs

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
- A full annotated example: `TrackCtrlHw/data/plc/green_wayside_1.plc`.
  The formal grammar is the module docstring in
  `TrackCtrlHw/track_ctrl_hw/plc.py`.

## 4. PLC program details dialog

Opened from the **i** button beside **New PLC**.

| Field | Meaning |
|---|---|
| Checksum (CRC-32) | For confirming two waysides run the identical program file — not for diagnosing program behavior. |
| Scan overruns since load | Should stay `0`. Nonzero means a scan took longer than the scan interval. |
| Boolean variables / Statements | Size of the compiled program. |
| Scan interval / Last scan / Scan time | Timing of the two-channel scan described in §5. |

## 5. How a scan is checked (the diverse-channel guarantee)

Every statement compiles twice, by two different algorithms — recursive
descent (Channel A) and shunting-yard (Channel B) — run independently on
every scan. Any disagreement between them is a **channel fault**: see the
header badge in §2.

## 6. Troubleshooting

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
