**Target:** truth/decisions/D010-train-model-test-ui-boundary.md
**Action:** replace
**Proposed by:** Claude (Claude Code) on train-model-clock-update
**Provenance:** the test UI taking dt from the shared clock with a 1x / 10x speed toggle, asserted by Kevin Schillinger 2026-10-02 in this chat (moved here from the D012 proposal); validating each step before the shared clock ticks, and a drift check every 30 ticks, decided by Kevin Schillinger 2026-10-03 in this chat, after a rejected step was found to advance the shared clock without the Train Model; the rest of the entry unchanged from truth

---

# D010-train-model-test-ui-boundary

**Status:** current
**Owner:** Kevin Schillinger
**Provenance:** asserted by Kevin Schillinger 2026-10-01; dt from the shared clock and a 1x / 10x speed toggle asserted by Kevin Schillinger 2026-10-02; validating steps before the clock ticks and a drift check every 30 ticks asserted by Kevin Schillinger 2026-10-03
**Aliases:** Train Model test UI, test harness boundary, separate UI processes, drop-in test harness
**Last updated:** 2026-10-03

## Context

The Train Model UI and its test UI were one window with buttons switching between
them, and the test harness reached into the module's internal state. A requirement
change makes them two independent UIs that still work together, and the system must
be able to drop the test UI at integration.

## Decision

- The Train Model UI and the test UI are two independent windows, each its own
  process. Neither switches to the other.
- The test UI stands in for the Track Model, the Train Controller and the clock. It
  drives the Train Model only through the module interface: `step(dt, inputs)`
  returning the outputs. It reads back only the cross-module outputs, never the
  Train Model UI snapshot.
- Once the system is integrated, the test UI is removed and the Train Model is
  wired into the system with no change to the module.
- Three test-only commands sit outside the interface and are never used at
  integration: set a failure, clear the passenger emergency brake latch, and reset
  the module.
- A Train Model UI action between steps (passenger emergency brake, failure) reaches
  the test UI immediately, as outputs, including while the clock is held.
- The Train Model UI shows Running while steps arrive and Paused when they stop,
  whoever sends them.
- The test UI takes dt from the shared clock's tick length and offers a 1x / 10x
  speed toggle.
- The test UI validates each step before it ticks the shared clock, so input the
  Train Model would reject never advances the clock.
- Every 30 clock ticks the test UI checks for drift between the shared clock and the
  Train Model, and shows any it finds.

## Consequences

- Failure injection is available from both windows; both show the same failure
  status.
- The test UI cannot show values that are not outputs, such as the onboard passenger
  count or power consumption; the Train Model UI shows them.
- The transport between the two processes is test scaffolding, not part of the
  module.
- The Train Model's own time is not an output, so drift is measured against the
  steps the Train Model accepted.
