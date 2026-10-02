**Target:** truth/decisions/D012-shared-simulation-clock.md
**Action:** create
**Proposed by:** Claude (Claude Code) on train-model-clock-update
**Provenance:** the clock util on development (`utils/system_clock.py`, commit `4d83118`) is the clock every module uses once the system is integrated, and the Train Model test UI takes dt from it with a 1x / 10x speed toggle, asserted by Kevin Schillinger 2026-10-02 in this chat; every other fact from the generic-clock-config proposal `20261001-1658-shared-simulation-clock.md`, asserted by Landis 2026-10-01. That proposal targets D009, which truth has since assigned to D009-train-model-control-boundary, so this entry carries the same decision under the next free number, D012 (D004 is claimed by the pending shared-window-scaling proposal).

---

# D012-shared-simulation-clock

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-01 (generic-clock-config proposal `20261001-1658-shared-simulation-clock.md`), including the 05:00:00 start time and 24-hour display; adoption by every module once integrated, and by the Train Model test UI, asserted by Kevin Schillinger 2026-10-02
**Aliases:** system clock, simulation clock, shared clock, SystemClock, sim time, clock speed, 10x, D009-shared-simulation-clock
**Last updated:** 2026-10-02

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
- The central harness (D005) owns the clock and passes simulation time to every
  module. Modules do not run clocks of their own.
- The CTC Office sets the speed and pauses or resumes the clock, through the harness.

## Consequences

- At the default tick length, ticks happen 10 times per real second at 1x and 100
  times per real second at 10x.
- The CTC Office's speed and pause controls act on the shared clock. They do not
  change any module's time step.
- Time crosses module boundaries in seconds (`conventions/units.md`).
- The Train Model test UI takes dt from the shared clock's tick length and offers a
  1x / 10x speed toggle.
