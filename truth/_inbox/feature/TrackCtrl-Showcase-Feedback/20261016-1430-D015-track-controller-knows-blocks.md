**Target:** truth/decisions/D015-track-controller-knows-blocks.md
**Action:** create
**Proposed by:** GitHub Copilot on feature/TrackCtrl-Showcase-Feedback
**Provenance:** asserted by Braden 2026-10-06; the report carrying signal aspects asserted by Braden 2026-10-08; failures reaching the Track Controller only as occupancy asserted by Braden 2026-10-16

Note for the promoter: this replaces both pending D015 proposals in
`truth/_inbox/feature/TrackCtrl-Module-Implementation/`,
`20261007-0110-D015-track-controller-knows-blocks.md` and
`20261008-1314-D015-track-controller-knows-blocks.md`. It is the 2026-10-08
one with failure taken out of the report and one line added: a failure reaches
the Track Controller only as occupancy. Promote this one and deny both.

This still contradicts `signals/suggested-speed.md` and
`signals/suggested-authority.md` on `truth`, which key each value by train ID.
Promote it only together with a resolution of that.

---

# D015-track-controller-knows-blocks

**Status:** current
**Owner:** Braden
**Provenance:** asserted by Braden 2026-10-06; the report carrying signal aspects asserted by Braden 2026-10-08; failures reaching the Track Controller only as occupancy asserted by Braden 2026-10-16
**Aliases:** wayside knows no trains, per-block Track Controller interface, block-keyed wayside, failure reads occupied
**Last updated:** 2026-10-16

## Context

A wayside controller detects a train only as an occupied block, through the
track circuit. Nothing it receives names a train: the Track Model reports
occupancy per block, and speed and authority reach a train down the track
circuit of the block it is in. A failed block (a broken rail, a failed track
circuit, a power failure) reaches it the same way, as occupancy.

## Decision

The Track Controller knows the blocks it governs, never the trains on them,
and never what has failed on them.

- Everything it exchanges with the CTC Office and the Track Model is keyed by
  block. That includes the suggested speed and authority from the CTC Office.
- It reports no train identity, location or speed to the CTC Office.
- It shows no train IDs.
- It cannot tell a failure from a train. A failed block reads as occupied, and
  it reports that block to the CTC Office as occupied.

## Consequences

- The CTC Office sends a suggestion for a block, not for a train. Mapping a
  train to the block it occupies happens outside the Track Controller.
- The report to the CTC Office carries occupancy, switch position, signal
  aspect and crossing state per block. It carries no failure.
- The Track Model sends the Track Controller occupancy, not a failure kind.
