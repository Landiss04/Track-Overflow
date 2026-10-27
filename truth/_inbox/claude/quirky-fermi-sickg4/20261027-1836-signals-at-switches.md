**Target:** truth/decisions/signals-at-switches.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** `documents/module-owner-review-braden.md` (branch `feature/TrackCtrl-HW-vital`, `a5bd465`), TM-2: stated by the professor, relayed by Braden Bosilovich 2026-10-26

---

# signals-at-switches

**Status:** current
**Owner:** Track Model
**Provenance:** the professor, relayed by Braden Bosilovich 2026-10-26 (module owner review TM-2), `documents/module-owner-review-braden.md` (branch `feature/TrackCtrl-HW-vital`, `a5bd465`)
**Aliases:** wayside signal placement, light ahead, signal per switch, B1
**Last updated:** 2026-10-27

## Context

Module owner review TM-2 asked where the lights stand, so that the Track Model can
pick the light ahead of a train.

## Decision

Signals sit only at switches: one signal per switch, at the switch, identified by the
switch's ID.

## Consequences

- The Track Model picks a train's next signal from the switches ahead of it.
- Track Controller signal outputs are per switch (`SIG_s_*`).
