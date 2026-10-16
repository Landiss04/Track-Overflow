**Target:** truth/decisions/D007-station-dwell.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-16, the entry's resolution owner, in the team's review of `documents/system-integration-design.md` (G-SIG-15): "its 45 seconds".

---

# D007-station-dwell

**Status:** current
**Owner:** Kevin
**Provenance:** `Train_Model_Backend_Design.pdf` §5.2 (Locked), supplied by Kevin Schillinger 2026-09-30; conflict with the 60 s Green Line dwell in Schedule v4 resolved for 45 s by Kevin Schillinger 2026-10-16
**Aliases:** dwell time, station dwell, 45 second dwell
**Last updated:** 2026-10-16

## Context

At each station, passengers disembark and board. Every module that plans or times a stop
needs the same value for how long a train stays at a station.

## Decision

Station dwell time is 45 s, fixed.

## Consequences

- The dwell does not vary by station or passenger count.
- The source does not say which module enforces the dwell.

## Supersedes

- Conflict: `documents/Project_Information/Schedule v4.xlsx` (Green Line Schedule sheet,
  "dwell time (sec)" column) gave 60 s at every Green Line station against this
  entry's 45 s. Resolved for 45 s by Kevin Schillinger, the resolution owner,
  2026-10-16.
