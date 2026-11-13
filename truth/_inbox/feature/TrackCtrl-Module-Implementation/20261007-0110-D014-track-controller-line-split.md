**Target:** truth/decisions/D014-track-controller-line-split.md
**Action:** create
**Proposed by:** GitHub Copilot on feature/TrackCtrl-Module-Implementation
**Provenance:** asserted by Braden 2026-10-06

Note for the promoter: D012 and D013 are already taken by pending proposals on
`Train-model-Interface` and `ctc-interfacing`, so this takes D014. Renumber it if
those are promoted under other numbers.

---

# D014-track-controller-line-split

**Status:** current
**Owner:** Braden
**Provenance:** asserted by Braden 2026-10-06
**Aliases:** hardware Track Controller line, software Track Controller line, waysides per line, line split
**Last updated:** 2026-10-06

## Context

The Track Controller exists as a hardware and a software variant. Each line needs
at least two wayside controllers, so which variant runs which waysides decides
how each variant is built: one wayside, or several.

## Decision

- The hardware Track Controller runs every wayside of one line. The software
  Track Controller runs every wayside of the other line.
- Each line has at least two wayside controllers.
- A wayside's territory, the blocks it governs, is loaded from a database file
  in the Track Controller UI.

## Consequences

- Each variant hosts several waysides at once and lets the user switch between
  them; each wayside runs its own PLC program.
- A variant refuses a database for the other line.
- Which line each variant runs is not decided by this entry.
