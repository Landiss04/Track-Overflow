**Target:** truth/decisions/D010-train-model-test-ui-boundary.md
**Action:** replace
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** every change to this entry pending in the inbox, merged into one proposal. The test UI taking dt from the shared clock with a 1x / 10x speed toggle, asserted by Kevin Schillinger 2026-10-02 (moved here from the D012 proposal); validating each step before the shared clock ticks, and a drift check every 30 ticks, decided by Kevin Schillinger 2026-10-03, after a rejected step was found to advance the shared clock without the Train Model; the test UI's speed limiter, the Blue Line loaded by default, the trimmed output table and the in-place looping input list, asserted by Kevin Schillinger 2026-10-05 ("In the test harness add a control law that regulates the max speed when it goes too high"; "on the blue line stuff have that track loaded by default in the test harness"; "the test ui outputs should only be the output that goes to the train controller and the track model. cabin temp speed passenger capacity speed limit light state emergency brake state door state position offset position block"; "Make the left column of the test ui scrollable in place only showing as many buttons as fit on the screen make the scroll a loop"); failure injection removed from the test UI as redundant with the Train Model UI, asserted by Kevin Schillinger 2026-10-05 ("remove the murpy failure modes from the test ui that is redundant"); the test UI's service brake control showing the brake's engaged state rather than the command last sent, asserted as deliberate by Kevin Schillinger 2026-10-06 ("On the brake button yes revert I did that for a reason"), after an agent changed it to show the command; the Train Model UI's power readout retitled Power command, showing the commanded power rather than power consumption, asserted by Kevin Schillinger 2026-10-06 ("the readout should show the commanded power. so change the title of the readout to power commmand"), with this entry's example of a value only the Train Model UI shows updated to match; the test UI holding the station dwell, asserted by Kevin Schillinger 2026-10-06 ("Definitely one draw per stop and every stip is to be 45sec") and, asked which module enforces the 45 s dwell, chose "Test UI holds it", whose description read "The test UI, standing in for the Train Controller, holds the train at a station for 45 s with the doors open, then lets it go. The Train Model stays physics-only (D009); the real Train Controller does this at integration."; one test UI at a time, asserted by Kevin Schillinger 2026-10-06 ("Make it singleton only", on two test UIs driving one Train Model); the train reset when a new test UI takes over, asserted by Kevin Schillinger 2026-10-06 ("Fix b2. When a New test ui takes over reset the train"). Every quotation is from chat with Claude; none is in the repository. Replaces the six earlier inbox proposals for this entry, one of them `train-model-clock-update/20261003-2137-D010-train-model-test-ui-boundary.md`, deleted as duplicates on 2026-10-06 at Kevin Schillinger's request ("review all the proposals and dedupe").

---

# D010-train-model-test-ui-boundary

**Status:** current
**Owner:** Kevin Schillinger
**Provenance:** asserted by Kevin Schillinger 2026-10-01; dt from the shared clock and a 1x / 10x speed toggle asserted by Kevin Schillinger 2026-10-02; validating steps before the clock ticks and a drift check every 30 ticks asserted by Kevin Schillinger 2026-10-03; the speed limiter, the Blue Line by default, the trimmed output table and the in-place input list asserted by Kevin Schillinger 2026-10-05; failure injection removed from the test UI as redundant, asserted by Kevin Schillinger 2026-10-05; the service brake control showing the engaged state, asserted by Kevin Schillinger 2026-10-06; the Train Model UI's power readout retitled Power command, asserted by Kevin Schillinger 2026-10-06; the test UI holding the station dwell, and one test UI at a time, asserted by Kevin Schillinger 2026-10-06; the train reset when a new test UI takes over, asserted by Kevin Schillinger 2026-10-06
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
- When a new test UI takes over a train that another test UI drove, the Train Model
  resets the train first, so it matches the new test UI's fresh stand-ins. A train no
  test UI has driven is not reset.

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
