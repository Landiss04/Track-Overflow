**Target:** truth/decisions/signals-at-switches.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** the professor, relayed by Braden Bosilovich 2026-10-26 (TM-2), as in pending proposal `20261027-1836-signals-at-switches.md`, which this replaces; the light facing the oncoming train, confirmed by the Track Model owner, relayed by Kevin Schillinger 2026-10-28 ("yes on the lights facing the oncoming train"); Track Controller SW placement confirmed by Harry Tye, relayed by Kevin Schillinger 2026-10-28 ("c6 confirmed")

---

# signals-at-switches

**Status:** current
**Owner:** Track Model
**Provenance:** the professor, relayed by Braden Bosilovich 2026-10-26 (module owner review TM-2), `documents/module-owner-review-braden.md` (branch `feature/TrackCtrl-HW-vital`, `a5bd465`); facing confirmed by the Track Model owner, relayed by Kevin Schillinger 2026-10-28; Track Controller SW agreement (C6) confirmed by Harry Tye, relayed by Kevin Schillinger 2026-10-28
**Aliases:** wayside signal placement, light ahead, signal per switch, B1, C6, signal facing
**Last updated:** 2026-10-28

## Context

Module owner review TM-2 asked where the lights stand, so that the Track Model can
pick the light ahead of a train, and which way each light faces.

## Decision

Signals sit only at switches: one signal per switch, at the switch, identified by the
switch's ID.

Each light faces the oncoming train: a train approaching the switch from its fixed side
(the side away from its two legs) sees it. A train coming off either leg does not.

## Consequences

- The Track Model picks a train's next signal as the first switch ahead of it, along
  its route with the switches as set, that it will enter from the fixed side
  ([signal-aspect-ahead](../signals/signal-aspect-ahead.md)).
- Track Controller signal outputs are per switch (`SIG_s_*`), in both the HW and the
  SW variant.
