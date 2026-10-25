# Key System-Wide Design Concepts

The concepts every module's design rests on. Each states the design and the decision or
`truth` entry behind it; a module's own detail stays in its chapter. Consolidated from the
Track Controller, CTC Office, Track Model and Train Controller drafts.

---

## 1. Route

A train's route is the sequence of blocks it runs from its line's yard to its scheduled
stations, in the order the track reaches them, and back to the yard (D020, D022).

- **The CTC Office plans it.** It finds the shortest route the train can run on a graph built
  from each block's `next_blocks` and each switch's two legs. A route never turns a train back.
  It goes round closed, closing and failed blocks and trains that are not moving, preferring a
  way round both, then round unusable blocks only; no detour is more than twice the shortest.
  When only reversing would get round, the train waits and the dispatcher is alerted
  (`arbitration/reroute-around-blockage`).
- **The route is never sent as one object.** The CTC Office expresses it as a suggested speed
  and authority for the block the train is in and the next block on its route.
- **The waysides set the switches.** Outside maintenance mode only the waysides' PLC programs
  move switches; the CTC Office commands a switch only in maintenance mode, and never one
  whose block is occupied (`arbitration/no-switch-under-train`). Authority stops at the block
  before a switch not reported set for the route, and grows once the wayside sets it.
- **The Track Model never routes.** A train follows the rails as the switches lie; a switch
  set wrong sends it where the track leads, as on a real railway.

---

## 2. Authority

Authority is **the number of blocks ahead of the train's current block that it may still
enter** before it must stop, a non-negative integer, everywhere in the system (D013).
0 means stop before leaving the current block.

| Module | Role |
|---|---|
| CTC Office | Computes it along the route, never into a block that is occupied, closed, closing, failed or within another train's authority (`arbitration/exclusive-authority`). Suggests it per block, with a speed the train can stop from: √(2 × 1.2 m/s² × d), and 1 m/s under the block's limit. |
| Harness | Maps each train's suggestions to per-block values and drops the train ID. |
| Track Controller | The PLC program's `AUTH_n` passes block n's authority down its track circuit or sends 0; every speed bit is ANDed with it, so withheld authority sends no speed. |
| Track Model | Holds each block's speed and authority as that block's track-circuit signal, delivers it to the train in the block, then clears it to zero. A block never commanded, or with a failed circuit, carries 0 and 0. |
| Train Controller | Uses the count it receives and never counts down itself. At 0 it targets 0 and brakes while moving; at 3 it announces arrival. A drop of speed and authority to 0 together from 2 or more blocks is read as a signal pickup failure. |

Speed and authority are per block, not per train, like the signal in the rails.

---

## 3. Distribution of wayside controllers

| Line | Variant | Runs on | Waysides |
|---|---|---|---|
| Green | Track Controller SW | Host PC | 6 by default; the count is set when the line is loaded (2 up to one per block) |
| Red | Track Controller HW | One Raspberry Pi 5 over USB | 3, proposed: Red-1 blocks 1–24 and 73–76, Red-2 25–45 and 67–72, Red-3 46–66 (awaiting approval) |

- **One variant per line** (D021). The Train Controller follows the same split: a train on the
  Green Line gets the software Train Controller, on the Red Line the hardware one.
- **A wayside owns a contiguous run of blocks**, with every switch, signal and crossing listed
  on them; a switch's point stays in the same wayside. Each wayside has its own database and
  its own PLC program.
- **A line runs only when every wayside on it is ready**: a person has loaded its database and
  its PLC program, and its channels agree. While any wayside of a line is not ready, every
  wayside of that line holds fail-safe and the CTC Office dispatches nothing on it (D022). The
  other line keeps running.
- **Nothing outside the Track Controller depends on the split.** Every other module's inputs
  and outputs are keyed by block, switch or crossing, never by wayside, so the boundaries can
  change without touching them.

---

## 4. Simulation timing

- **One clock, in the harness** (D017). `SystemClock` is the only clock. Every tick the harness
  sends dt and the simulation time to every module; time counts from 05:00:00 without
  wrapping. A module steps on the inputs of that tick, which are the outputs of the tick before.
- **Fixed step** (D006, D017): dt is 0.1 s at every speed. 1x is 10 ticks per real second and 10x
  is 100, so the same inputs give the same results at both.
- **Pause and speed** are the CTC Office's, sent through the harness.
- **The harness waits** for every module's reply before the next tick, and pauses the clock and
  names the module if a reply takes longer than about 1 s.
- **Consequences.** A command reaches the train a few ticks after the decision that caused it
  (system interaction view). At 10x a hardware variant's USB round trip plus its scan must
  stay under 10 ms. The PLC scans once per tick and keeps no memory between scans. Time-of-day
  rules (announcements held 5 s; train lights on at 18:00 and off at 06:00) read the shared
  clock.

