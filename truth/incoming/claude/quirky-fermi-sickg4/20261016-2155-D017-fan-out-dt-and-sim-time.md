**Target:** truth/decisions/D017-shared-simulation-clock.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-16 in the team's review of `documents/system-integration-design.md` (decisions 1 and 2): "Direct fan out to the modules. Modules only see inputs on the rising clock edge"; "Send both dt and sim time". Supersedes the unpromoted proposal `20261016-1828-D017-clock-to-every-module-in-parallel.md` on this branch.

---

# D017-shared-simulation-clock

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-01 (generic-clock-config proposal `20261001-1658-shared-simulation-clock.md`), including the 05:00:00 start time and 24-hour display; adoption by every module once integrated asserted by Kevin Schillinger 2026-10-02; speed command per `signals/clock-speedup.md`; direct fan-out of dt and simulation time to every module, and inputs seen only on the rising clock edge, asserted by Kevin Schillinger 2026-10-16
**Aliases:** system clock, simulation clock, shared clock, SystemClock, sim time, D009-shared-simulation-clock, D012-shared-simulation-clock
**Last updated:** 2026-10-16

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
- The CTC Office sets the speed and pauses or resumes the clock, through the harness.

## Consequences

- At the default tick length, ticks happen 10 times per real second at 1x and 100
  times per real second at 10x.
- The CTC Office's speed and pause controls act on the shared clock. They do not
  change any module's time step.
- Time crosses module boundaries in seconds (`conventions/units.md`).
- The CTC Office's speed command reaches the clock as the clock-speedup signal
  (`signals/clock-speedup.md`).

## Supersedes

- Clock propagation: previously the harness passed simulation time to every module
  without saying how; now it fans out both dt and the simulation time directly to
  every module on each tick, and a module sees its inputs only on the rising clock edge
  (Kevin Schillinger 2026-10-16).
