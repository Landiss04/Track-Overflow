**Target:** truth/decisions/D017-shared-simulation-clock.md
**Action:** replace
**Proposed by:** Claude on integrate/harness-into-development
**Provenance:** asserted by Kevin Schillinger 2026-11-12 (the harness gets a reset button that restarts the simulation fresh, with the flags used at launch retained) and 2026-11-13 (reset is done by restarting every module process from the saved launch options, inside the running harness)

---

# D017-shared-simulation-clock

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-01 (generic-clock-config proposal `20261001-1658-shared-simulation-clock.md`), including the 05:00:00 start time and 24-hour display; adoption by every module once integrated asserted by Kevin Schillinger 2026-10-02; speed command per `signals/clock-speedup.md`; direct fan-out of dt and simulation time to every module, and inputs seen only on the rising clock edge, asserted by Kevin Schillinger 2026-10-16; unwrapped simulation time, waiting for every module's reply with a timeout, and the 0.1 s tick as a recorded deviation, proposed in the design doc's per-module questions and accepted by Kevin Schillinger 2026-10-20; reset from the harness window by restarting every module with the launch options kept, asserted by Kevin Schillinger 2026-11-12 and 2026-11-13
**Aliases:** system clock, simulation clock, shared clock, SystemClock, sim time, D009-shared-simulation-clock, D012-shared-simulation-clock
**Last updated:** 2026-11-13

## Context

`conventions/files-and-paths.md` requires one simulation clock shared by every
component, supporting real time and fast-forward. D006 fixes the tick length and lets
speed change only the tick rate. Neither entry says where the clock lives, which
speeds it allows, what time a simulation starts at, how long a tick is by default, or
who controls it.

## Decision

- One shared clock, `SystemClock`, in the `utils/` package at `utils/system_clock.py`.
  Every module uses it once the system is integrated.
- At 1x, one simulated second lasts one real second.
- The allowed speeds are 1x and 10x. No other speed is accepted.
- The clock can be paused and resumed.
- A simulation starts at 05:00:00 simulated time.
- Simulated time of day is shown in 24-hour (military) time as zero-padded
  `HH:MM:SS`, hours 00 to 23: 1:05 PM is `13:05:00`.
- The default tick length is 0.1 s. It is configurable per clock and does not change
  while the clock runs (D006).
- The central harness (D005) owns the clock. On every tick it sends both dt and the
  simulation time directly to every module; no module relays the clock to another.
  Modules do not run clocks of their own.
- A module sees its inputs only on the rising edge of the clock.
- The simulation time sent is unwrapped: `SystemClock.sim_time_s`, which starts at
  18 000 s (05:00:00) and keeps counting past midnight. Each module works out the time
  of day from it.
- The harness waits for every module's reply to a tick before it sends the next one.
  If a reply takes longer than a set limit, about 1 s, the harness pauses the clock and
  names the late module.
- The clock is never set back while module processes are running. The harness window
  has a reset: it ends every module process and starts each again with the options
  the system was launched with, and the clock starts again at 05:00:00. The harness
  process keeps running.
- The CTC Office sets the speed and pauses or resumes the clock, through the harness.

## Consequences

- At the default tick length, ticks happen 10 times per real second at 1x and 100
  times per real second at 10x.
- The CTC Office's speed and pause controls act on the shared clock. They do not
  change any module's time step.
- Time crosses module boundaries in seconds (`conventions/units.md`).
- No tick is skipped. When the harness falls behind, simulated time runs slower than
  real time instead, which is how REQ-NFR-001.2 ("shall not drop any ticks") is met.
- The 0.1 s tick departs from REQ-NFR-001.1, under which the simulation should advance
  in 1 ms ticks. This is a recorded deviation.
- The CTC Office's speed command reaches the clock as the clock-speedup signal
  (`signals/clock-speedup.md`).
- A module never sees simulation time go backwards within its own process.
- Options given at launch apply again after a reset. Anything a person loaded in a
  module's window is lost by it.

## Supersedes

- Reset: previously the clock was not reset during a run and resetting meant
  restarting the whole system; now the harness window can reset by restarting every
  module process with the launch options kept, the harness itself staying up (Kevin
  Schillinger 2026-11-13).
