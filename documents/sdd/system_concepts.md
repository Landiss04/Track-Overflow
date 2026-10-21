# Key System-Wide Design Concepts (SDD 1.1) — draft

Draft for Braden, Harry Tye and Landis to complete together. Each concept says what the
design is and which decision or entry on the `truth` branch it rests on. Paragraphs marked
**To complete** need the owner named.

| | |
|---|---|
| **Status** | Draft for WP2 and the design review, 2026-10-22 |
| **Sources** | `truth` decisions D005, D006, D013, D017, D020 to D027; signals `suggested-authority`, `track-signal`; arbitration entries; `TrackCtrlHw/README.md`; `TrackCtrlSW/README.md` |

---

## 1. Route

A train's route is the sequence of blocks it runs, from its line's yard to its scheduled
stations in track order and back to the yard (D020, D022).

- **The CTC Office owns the route.** It releases a train from the yard at the line's exit
  block (Green 63, Red 9), sends it to each scheduled station in the order the track reaches
  them, and retires it at the yard entry block (Green 57, Red 9).
- **The track's topology is in the layout file.** Each block's `next_blocks` lists where a
  train in it may go next, which gives the direction of travel; `"yard"` marks the way into
  the yard. Switches choose between the two legs where the track divides.
- **The waysides set the switches, not the CTC Office.** Outside maintenance mode, every
  switch moves only by its wayside's PLC program, which knows blocks, never trains or their
  destinations. A program therefore sets a switch from the pattern of occupancy (for
  example, a train waiting on a loop block). The CTC Office commands a switch only in
  maintenance mode.
- **A route follows the switches as they lie.** The CTC Office computes authority along the
  route through the current switch positions, which the waysides report every tick
  (`arbitration/authority-stops-before-obstruction`): a switch not set for the train's route
  cuts its authority short.

**To complete (Landis):** how the CTC Office picks a route where the track divides, and what
it does when a wayside's switch is not set for it (`arbitration/reroute-around-blockage`).

**Open:** with switches set only from occupancy, a train may wait at a switch that no
program will throw for it. The waysides' programs and the CTC Office's routes must agree on
each switch's rule.

---

## 2. Authority

Authority is **the number of blocks ahead of the train's current block that it may still
enter** before it must stop, a non-negative integer, everywhere in the system (D013).
0 means stop before leaving the current block.

1. **The CTC Office computes it** along the train's route, never into an occupied, closed or
   failed block, or over a switch not set for the route
   (`arbitration/authority-stops-before-obstruction`). No block is ever within two trains'
   authority (`arbitration/exclusive-authority`).
2. **It suggests it per block.** For each train: one value for the block it is in and, while
   that value is at least 1, one for the next block on its route, one less
   (`signals/suggested-authority`). The harness drops the train ID: the Track Controller
   sees only blocks.
3. **The wayside passes it on or withholds it.** Its PLC program sets `AUTH_n` per block: 1
   sends the CTC Office's count down that block's track circuit, 0 sends authority 0 and
   speed 0. The program withholds it for a closed block, a switch that does not report
   where it was commanded, or an occupied neighbour.
4. **The Track Model delivers it** to the train in that block, then clears the block's values
   to zero (`signals/track-signal`).
5. **The Train Controller enforces it**, braking to stop within it.

Speed travels with authority: the CTC Office suggests it under the block's limit and so
that the train can stop within its authority
(`arbitration/suggested-speed-under-block-limit`,
`arbitration/suggested-speed-stops-within-authority`); the wayside caps it again at the
block's limit.

---

## 3. Distribution of wayside controllers

| Line | Variant | Runs on | Waysides |
|---|---|---|---|
| Green | Track Controller SW | Host PC | 6 by default; the count is set when the line is loaded (at least 2) |
| Red | Track Controller HW | One Raspberry Pi 5 over USB | One per database file; boundaries to be chosen |

- **One variant per line** (D021). Each runs every wayside of its line. A Train Controller
  follows the same split: a train on the Green Line gets the software Train Controller, on
  the Red Line the hardware one.
- **A wayside owns a contiguous run of blocks**, with every switch, signal and crossing on
  them. Each has its own database and its own PLC program, written for its own inputs and
  outputs.
- **A line runs only when every wayside on it is ready.** A wayside is ready once a person
  has loaded both its database and its PLC program, and its channels agree. While any
  wayside of a line is not ready, every wayside of that line holds fail-safe, and the CTC
  Office dispatches nothing on it (D022). The other line keeps running.
- **Fewer waysides cost less** (meeting 006). The minimum is set by the PLC: each program
  must stay small enough to read and check.

**To complete (Braden):** the Red Line's boundaries. Constraint: a switch's point and its
listed block must lie in one wayside.

---

## 4. Simulation timing

- **One clock, in the harness** (D017). Every tick, the harness sends dt and the simulation
  time straight to every module; a module sees only the inputs of that tick (outputs of the
  previous one).
- **Fixed step** (D006, D017): dt is 0.1 s at every speed. 10x changes how often ticks come,
  never how long a tick is, so the same inputs give the same results at 1x and 10x.
