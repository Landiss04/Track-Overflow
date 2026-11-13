**Target:** truth/decisions/D020-automatic-dispatch-from-schedule.md
**Action:** replace
**Proposed by:** Claude on integrate/quirky-into-development-resolved
**Provenance:** asserted by Landis 2026-11-03: "auto dispatch needs to start the moment that the schedule is uploaded … when the run button is pressed we need to query to see if a schedule has been loaded, if so that moment regardless of simulation time is T = 0 … if the simulation is running already and we load a schedule … same logic holds, where that is T = 0." Only the time zero changes; the rest of the entry is as on `truth`.

---

# D020-automatic-dispatch-from-schedule

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-14 (CTC scheduling algorithm: runs stop in track order, as a first approach that may change; the CTC Office stops trains at their scheduled stations); trains stop only at the stations they are scheduled at, confirmed by Landis 2026-10-14; the schedule's time zero is the moment it starts, asserted by Landis 2026-11-03
**Aliases:** automatic dispatch, auto dispatch, scheduling algorithm, schedule runs, track order, scheduled stops, schedule time zero, T = 0
**Last updated:** 2026-11-03

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
- **Time zero is the moment the schedule starts**: the simulation time when the shared
  clock ([D017](D017-shared-simulation-clock.md)) runs with the schedule loaded. That
  is when the dispatcher presses Run with a schedule loaded, or the moment a schedule
  is loaded while the clock is already running, whatever the simulation time is then.
  A run is due to leave the yard at time zero plus its departure time in the schedule.
  Loading a schedule again starts it again.

## Consequences

- The schedule's per-stop times are not used as given, since they assume the
  block-number order. Each run's departure time is used, and its time at each station
  follows from its route and the dwells before it.
- Runs keep the schedule's headway however late it is loaded: none is due before time
  zero, so they do not all leave together.
- Blocks the schedule times that are not stations are not stops.
- Nothing is dispatched or moved on outside automatic mode, or while the dispatcher has
  paused automatic dispatch.

## Notes

- Contradicts the proposed D012 (on `Train-Ctrl_SW`), under which a train in automatic
  mode stops at every station by itself. Under this decision it stops only at its
  scheduled stations, which are where its authority ends.

## Supersedes

- Time zero: previously the simulation start, 05:00:00. A schedule loaded later then
  had every run due by that time dispatched at once, piling trains up on the yard exit
  block (Landis 2026-11-03).
