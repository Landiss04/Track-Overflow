**Target:** truth/decisions/D009-train-model-control-boundary.md
**Action:** create
**Proposed by:** Codex on Train-model-Interface
**Provenance:** asserted by Kevin Schillinger 2026-09-30 in this chat: "this module is physics only the controls happen in the train controller"

---

# D009-train-model-control-boundary

**Status:** current
**Owner:** Kevin Schillinger
**Provenance:** asserted by Kevin Schillinger 2026-09-30
**Aliases:** Train Model physics-only scope, train speed control ownership
**Last updated:** 2026-09-30

## Decision

The Train Model simulates the physical response to commands. Control logic
belongs to the Train Controller, including speed regulation and enforcement
of commanded and permitted speeds. A configured vehicle maximum speed does
not authorize adding a speed governor to the Train Model.

## Consequences

Physics corrections in the Train Model must preserve this boundary. Vehicle
calibration and physical power accounting are separate from control logic.