- **1x and 10x, and pause**, set by the CTC Office through the harness.
- **The harness waits** for every module's reply before the next tick, and pauses the clock
  if a reply takes longer than about 1 s.
- **Consequence for the hardware variants:** at 10x the harness sends 100 ticks per real
  second, so a hardware variant's USB round trip and scan must stay under 10 ms.
- **The PLC scans once per tick**, every wayside. A program has no timers and no memory
  between scans.

---

## 5. Vitality

The communication channels between the CTC Office, the waysides and the trains are
non-vital (REQ-INTF-021); the Track Controller and the Train Controller themselves are
vital (REQ-FUNC-058, REQ-FUNC-037). The wayside's vitality comes from these layers:

1. **The operating system only holds and parses the PLC program.** Every decision is PLC
   code, which the programmer can read (the professor, Iteration 2).
2. **A read-only vital block** (design assumption, pending Harry Tye). Each wayside runs a
   fixed PLC block, generated from its territory, after the user's program. It can only make
   an output more restrictive: zero authority on a closed block, cap the speed at the
   block's limit, lock a switch under a train, turn a signal red on an occupied or closed
   block, activate a crossing for a train beside it. A wrong user program then stops trains;
   it cannot put two in one block.
3. **Diverse execution** (hardware variant). Every statement is compiled twice, by two
   different algorithms, and both run every scan. If they disagree, the wayside holds every
   output fail-safe until a new program is loaded.
4. **Diverse implementations.** The two variants share a language and an interface, but not
   code: each implementation was written separately.
5. **Fail-safe outputs.** No program, a program that has not scanned yet, a channel fault, or
   another wayside not ready: every signal red, every crossing active, speed and authority 0,
   switches left where they are. Switches stay put because moving one is not a safe way to
   fail.
6. **Checked inputs.** A bad tick is rejected whole, before any state changes; a bad program
   or database never loads.
7. **The CTC Office never gives two trains one block** (`arbitration/exclusive-authority`), and
   the wayside's program withholds authority it cannot confirm. A failure reads as
   occupancy, so it is protected like a train.

**To complete (Harry Tye):** the software variant's form of layers 2 and 3.
**Train-side vitality** belongs to the Train Controller owners.

---

## 6. Wayside language

A Boolean-only PLC language shared by both variants (REQ-FUNC-051; pending proposal D016),
each with its own implementation.

```
// a comment
VAR_IN   OCC_1..20 CLOSED_13 SWREV_12 CTCSW_12 CTCREV_12 SPD_3_0..4
VAR_OUT  AUTH_1..20 SW_12 SIG_12_R SIG_12_Y SIG_12_G SIG_12_SG XING_19 CMD_3_0..4
LOCK_12 := OCC_12 OR OCC_13
SW_12   := (LOCK_12 AND SWREV_12) OR (NOT LOCK_12 AND (CTCSW_12 AND CTCREV_12))
```

- **Grammar.** `VAR_IN`, `VAR_OUT` and `NAME := expression`. Operators `NOT`, `AND`, `XOR`,
  `OR` (in that binding order), constants `0` and `1`, parentheses. Ranges such as
  `OCC_1..20`.
- **Scan.** Assignments run top to bottom, once per tick. A name not yet set reads 0, which
  is the restrictive value, and the compiler warns about it.
- **Inputs, per block n or switch s:** `OCC_n`, `CLOSED_n`, `SPD_n_0..4` (the CTC Office's speed,
  five bits, 1 to 16 m/s), `SWREV_s` (the switch reports reverse), `CTCSW_s` and `CTCREV_s`
  (the CTC Office's maintenance command).
- **Outputs:** `AUTH_n`, `CMD_n_0..4` (speed sent, five bits), `SW_s`, `SIG_s_R` / `_Y` / `_G`
  / `_SG`, `XING_c`.
- **Numbers as bits.** Speed crosses into and out of the program as five bits, so the
  program can compare it with the block's limit in Boolean logic.
- **Checks at load.** Every line with an error is reported with its line number; a program
  that names anything its wayside does not have is refused.

**Open:** the variants still use different names (the software variant uses `MAINT` and has no
speed bits), so one program file does not yet load on both (REQ-INTF-009).

---

## 7. Hardware/software interface

- **Same interface.** Each variant implements the same `TrackController` Protocol and
  exchanges the same inputs and outputs with the harness; the harness cannot tell them
  apart (D021).
- **Where the hardware runs.** Each hardware variant's core runs on its own Raspberry Pi; its
  window runs on the PC (D021, D027).
- **The link.** One USB cable. The Pi runs in USB device mode as a standard USB serial
  device (CDC-ACM), which Windows drives with its built-in driver: no installation, no admin
  rights. The PC finds the Pi by its USB identity, never a fixed COM number, and the Pi
  states on connecting which module it runs (D027).
- **The messages.** The same newline-delimited JSON the harness exchanges with every module,
  each with a request ID and the tick (D005). The module's process on the PC owns the serial
  port and relays the harness's messages to the Pi and the replies back.
- **If a Pi is unplugged**, its replies stop and the harness pauses the clock and names the
  module (D027).

**Open:** the message framing (Kevin); power for a Pi 5 through the same USB-C port.
