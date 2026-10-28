**Target:** truth/decisions/D028-red-yard-connection.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** Kevin Schillinger 2026-10-21 (K2) and 2026-10-22, as in pending proposal `20261021-1808-red-yard-connection.md`, which this replaces; switch-9 geometry confirmed by the Track Model owner 2026-10-26 (LAYOUT-1, `documents/module-owner-review.md`) and by Kevin Schillinger 2026-10-28 ("yes on layout-01"); the light at the switch point per `signals-at-switches`, accepted by Kevin Schillinger 2026-10-28

---

# D028-red-yard-connection

**Status:** current
**Owner:** Track Model
**Provenance:** asserted by Kevin Schillinger 2026-10-21 (K2: "block 9 physically connects to the yard via a switch … note that block 9 is in section c") and 2026-10-22 ("the track is a given data point and can not be modified"); switch-9 geometry confirmed by the Track Model owner 2026-10-26 (LAYOUT-1) and by Kevin Schillinger 2026-10-28
**Aliases:** Red yard, Red block 9, Red switch 9, Phase 3 Q5, LAYOUT-1
**Last updated:** 2026-10-28

## Context

The Red Line track file lists the yard connection in a way the readers had to
interpret. The module owner review (LAYOUT-1) asked for the geometry to be confirmed.

## Decision

The Red yard physically connects through the switch on Red block 9, section C. The
given track data is not modified.

Switch 9: the point is block 9; NORMAL leads to block 8, REVERSE to the yard; the
fixed side is block 10. A train leaving the Red yard goes out through the REVERSE leg
and the fixed side, to block 10. A Red train returns to the yard at block 9. Switch 9's
light stands at the switch, on block 9
([signals-at-switches](signals-at-switches.md)).

## Consequences

- The Track Model's `layout.py` reading is the master; the CTC Office and the Track
  Controllers follow it ([track-model-layout-is-master](track-model-layout-is-master.md),
  proposed).
- The light formerly read as standing on block 10 now stands on block 9, under
  [signals-at-switches](signals-at-switches.md).
