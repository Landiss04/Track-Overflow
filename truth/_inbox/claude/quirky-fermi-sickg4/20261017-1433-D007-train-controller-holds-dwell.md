**Target:** truth/decisions/D007-station-dwell.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** as `20261016-2254-D007-dwell-conflict-resolved.md` on this branch, which this proposal supersedes (deny that one), plus Kevin Schillinger 2026-10-17, answering who holds the 45 s dwell once the Train Model test UI is removed: "assume the train controller holds this for now".

---

# D007-station-dwell

**Status:** current
**Owner:** Kevin
**Provenance:** `Train_Model_Backend_Design.pdf` §5.2 (Locked), supplied by Kevin Schillinger 2026-09-30; conflict with the 60 s Green Line dwell in Schedule v4 resolved for 45 s by Kevin Schillinger 2026-10-16; the Train Controller holding the dwell asserted by Kevin Schillinger 2026-10-17, for now
**Aliases:** dwell time, station dwell, 45 second dwell
**Last updated:** 2026-10-17

## Context

At each station, passengers disembark and board. Every module that plans or times a stop
needs the same value for how long a train stays at a station.

## Decision

Station dwell time is 45 s, fixed.

## Consequences

- The dwell does not vary by station or passenger count.
- The Train Controller holds the dwell. Kevin Schillinger set this on 2026-10-17 as the
  working assumption "for now".

## Supersedes

- Conflict: `documents/Project_Information/Schedule v4.xlsx` (Green Line Schedule sheet,
  "dwell time (sec)" column) gave 60 s at every Green Line station against this
  entry's 45 s. Resolved for 45 s by Kevin Schillinger, the resolution owner,
  2026-10-16.
