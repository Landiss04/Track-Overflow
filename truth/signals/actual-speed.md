# actual-speed

**Status:** current
**Owner:** Train Model
**Provenance:** `Train_Model_Backend_Design.pdf` §1 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30
**Aliases:** Actual Speed, train speed, velocity
**Last updated:** 2026-09-30

## Definition

The train's actual speed in m/s. The Train Model sends it to both the Train Controller
and the Track Model.

## Notes

- The value is signed. It is negative during rollback, which is allowed and is required
  for brake failure on a grade.
- Brakes and rolling resistance can stop the train but never reverse it. If the speed
  would change sign within one tick, the Train Model sets it to exactly zero instead.
- The source lists how negative velocity and backward block transitions are handled as
  needing the Track Model's agreement.