---

## 5. Vitality

The channels between the CTC Office, the waysides and the trains are non-vital
(REQ-INTF-021); the Track Controller and the Train Controller are vital (REQ-FUNC-058,
REQ-FUNC-037). Each vital module therefore checks what it is given, and fails to a safe state.

**Track Controller (wayside)**

1. **The operating system only holds and parses the PLC program**; every protection is PLC
   code the programmer can read (the professor, Iteration 2; Kevin Schillinger, K3b).
2. **Read-only vital block** (design assumption, pending Harry Tye): a fixed PLC block
   generated per territory and run after the user's program, which can only make outputs more
   restrictive. The software variant implements the same rules today as a Python supervisor,
   to be moved into PLC code.
3. **Diverse execution** (hardware variant): every statement is compiled twice, by different
   algorithms, and both run every scan; a disagreement holds every output until a new program
   is loaded.
4. **Diverse implementations**: the two variants share a language and an interface, not code.
5. **Fail-safe outputs**: no program, a program that has not scanned yet, a channel fault, or
   another wayside not ready: every signal red, every crossing active, speed and authority 0,
   switches left where they stand.

**Train Controller**

- Every input every tick, validated all or nothing; a bad value leaves every train unchanged.
- Failures inferred from returned signals latch the emergency brake and set the target to 0.
- No traction while any brake is commanded (`arbitration/traction-cut-under-braking`); service
  brake at authority 0 while moving; the commanded speed is the only cap in both modes.
- No power until the engineer commissions the gains (D024); the emergency brake is released
  only by the driver, at a stand.

**System**

- A failure reads as occupancy, so it is protected like a train; its track circuit carries 0.
- The CTC Office never gives two trains one block (`arbitration/exclusive-authority`).
- Every module rejects an invalid tick whole, before any state changes.

---

## 6. Wayside language

A Boolean-only PLC language shared by both Track Controller variants (REQ-FUNC-051; pending
proposal D016), each with its own implementation.

```
// a comment
VAR_IN   OCC_12 OCC_13 SWREV_12 CTCSW_12 CTCREV_12
VAR_OUT  SW_12
LOCK_12 := OCC_12 OR OCC_13
WANT_12 := CTCSW_12 AND CTCREV_12
SW_12   := (LOCK_12 AND SWREV_12) OR (NOT LOCK_12 AND WANT_12)
```

- **Grammar.** `VAR_IN`, `VAR_OUT` and `NAME := expression`; operators `NOT`, `AND`, `XOR`,
  `OR` (in that binding order), constants `0` and `1`, parentheses; ranges such as `OCC_1..20`.
  There are no numbers, so a scan always ends in bounded time.
- **Scan.** Assignments run top to bottom, once per tick. A name not yet set reads 0, the
  restrictive value, and the compiler warns about it.
- **Inputs**, per block n or switch s: `OCC_n`, `CLOSED_n`, `SPD_n_0..4` (the CTC Office's speed
  as five bits, 1 to 16 m/s), `SWREV_s`, and the maintenance command `CTCSW_s`, `CTCREV_s`.
- **Outputs**: `AUTH_n`, `CMD_n_0..4` (the speed sent, five bits), `SW_s`, signal aspects
  `SIG_s_R` / `_Y` / `_G` / `_SG`, crossing `XING_c`.
- **Checks at load.** Every line with an error is reported with its line number; a program
  that names anything its wayside does not have is refused.
- **Open.** The variants' names are not yet identical (the software variant keeps `MAINT`), so
  one program file does not yet load on both (REQ-INTF-009).

---

## 7. Hardware/software interface

- **Same interface.** A module's software and hardware variants implement the same Protocol
  and exchange the same inputs and outputs; the harness cannot tell them apart (D021).
- **Where the hardware runs.** Each hardware variant's core runs on its own Raspberry Pi 5: one
  for the Track Controller (every Red Line wayside), one for the Train Controller (every Red
  Line train). Its window runs on the host PC (D021, D027).
- **The link.** One USB cable. Each Pi runs in USB device mode as a standard USB serial
  (CDC-ACM) device, which Windows drives with its built-in driver. The host finds it by its USB
  product name, never a fixed COM number (D027).
- **The messages.** The harness's newline JSON, each with a request ID and the tick (D005). The
  module's host process owns the serial port: `HardwareRelay` relays STEP to the Pi and the
  reply back, in order, and carries the window's actions; `PiLinkServer` on the Pi journals
  every request, so a restarted Pi rebuilds its state (`common/hw_link/`).
- **If a Pi is lost**, its host holds the replies and the harness pauses the clock and names
  the module.
- **Open.** Power for a Pi 5 through the same USB-C port.
