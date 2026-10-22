**Target:** truth/decisions/D032-multiple-trains-per-line.md
**Action:** create
**Proposed by:** Integration on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-22: "2+ trains must be able to run on each line"

---

# D032-multiple-trains-per-line

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin Schillinger 2026-10-22: "2+ trains must be able to run on each line"
**Aliases:** multiple trains, 2+ trains, two or more trains, concurrent trains per line
**Last updated:** 2026-10-22

## Context

No entry stated how many trains the system must run at once on a line.

## Decision

The system must be able to run two or more trains at the same time on each
line in scope, the Green Line and the Red Line (D023).

## Consequences

- Every module handles more than one train on a line at once.
- Existing safety rules still apply between those trains, for example
  [one-train-per-block](../arbitration/one-train-per-block.md).
