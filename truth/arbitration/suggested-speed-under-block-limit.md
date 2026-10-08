# suggested-speed-under-block-limit

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-06 (suggested speed a little under the speed limit, 1 m/s below; the yard is a black box); `documents/srs-filled.md` REQ-FUNC-005.1 (speed limit within safety limits)
**Aliases:** suggested speed rule, CTC speed limit, speed within safety limits
**Last updated:** 2026-10-06

## Definition

The CTC Office's suggested speed for a train (see [suggested-speed](../signals/suggested-speed.md))
is a little under the speed limit of the block the train is in: that block's speed limit
in m/s, rounded down to a whole number, less 1 m/s, and never below 0.

The yard is a black box: a train gets a suggested speed and authority only once it is
reported on the track, computed from the block it is in then. A train with an order but
not yet reported gets neither.

## Notes

- Expected to change once several trains share the track: the suggested speed will
  then be adjusted on the fly to keep them apart.
