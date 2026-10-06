**Target:** truth/decisions/D010-train-model-test-ui-boundary.md
**Action:** replace
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** the test UI holding the station dwell, asserted by Kevin Schillinger 2026-10-06 in this chat ("Definitely one draw per stop and every stip is to be 45sec") and, asked which module enforces the 45 s dwell, chose "Test UI holds it", whose description read "The test UI, standing in for the Train Controller, holds the train at a station for 45 s with the doors open, then lets it go. The Train Model stays physics-only (D009); the real Train Controller does this at integration."; one test UI at a time, asserted by Kevin Schillinger 2026-10-06 in this chat ("Make it singleton only", on two test UIs driving one Train Model). Builds on and replaces the inbox proposal `20261006-1008-D010-train-model-test-ui-boundary.md`, whose changes it keeps unaltered.

---

# D010-train-model-test-ui-boundary

**Status:** current
**Owner:** Kevin Schillinger
**Provenance:** asserted by Kevin Schillinger 2026-10-01; dt from the shared clock and a 1x / 10x speed toggle asserted by Kevin Schillinger 2026-10-02; validating steps before the clock ticks and a drift check every 30 ticks asserted by Kevin Schillinger 2026-10-03; the speed limiter, the Blue Line by default, the trimmed output table and the in-place input list asserted by Kevin Schillinger 2026-10-05; failure injection removed from the test UI as redundant, asserted by Kevin Schillinger 2026-10-05; the service brake control showing the engaged state, asserted by Kevin Schillinger 2026-10-06; the test UI holding the station dwell, and one test UI at a time, asserted by Kevin Schillinger 2026-10-06
**Aliases:** Train Model test UI, test harness boundary, separate UI processes, drop-in test harness, test UI speed limiter, test UI Blue Line, test UI station dwell, single test UI
**Last updated:** 2026-10-06

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
- Two test-only commands sit outside the interface and are never used at
  integration: clear the passenger emergency brake latch, and reset the module.
- Failures are injected only from the Train Model UI. The test UI has no failure
  controls.
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
- As the stand-in Train Controller, the test UI applies a control law that limits the
  train's speed when it goes too high. The Train Model itself still does not govern its
  speed (D009).
- As the stand-in Track Model, the test UI loads the Blue Line by default.
- The test UI's output table lists only cabin temperature, speed, passenger capacity,
  speed limit, light state, emergency brake state, door state, position offset and
  position block.
- The test UI's inputs scroll in place, showing only the rows that fit, and wrap from
  the last row to the first.
- The test UI's service brake control shows whether the service brake is engaged,
  read back from the outputs, not the command last sent. While a brake failure blocks
  a commanded service brake the control shows off, and it shows on again when the
  failure clears and the brake engages. This is deliberate.
- As the stand-in Train Controller, the test UI holds the 45 s station dwell (D007):
  once a door opens with the train at rest at a station, it sends no power, the
  service brake and the open doors for 45 s, whatever is entered, once per stop.
- One test UI at a time drives a Train Model. The Train Model refuses a second until
  the first leaves.

## Consequences

- The test UI sees a failure only through its effect on the outputs. It does not show
  which failures are set, since failure status is not an output.
- The test UI cannot show values that are not outputs, such as the onboard passenger
  count; the Train Model UI shows them.
- The transport between the two processes is test scaffolding, not part of the
  module.
- The Train Model's own time is not an output, so drift is measured against the
  steps the Train Model accepted.
- The speed limiter, the loaded Blue Line and the station dwell are part of the test
  UI, so they are removed with it at integration.

## Supersedes

- Example of a Train Model UI-only value: previously power consumption; that readout
  now shows the commanded power, titled Power command (Kevin Schillinger
  2026-10-06).
- Failure injection: previously available from both windows, with setting a failure
  as a third test-only command; now from the Train Model UI only, the test UI's
  controls being redundant (Kevin Schillinger 2026-10-05).
