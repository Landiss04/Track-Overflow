**Target:** truth/decisions/D010-train-model-test-ui-boundary.md
**Action:** create
**Proposed by:** Claude Code on Train-model-Interface-ui-split
**Provenance:** asserted by Kevin Schillinger 2026-10-01 in a Claude Code session: requirement change splitting the Train Model UI and test UI into separate processes, "the harness should follow the interface and be drop in compatible for the inputs from both the track model and the train controller ... once the system is integrated the test ui should be able to be removed and the train model wired into the system without any rework"; test-only commands, outputs-only readback, immediate mirroring of Train Model UI actions and the derived run state chosen by Kevin Schillinger in the same session

---

# D010-train-model-test-ui-boundary

**Status:** current
**Owner:** Kevin Schillinger
**Provenance:** asserted by Kevin Schillinger 2026-10-01
**Aliases:** Train Model test UI, test harness boundary, separate UI processes, drop-in test harness
**Last updated:** 2026-10-01

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

## Consequences

- Failure injection is available from both windows; both show the same failure
  status.
- The test UI cannot show values that are not outputs, such as the onboard passenger
  count or power consumption; the Train Model UI shows them.
- The transport between the two processes is test scaffolding, not part of the
  module.
