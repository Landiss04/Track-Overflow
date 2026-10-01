**Target:** truth/decisions/D009-shared-simulation-clock.md
**Action:** create
**Proposed by:** Claude on generic-clock-config
**Provenance:** asserted by Landis 2026-10-01

---

# D009-shared-simulation-clock

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-01
**Aliases:** system clock, simulation clock, shared clock, sim time, clock speed, 10x
**Last updated:** 2026-10-01

## Context

`conventions/files-and-paths.md` requires one simulation clock shared by every
component, supporting real time and fast-forward. D006 fixes the tick length and lets
speed change only the tick rate. Neither entry says where the clock lives, which
speeds it allows, what time a simulation starts at, how long a tick is by default, or
who controls it.

## Decision

- One shared clock, `SystemClock`, in the `utils/` package at `utils/system_clock.py`.
- At 1x, one simulated second lasts one real second.
- The allowed speeds are 1x and 10x. No other speed is accepted.
- The clock can be paused and resumed.
- A simulation starts at 08:00:00 simulated time.
- The default tick length is 0.1 s. It is configurable per clock and does not change
  while the clock runs (D006).
- The central harness (D005) owns the clock and passes simulation time to every
  module. Modules do not run clocks of their own.
- The CTC Office sets the speed and pauses or resumes the clock, through the harness.

## Consequences

- At the default tick length, ticks happen 10 times per real second at 1x and 100
  times per real second at 10x.
- The CTC Office's speed and pause controls act on the shared clock. They do not
  change any module's time step.
- Time crosses module boundaries in seconds (`conventions/units.md`).
