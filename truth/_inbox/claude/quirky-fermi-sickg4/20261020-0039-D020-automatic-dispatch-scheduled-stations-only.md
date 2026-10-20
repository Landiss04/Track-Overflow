**Target:** truth/decisions/D020-automatic-dispatch-from-schedule.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4 (re-filed; first proposed by Claude on ctc-deployment)
**Provenance:** re-filed at the CTC Office's request in the CTC Office's answers of 2026-10-20, relayed by Kevin Schillinger. First proposed as `ctc-deployment/20261014-1937-automatic-dispatch-scheduled-stations-only.md`. Commit `201708b` removed it from the inbox as promoted, but `truth/_promotions.md` has no record of it and `truth` does not hold it. The entry is unchanged. It has the CTC Office hold a train at a station for the dwell, while the proposed D007 has the Train Controller hold it; under both, a train leaves once both have let it go.

---

# D020-automatic-dispatch-from-schedule

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-14 (CTC scheduling algorithm: runs stop in track order, as a first approach that may change; the CTC Office stops trains at their scheduled stations; the schedule's time zero is the simulation start); trains stop only at the stations they are scheduled at, confirmed by Landis 2026-10-14
**Aliases:** automatic dispatch, auto dispatch, scheduling algorithm, schedule runs, track order, scheduled stops
**Last updated:** 2026-10-14

## Context

In automatic mode the CTC Office loads and runs a train schedule (REQ-FUNC-007,
REQ-FUNC-010). The schedule, `documents/Project_Information/Schedule v4.xlsx` (as
`utils/schedule_v4.json`), lists each run's timed stops in block-number order. A train
cannot always run that order: on the Green line, out of the yard at 63 a train reaches
Glenbury (65) first and Pioneer (2) near the end, and block 1 cannot run to block 2.

## Decision

- **Scheduled stations only.** A train stops only at the stations its run is scheduled
  at. A station on its way that is not on its schedule, it runs through without
  stopping. A scheduled station is a block the schedule lists for the run that the
  track layout marks as a station, named or not.
- **Track order.** A run visits its scheduled stations in the order the track reaches
  them from its line's yard, then returns to the yard. This is a first approach and may
  change.
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
- Blocks the schedule times that are not stations are not stops.
- Nothing is dispatched or moved on outside automatic mode, or while the dispatcher has
  paused automatic dispatch.

## Notes

- Contradicts the proposed D012 (on `Train-Ctrl_SW`), under which a train in automatic
  mode stops at every station by itself. Under this decision it stops only at its
  scheduled stations, which are where its authority ends.
