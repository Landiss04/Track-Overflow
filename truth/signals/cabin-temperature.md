# cabin-temperature

**Status:** current
**Owner:** Train Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.4 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; unit per `conventions/units.md` as resolved by Kevin 2026-09-30
**Aliases:** Cabin Temp, cabin temperature, actual cabin temperature
**Last updated:** 2026-09-30

## Definition

The actual cabin temperature, sent from the Train Model to the Train Controller.

## Notes

- The Train Model regulates the cabin toward the Temperature Setpoint. The source leaves
  the regulation model and its time constant open.
- The unit is °C, the backend unit in `conventions/units.md`. UIs display °F.
