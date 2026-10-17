**Target:** truth/decisions/D021-hardware-variants-and-selection.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** as `20261016-2254-D021-hardware-variants-and-selection.md` on this branch, which this proposal supersedes (deny that one), plus Kevin Schillinger 2026-10-17: "the hardware versions communicate with the host machine over the usb cable but the UI still runs on the host machine". The USB protocol and the one-computer question remain open ("open still", Kevin Schillinger 2026-10-17). The Blue Line note is dropped because the Blue Line is out of scope (`20261017-1433-D023-blue-line-out-of-scope.md`, proposed alongside).

---

# D021-hardware-variants-and-selection

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin Schillinger 2026-10-16; a hardware variant's UI on the host PC asserted by Kevin Schillinger 2026-10-17
**Aliases:** HW variants, hardware variants, Raspberry Pi, USB link, variant selection, line assignment, HW UI on the host
**Last updated:** 2026-10-17

## Context

The Track Controller and the Train Controller each have a software and a hardware
instance (`conventions/naming.md`). Which instance is active, and where the hardware
instances run, is a decision rather than a module fact. No entry said either.

## Decision

- The hardware variants run on Raspberry Pis. They communicate with the host PC over
  USB.
- A hardware variant's UI runs on the host PC, not on the Raspberry Pi.
- A module's software and hardware variants have identical interfaces: they consume
  and produce the same I/O. The hardware variant's I/O travels over USB to its
  Raspberry Pi.
- The Track Controller HW runs the Red Line. The Track Controller SW runs the Green
  Line.
- A train on the Green Line is driven by the Train Controller SW. A train on the Red
  Line is driven by the Train Controller HW.

## Consequences

- The variant that serves a block or a train follows from its line.
- Open: the protocol over USB, and whether the Raspberry Pis count toward running
  every module on one computer.
