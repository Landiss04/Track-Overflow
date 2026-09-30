**Target:** truth/signals/emergency-brake-state.md
**Action:** create
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** `Train_Model_Backend_Design.pdf` §5.8 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; not in the repository

---

# emergency-brake-state

**Status:** current
**Owner:** Train Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.8 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30
**Aliases:** Emergency Brake State, e-brake state, emergency brake active
**Last updated:** 2026-09-30

## Definition

A `bool` sent from the Train Model to the Train Controller. It is true while the
emergency brake is active, whether engaged by the Train Controller's Emergency Brake
Command or by a passenger pull in the Train Model UI.

## Notes

- For who owns the passenger pull, see `arbitration/passenger-emergency-brake.md`.
