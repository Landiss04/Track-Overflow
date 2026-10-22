**Target:** truth/decisions/D030-pi-link-extensions.md
**Action:** create
**Proposed by:** Integration on claude/quirky-fermi-sickg4
**Provenance:** Kevin Schillinger's Phase 5 decisions relayed in the session prompt, 2026-10-21. K6: "accept" to the host-to-Pi HELLO, ACTION/ACK and VIEW additions.

---

# pi-link-extensions

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin Schillinger 2026-10-21; K6: "accept" to the host-to-Pi HELLO, ACTION/ACK and VIEW additions
**Aliases:** HELLO, ACTION ACK, VIEW, Option A
**Last updated:** 2026-10-21

## Decision

D027's host-to-Pi newline JSON link additionally carries:

- HELLO: protocol, module, agent version/hash and session identity.
- ACTION/ACK: operator actions acknowledged after acceptance and applied
  before the next STEP.
- VIEW: a display snapshot sent at most once per 100–200 ms.

These additions belong only to the host-to-Pi link. The protocol between
the central harness and its ordinary module processes is unchanged. The
hardware module's host process relays STEP and shows its window; the Pi
agent runs only the Qt-free core. It has no clock of its own (D017).
