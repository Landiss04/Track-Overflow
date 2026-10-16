**Target:** truth/decisions/D021-hardware-variants-and-selection.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-16 in the team's review of `documents/system-integration-design.md`: "The HW variants run on Raspberry pis and communicate with the host pc via USB. HW on the red line and SW on the green. If a train is on the green line it gets SW train controller on red a HW controller" (decision 5); "Every hardware modules are running on raspberry Pis. The interfaces between the software and hardware modules are identical meaning that they will consume the same IO, but hardware will communicate over USB to the PIS" (G-HW-1). Settles which line each Track Controller variant runs, which the pending `feature/TrackCtrl-Module-Implementation/20261007-0110-D014-track-controller-line-split.md` leaves undecided. ID D021 because D019 and D020 are reserved by pending or removed proposals.

---

# D021-hardware-variants-and-selection

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin Schillinger 2026-10-16
**Aliases:** HW variants, hardware variants, Raspberry Pi, USB link, variant selection, line assignment
**Last updated:** 2026-10-16

## Context

The Track Controller and the Train Controller each have a software and a hardware
instance (`conventions/naming.md`). Which instance is active, and where the hardware
instances run, is a decision rather than a module fact. No entry said either.

## Decision

- The hardware variants run on Raspberry Pis. They communicate with the host PC over
  USB.
- A module's software and hardware variants have identical interfaces: they consume
  and produce the same I/O. The hardware variant's I/O travels over USB to its
  Raspberry Pi.
- The Track Controller HW runs the Red Line. The Track Controller SW runs the Green
  Line.
- A train on the Green Line is driven by the Train Controller SW. A train on the Red
  Line is driven by the Train Controller HW.

## Consequences

- The variant that serves a block or a train follows from its line.
- Open: which variants serve the Blue Line is not stated.
