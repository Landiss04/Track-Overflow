**Target:** truth/decisions/D007-station-dwell.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** as `20261020-0039-D007-depart-on-commanded-speed.md` on this branch, which this proposal supersedes (deny that one), plus Kevin Schillinger 2026-10-20, on which stations a train stops at: "stop at scheduled only". Matches the proposed D020.

---

# D007-station-dwell

**Status:** current
**Owner:** Kevin
**Provenance:** `Train_Model_Backend_Design.pdf` §5.2 (Locked), supplied by Kevin Schillinger 2026-09-30; conflict with the 60 s Green Line dwell in Schedule v4 resolved for 45 s by Kevin Schillinger 2026-10-16; the Train Controller holding the dwell asserted by Kevin Schillinger 2026-10-17, for now; the station-stop sequence proposed in `documents/system-integration-design.md` and accepted by Kevin Schillinger 2026-10-20, with departure on commanded speed above zero; stops at scheduled stations only, asserted by Kevin Schillinger 2026-10-20
**Aliases:** dwell time, station dwell, 45 second dwell
**Last updated:** 2026-10-20

## Context

At each station, passengers disembark and board. Every module that plans or times a stop
needs the same value for how long a train stays at a station.

## Decision

Station dwell time is 45 s, fixed.

## Consequences

- The dwell does not vary by station or passenger count.
- The Train Controller holds the dwell. Kevin Schillinger set this on 2026-10-17 as the
  working assumption "for now".
- At a station stop the Train Controller opens the platform-side doors, holds the
  train for the dwell, closes the doors, and departs only once its commanded speed is
  above zero.
- A train stops only at its scheduled stations, where its authority ends, and runs
  through the others (D020).

## Supersedes

- Conflict: `documents/Project_Information/Schedule v4.xlsx` (Green Line Schedule sheet,
  "dwell time (sec)" column) gave 60 s at every Green Line station against this
  entry's 45 s. Resolved for 45 s by Kevin Schillinger, the resolution owner,
  2026-10-16.
