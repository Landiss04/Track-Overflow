**Target:** truth/decisions/D023-blue-line-out-of-scope.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-17, answering which variants serve the Blue Line: "The blue line was for testing on a previous iteration not for the final product nothing on the blue line should be accounted for". ID D023 because D019 and D020 are reserved and D021 and D022 are proposed on this branch.

---

# D023-blue-line-out-of-scope

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin Schillinger 2026-10-17
**Aliases:** Blue Line, blue line, `blue_line.json`, test line
**Last updated:** 2026-10-17

## Context

The repository holds a Blue Line layout, `TrackModel/blue_line.json`, beside the Green
and Red Lines, and the Train Model test UI loads it by default
([D010](D010-train-model-test-ui-boundary.md)). No entry said whether the final system
runs it.

## Decision

The Blue Line is not part of the final product. It was for testing in a previous
iteration. Nothing on the Blue Line is accounted for.

## Consequences

- The integrated system runs the Green and Red Lines only.
- The Blue Line default in D010 belongs to the Train Model test UI, which is removed at
  integration.
