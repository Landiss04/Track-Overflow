**Target:** truth/decisions/D035-pi-paths-share-one-implementation.md
**Action:** create
**Proposed by:** Integration on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-22: "do not repeat code for this reuse as much as possible so that changes can be applied in one place"

---

# D035-pi-paths-share-one-implementation

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin Schillinger 2026-10-22: "do not repeat code for this reuse as much as possible so that changes can be applied in one place"
**Aliases:** code reuse, one place, no repeated code, simulated Pi, real Pi, Pi bring-up, shared Pi path
**Last updated:** 2026-10-22

## Context

Kevin gave this instruction while the Pi path was being made turnkey: the
simulated and real Raspberry Pis, and the Pi bring-up, for the hardware
variants (D021, D027).

## Decision

Kevin's words: "do not repeat code for this reuse as much as possible so that
changes can be applied in one place".

The simulated-Pi path, the real-Pi path and the hardware variants reuse one
implementation wherever they can, so that a change is made in one place.

## Consequences

- Where code for these paths would otherwise be repeated, it is shared.
- "As much as possible" is Kevin's limit. The entry does not require that
  every line be shared.

## Interpretation

Not Kevin's words; to be confirmed by the owner.

- Read as covering the Pi path for both hardware variants, the Track
  Controller HW and the Train Controller HW: host link, Pi agent and
  bring-up, simulated or real.
- Not read as requiring a module's software and hardware variants to share
  code. The proposed D016 says the Track Controller variants "share the file
  format, not code", and the scope of the diversity requirement is still
  unresolved (`modules/track-controller/track-controller.md`). This entry does
  not change either.
- Simulation stays an explicit choice for tests and development, with no
  automatic fallback from a real Pi (proposed `arbitration/pi-link-recovery.md`).
