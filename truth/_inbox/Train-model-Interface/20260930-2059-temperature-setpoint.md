**Target:** truth/signals/temperature-setpoint.md
**Action:** create
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** `Train_Model_Backend_Design.pdf` §5.4 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; unit per `conventions/units.md` as resolved by Kevin 2026-09-30; not in the repository

---

# temperature-setpoint

**Status:** current
**Owner:** Train Controller
**Provenance:** `Train_Model_Backend_Design.pdf` §5.4 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; unit per `conventions/units.md` as resolved by Kevin 2026-09-30
**Aliases:** Temperature Setpoint, cabin setpoint, desired cabin temperature
**Last updated:** 2026-09-30

## Definition

The desired cabin temperature, sent from the Train Controller to the Train Model. The
Train Model regulates the cabin toward it.

## Notes

- The unit is °C, the backend unit in `conventions/units.md`. UIs display °F.
- The source is the Train Model design. The Train Controller owners have not confirmed
  it.
