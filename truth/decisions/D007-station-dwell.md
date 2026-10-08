# D007-station-dwell

**Status:** current
**Owner:** Kevin
**Provenance:** `Train_Model_Backend_Design.pdf` §5.2 (Locked), supplied by Kevin Schillinger 2026-09-30
**Aliases:** dwell time, station dwell, 45 second dwell
**Last updated:** 2026-10-02

## Context

At each station, passengers disembark and board. Every module that plans or times a stop
needs the same value for how long a train stays at a station.

## Decision

Station dwell time is 45 s, fixed.

## Consequences

- The dwell does not vary by station or passenger count.
- The source does not say which module enforces the dwell.

## Conflict

- 45 s at every station: `Train_Model_Backend_Design.pdf` §5.2 (Locked), supplied by Kevin
  Schillinger 2026-09-30 (the decision above).
- 60 s at every Green Line station: `documents/Project_Information/Schedule v4.xlsx`, Green
  Line Schedule sheet, "dwell time (sec)" column. The Red Line sheet gives no dwell.

**Resolution owner:** Kevin

