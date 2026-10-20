**Target:** truth/decisions/D024-train-gains-set-by-engineer.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-20: "Trains must wait for engineer to set gains, can be a default value but aren't auto applied"; the UI on the host PC per the proposed D021. ID D024 because D019 to D023 are taken by pending proposals.

---

# D024-train-gains-set-by-engineer

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin Schillinger 2026-10-20
**Aliases:** gains, Kp and Ki, commissioning, default gains, engineer gains
**Last updated:** 2026-10-20

## Context

A Train Controller applies no power until its control gains are set. In the integrated
system the CTC Office creates trains while the simulation runs, so the question was
whether a new train's gains are ever set without a person.

## Decision

- Every new train waits for an engineer to set its gains before it applies power.
- The Train Controller UI may offer default gain values, but it never applies them by
  itself.

## Consequences

- A train the CTC Office releases from the yard does not move until an engineer has set
  its gains.
- The engineer sets gains in the Train Controller UI, which runs on the host PC for the
  hardware variant too.
