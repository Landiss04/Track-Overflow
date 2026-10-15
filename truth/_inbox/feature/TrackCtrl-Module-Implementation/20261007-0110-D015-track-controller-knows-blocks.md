**Target:** truth/decisions/D015-track-controller-knows-blocks.md
**Action:** create
**Proposed by:** GitHub Copilot on feature/TrackCtrl-Module-Implementation
**Provenance:** asserted by Braden 2026-10-06

Note for the promoter: this contradicts `signals/suggested-speed.md` and
`signals/suggested-authority.md` on `truth`, which key each value by train ID.
The pending proposals `20261006-1530-suggested-speed.md` and
`20261006-1530-suggested-authority.md` on `feature/TrackCtrl-TestUI-PerBlock`
record that as a conflict owned by Kevin. Promote this only together with a
resolution of those conflicts.

---

# D015-track-controller-knows-blocks

**Status:** current
**Owner:** Braden
**Provenance:** asserted by Braden 2026-10-06
**Aliases:** wayside knows no trains, per-block Track Controller interface, block-keyed wayside
**Last updated:** 2026-10-06

## Context

A wayside controller detects a train only as an occupied block, through the
track circuit. Nothing it receives names a train: the Track Model reports
occupancy per block, and speed and authority reach a train down the track
circuit of the block it is in.

## Decision

The Track Controller knows the blocks it governs, never the trains on them.

- Everything it exchanges with the CTC Office and the Track Model is keyed by
  block. That includes the suggested speed and authority from the CTC Office.
- It reports no train identity, location or speed to the CTC Office.
- It shows no train IDs.

## Consequences

- The CTC Office sends a suggestion for a block, not for a train. Mapping a
  train to the block it occupies happens outside the Track Controller.
- The report to the CTC Office carries occupancy, switch, crossing and failure
  state per block.
- The CTC Office's current interface, which keys suggestions by train and
  expects train reports from the Track Controller, needs a central-harness
  mapping or a change.
