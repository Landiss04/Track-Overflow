# Track Controller — PLC Program Help

This is the Help File for the wayside PLC language, written for the Programmer
persona (`documents/srs-filled.md` §2.3) and anyone reading this window who
needs to understand what a wayside is actually running. For the window's
day-to-day controls, see the tooltips in the UI itself and
`TrackCtrlHw/README.md`.

## What a wayside program is

Each wayside runs one Boolean-only PLC program, loaded from a `.plc` text
file (see `data/plc/` for real examples). The language is shared with the
software Track Controller variant (REQ-INTF-009) — same syntax, independently
implemented, so a bug in one implementation is unlikely to exist in the other.

## Syntax, in brief

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
  in advance, so check the **warnings** list in the PLC program details
  dialog (the "i" button next to **New PLC**) before trusting a scan result.

## How a scan is checked

Every statement compiles twice, by two different algorithms (recursive
descent and shunting-yard), run independently on every scan. Any
disagreement between them is a **channel fault**: the wayside holds every
output fail-safe until a new program is loaded. If the window's header shows
a **Channel fault** badge, that's what it means — not a wiring problem, a
disagreement between the program's two compiled forms.

## Reading the window against the program

- **Switches panel → Agreement column**: compares the switch's reported
  position against what the program (`SW_n`) commanded. A mismatch usually
  means the physical/simulated switch hasn't finished moving yet, or has
  failed to move.
- **Switches/Signals panels → CTC asks / Set by columns**: the CTC Office's
  request is an *input* to the program (e.g. `CTCSW_12`, `CTCREV_12`); the
  program decides whether to honor it. "Set by" shows whether the last
  output change came from the running program or from the wayside's
  fail-safe default (not ready / channel fault).
- **From the office panel**: the CTC Office's suggested speed/authority
  arrive as the program's `SPD_n_*` inputs; the program's `CMD_n_*` /
  `AUTH_n` outputs are what it actually commands, capped at the block's own
  speed limit.

## Where to look next

- A full annotated example: `TrackCtrlHw/data/plc/green_wayside_1.plc`
- The language's formal grammar: module docstring in
  `TrackCtrlHw/track_ctrl_hw/plc.py`
- Window-level help strategy this file is part of:
  `documents/user-help-strategy.md`
