**Target:** truth/signals/cabin-temperature.md
**Action:** create
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** `Train_Model_Backend_Design.pdf` §5.4 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; not in the repository

---

# cabin-temperature

**Status:** current
**Owner:** Train Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.4 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30
**Aliases:** Cabin Temp, cabin temperature, actual cabin temperature
**Last updated:** 2026-09-30

## Definition

The actual cabin temperature, sent from the Train Model to the Train Controller.

## Notes

- The Train Model regulates the cabin toward the Temperature Setpoint. The source leaves
  the regulation model and its time constant open.
- The unit follows `conventions/units.md`. Whether the backend uses Fahrenheit or Celsius
  is an open conflict there, and this entry does not settle it.
