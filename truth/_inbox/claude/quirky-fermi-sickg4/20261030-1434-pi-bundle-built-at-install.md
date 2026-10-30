**Target:** truth/decisions/pi-bundle-built-at-install.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** asserted by Braden Bosilovich 2026-10-30, relayed by Kevin Schillinger (module owner review, "Track Controller HW answers, 2026-10-30", request 7)

---

# pi-bundle-built-at-install

**Status:** current
**Owner:** Braden Bosilovich (Track Controller HW)
**Provenance:** asserted by Braden Bosilovich 2026-10-30, relayed by Kevin Schillinger (`documents/module-owner-review.md`, "Track Controller HW answers, 2026-10-30")
**Aliases:** Pi bundle, hw_link bundle, bundle regeneration, Pi install
**Last updated:** 2026-10-30

## Context

The software each Raspberry Pi runs is a bundle built from the repository. The
question was who rebuilds the bundles after a change to the HW cores, and when.

## Decision

A Pi bundle is built when the Pi is installed, from exactly the commit the host
runs. No bundle is committed to the repository.

Each HW module owner builds and installs their own board: the Track Controller HW
owner the Track Controller board, and the Train Controller HW owner the Train
Controller board.

## Consequences

- Both bundles carry both HW cores and one shared hash, so a change to either core
  means rebuilding both boards.
- PLC programs are not part of the bundle; the host loads them at run time, so a
  program change needs no rebuild.
