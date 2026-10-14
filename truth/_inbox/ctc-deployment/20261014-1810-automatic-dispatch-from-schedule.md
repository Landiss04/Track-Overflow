**Target:** truth/decisions/D020-automatic-dispatch-from-schedule.md
**Action:** create
**Proposed by:** Claude on ctc-deployment
**Provenance:** asserted by Landis 2026-10-14 (CTC scheduling algorithm: runs stop in track order, as a first approach that may change; the CTC Office stops trains at their scheduled stations; the schedule's time zero is the simulation start)

---

# D020-automatic-dispatch-from-schedule

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-14 (CTC scheduling algorithm: runs stop in track order, as a first approach that may change; the CTC Office stops trains at their scheduled stations; the schedule's time zero is the simulation start)
**Aliases:** automatic dispatch, auto dispatch, scheduling algorithm, schedule runs, track order
**Last updated:** 2026-10-14

## Context

In automatic mode the CTC Office loads and runs a train schedule (REQ-FUNC-007,
REQ-FUNC-010). The schedule, `documents/Project_Information/Schedule v4.xlsx` (as
`utils/schedule_v4.json`), lists each run's timed stops in block-number order. A train
cannot always run that order: on the Green line, out of the yard at 63 a train reaches
Glenbury (65) first and Pioneer (2) near the end, and block 1 cannot run to block 2.

## Decision

- **Track order.** A run visits the named stations the schedule lists for it in the
  order the track reaches them from its line's yard, then returns to the yard. This is
  a first approach and may change.
- **The CTC Office stops the trains.** It sends a train to its next scheduled station
  (its authority ends there), holds it there for the station dwell
  ([D007](D007-station-dwell.md)), then sends it on to the next.
- **Time zero is the simulation start**, 05:00:00
  ([D017](D017-shared-simulation-clock.md)). A run is due to leave the yard at 05:00
  plus its departure time in the schedule.

## Consequences

- The schedule's per-stop times are not used as given, since they assume the
  block-number order. Each run's departure time is used, and its time at each station
  follows from its route and the dwells before it.
- Blocks the schedule times that are not named stations are not stops.
- Nothing is dispatched or moved on outside automatic mode, or while the dispatcher has
  paused automatic dispatch.
- The proposed D012 (on `Train-Ctrl_SW`) has an automatic train stop at every station
  by itself. Both can hold: the train may also stop at stations its run passes
  through.
