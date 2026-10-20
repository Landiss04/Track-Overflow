**Target:** truth/decisions/D025-ctc-test-ui-boundary.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4 (re-filed; first proposed by Claude on ctc-deployment)
**Provenance:** as `20261020-0039-D019-ctc-test-ui-boundary.md` on this branch, which this proposal supersedes (deny that one), renumbered from D019 to D025 because the pending `feature/TrackCtrl-Showcase-Feedback/20261016-1430-D019-wayside-runs-only-its-program.md` (PR #43) also uses D019; Kevin Schillinger 2026-10-20: "renumber as needed". First proposed as `ctc-deployment/20261014-1042-ctc-test-ui-boundary.md`. The entry is unchanged except its key, heading and aliases.

---

# D025-ctc-test-ui-boundary

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-14 (CTC module feedback: the test UI's only inputs are the ones that come from the Track Controller, and the CTC's own inputs are forced through the CTC UI)
**Aliases:** CTC test UI, CTC test harness, CTC test UI inputs, CTC test harness boundary, D019-ctc-test-ui-boundary
**Last updated:** 2026-10-14

## Context

The CTC Office test UI stood in for the Track Controller and the Track Model, and also
had rows standing in for the dispatcher's own actions (dispatch orders, block closures,
switch commands, maintenance mode, clock speed), which duplicated the CTC UI.

## Decision

- The CTC Office test UI stands in for the Track Controller only. Its inputs are only
  the signals the Track Controller sends the CTC Office: block occupancy, switch states
  and crossing states.
- Every input that is the CTC Office's own (dispatching, block closures, switch
  commands, the operating mode, the clock speed) is forced through the CTC UI, as a
  dispatcher would, never through the test UI.
- The test UI does not force ticket sales: they come from the Track Model
  ([ticket-sales](../signals/ticket-sales.md)), not the Track Controller.

## Consequences

- The test UI reads back the CTC Office's outputs, so the effect of an action taken in
  the CTC UI shows there.
- Ticket sales, and the throughput metrics derived from them, cannot be forced from the
  CTC test UI.
