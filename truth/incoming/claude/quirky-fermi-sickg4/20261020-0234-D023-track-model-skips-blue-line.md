**Target:** truth/decisions/D023-blue-line-out-of-scope.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** as `20261017-1433-D023-blue-line-out-of-scope.md` on this branch, which this proposal supersedes (deny that one), plus Kevin Schillinger 2026-10-20: "track model will not load blue line". The CTC Office rejects a station name it does not know, so Blue Line ticket sales must not reach it.

---

# D023-blue-line-out-of-scope

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin Schillinger 2026-10-17; the Track Model not loading the Blue Line at integration asserted by Kevin Schillinger 2026-10-20
**Aliases:** Blue Line, blue line, `blue_line.json`, test line
**Last updated:** 2026-10-20

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
- The Track Model does not load the Blue Line at integration, so no Blue Line block or
  station reaches another module.
- The Blue Line default in D010 belongs to the Train Model test UI, which is removed at
  integration.
