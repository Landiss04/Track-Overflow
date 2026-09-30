**Target:** truth/decisions/train-model-ui-state.md
**Action:** add
**Proposed by:** Codex on Train-model-Interface
**Provenance:** asserted by Kevin Schillinger 2026-09-30 in this chat: "all ui elements states should be directly tied to the state of the train model"

---

# train-model-ui-state

**Status:** current
**Owner:** Kevin Schillinger
**Provenance:** asserted by Kevin Schillinger 2026-09-30
**Aliases:** Train Model UI synchronization, test UI state binding
**Last updated:** 2026-09-30

## Decision

The Train Model overview and test UI must derive their displayed states
directly from the Train Model state. A state change made through either
view must be reflected in the other view's corresponding controls.

In particular, applying the passenger emergency brake through the overview
must be reflected in the test UI's emergency-brake control.
