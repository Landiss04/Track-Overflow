# failure-status

**Status:** current
**Owner:** Train Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.95 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; element order and brake failure disabling both brakes asserted by Kevin Schillinger 2026-09-30
**Aliases:** Failure Status, train failures, Train Model failures
**Last updated:** 2026-09-30

## Definition

Three independent booleans, `bool[3]`, reported by the Train Model to the Train
Controller. Element 0 is engine failure, element 1 is signal pickup failure, and element
2 is brake failure.

## Notes

- Failures are injected by Murphy from the Train Model UI. They are not a cross-module
  input.
- The three failures compose. Any combination is valid, including all three at once.
- Engine failure zeroes traction. Signal pickup failure affects the Track Signal only.
- Brake failure disables both the service brake and the emergency brake, including a
  passenger pull.
