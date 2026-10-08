**Target:** truth/decisions/D018-track-controller-test-ui-kept.md
**Action:** create
**Proposed by:** GitHub Copilot on feature/TrackCtrl-Module-Implementation
**Provenance:** asserted by Braden 2026-10-08

Note for the promoter: D010 says the Train Model test UI "is removed" once the
system is integrated. This entry keeps the Track Controller (hardware) test UI
instead. Braden's statement was "we should continuously support the test UI
throughout the entirety of the project"; whether that applies to every module,
and so changes D010, is for the team to confirm. Owner of that question: Braden.

---

# D018-track-controller-test-ui-kept

**Status:** current
**Owner:** Braden
**Provenance:** asserted by Braden 2026-10-08
**Aliases:** test UI through the final demo, test UI kept at integration, standalone demonstration
**Last updated:** 2026-10-08

## Context

The hardware Track Controller has a test UI that stands in for the CTC Office,
the Track Model and the clock, in its own process. If integration is incomplete
at the final demonstration, the module still has to be shown working.

## Decision

- The Track Controller (hardware) test UI is supported for the whole project,
  final demonstration included. It is not removed at integration.
- If the system is not fully integrated at the final demonstration, the module
  is demonstrated through its test UI.
- The test UI stays a separate process that drives the module only through its
  interface, `step(dt, inputs)` returning the outputs. The module never depends
  on it.

## Consequences

- Every change to the module's interface updates the test UI and its link in
  the same change.
- One driver steps the module at a time: the central harness when integrated,
  or the test UI when the module runs standalone.
