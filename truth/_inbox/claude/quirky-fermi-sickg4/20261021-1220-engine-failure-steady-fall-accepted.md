**Target:** truth/arbitration/engine-failure-detection.md
**Action:** create
**Proposed by:** Codex on claude/quirky-fermi-sickg4
**Provenance:** Kevin Schillinger's direct statements of 2026-10-21: the three engine-detection rules recorded in proposal `20261021-1536-engine-failure-detection.md`, followed by "Accept the steady-fall check as built" in answer to the question describing the additional straight-line check and Green 7's recoverable grade-entry sag. This full entry includes that later acceptance; the earlier proposal is preserved unchanged. The target is absent from the session's fetched `origin/truth`.

---

# engine-failure-detection

**Status:** current
**Owner:** Train Controller
**Provenance:** asserted by Kevin Schillinger 2026-10-21: never flag a train holding its target; flag falling speed with power commanded and no brake throughout a longer window; subsequently "Accept the steady-fall check as built", accepting the additional shape check and its as-built parameters.
**Aliases:** engine detection, engine failure detector, inferred engine failure, engine stall detection, steady-fall check
**Last updated:** 2026-10-21

## Definition

Both Train Controller variants shall infer an engine failure from reported speed
under these common rules:

1. Never flag a train holding its target within its control band.
2. Flag falling speed, not speed that fails to rise, only with power commanded
   above zero and no service or emergency brake commanded or reported applied
   anywhere in the detection window.
3. Use a simulation-time detection window a few seconds longer than 2 s.

## Accepted steady-fall detector

The accepted detector under review, in the shared `Train-Ctrl_HW` package, shall
never flag a train within 0.05 m/s of its target. Otherwise, it shall latch an
engine failure only when all of these conditions hold:

1. Power is commanded above zero on every tick of a 6 s simulation-time window.
2. Neither service nor emergency brake is commanded or reported applied on any tick
   of that window. A brake or zero commanded power clears the window.
3. Divide the window into consecutive half-second speed means. The first mean
   exceeds the last by more than 0.05 m/s, and every mean is within 10% of that total
   fall of the straight line joining the first and last means.

The falling-speed rule replaces a failure-to-rise rule. The additional steady-fall
shape check distinguishes a sustained fall from a recoverable grade-entry sag,
such as the approximately 0.51 m/s sag recovered in approximately 3 s at Green 7.
Acceptance of this detector does not assign its exact thresholds, control band,
window length or smoothing parameters to other independent variant implementations.

## Limits

- A stationary train with a dead engine is not flagged by this detector, because its
  speed does not fall.
- A heavily loaded train unable to hold speed on Green 7's 5% grade can satisfy
  these conditions and be flagged despite having a working engine. The rule does
  not distinguish that sustained loss of speed from a dead engine.

## Supersedes

- Previous proposed value: the three rules left exact thresholds and the fall's
  shape unspecified; Kevin's later acceptance accepts the steady-fall check and
  exact parameters for the detector under review. The earlier inbox proposal
  remains unchanged.
