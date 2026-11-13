**Target:** truth/decisions/D033-red-integration-plc-routing.md
**Action:** create
**Proposed by:** Integration on claude/quirky-fermi-sickg4
**Provenance:** Kevin Schillinger, 2026-10-22, Phase 6 instructions authorizing reuse of Braden's Green PLC switch logic for every Red switch.

---

# D033-red-integration-plc-routing

**Status:** current
**Owner:** Track Controller
**Provenance:** asserted by Kevin Schillinger 2026-10-22, Phase 6 switch-routing instructions
**Aliases:** Red test PLC routing, reuse Green switch logic
**Last updated:** 2026-10-22

## Decision

Reuse Braden's Green PLC switch-routing pattern for every Red switch in
the integration test PLC copies. A CTC switch command selects the requested
position; otherwise use occupancy and closures through AUTO/WANT logic.
Hold the reported position while the points are occupied, and make signals
follow the selected route. These remain integration test copies awaiting
Braden's review. Do not add automatic reversal.

## Supersedes

- The instruction to wait for real Red programs before adding Red switch routing is superseded by Kevin's 2026-10-22 authorization to reuse Braden's Green logic in the integration test copies.
