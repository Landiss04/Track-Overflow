# suggested-speed-stops-within-authority

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-06 (issue a safe suggested speed so trains do not run up on each other); service deceleration 1.2 m/s² from `modules/train-model.md` (Datasheet)
**Aliases:** safe suggested speed, authority-aware speed, braking speed
**Last updated:** 2026-10-06

## Definition

The CTC Office's suggested speed for a train is never more than the speed from which
the train can stop, at the service deceleration, within its authority:
√(2 × 1.2 m/s² × d), rounded down to a whole m/s, where d is the total length of the
blocks within its authority. With an authority of 0 the suggested speed is 0.

It is also never more than the limit in
[suggested-speed-under-block-limit](suggested-speed-under-block-limit.md); the lower of
the two applies.

## Notes

- The distance left in the train's own block is not counted, because the CTC Office
  does not know which way the train is heading through it. This is on the safe side.
- 1.2 m/s² is the service deceleration at 2/3 load. Whether braking scales with load
  is open in `signals/service-brake-command.md`.
