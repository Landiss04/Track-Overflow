**Target:** truth/decisions/D007-station-dwell.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** the current D007 on `truth`, plus Kevin Schillinger's direct statement of 2026-10-20 in the integration session: "station dwell is scheduled by the ctc but enforced by the train controller. 45s". It replaces the working assumption of 2026-10-17 that the Train Controller holds the dwell "for now".

---

# D007-station-dwell

**Status:** current
**Owner:** Kevin
**Provenance:** `Train_Model_Backend_Design.pdf` §5.2 (Locked), supplied by Kevin Schillinger 2026-09-30; conflict with the 60 s Green Line dwell in Schedule v4 resolved for 45 s by Kevin Schillinger 2026-10-16; the station-stop sequence proposed in `documents/system-integration-design.md` and accepted by Kevin Schillinger 2026-10-20, with departure on commanded speed above zero; stops at scheduled stations only, asserted by Kevin Schillinger 2026-10-20; the dwell scheduled by the CTC Office and enforced by the Train Controller, asserted by Kevin Schillinger 2026-10-20
**Aliases:** dwell time, station dwell, 45 second dwell
**Last updated:** 2026-10-20

## Context

At each station, passengers disembark and board. Every module that plans or times a stop
needs the same value for how long a train stays at a station.

## Decision

Station dwell time is 45 s, fixed. The CTC Office schedules the dwell, and the Train
Controller enforces it.

## Consequences

- The dwell does not vary by station or passenger count.
- The CTC Office's schedule allows the 45 s dwell at each scheduled station.
- The Train Controller enforces it. At a station stop it opens the platform-side doors,
  holds the train for at least the 45 s dwell, closes the doors, and departs only once
  its commanded speed is above zero.
- A train stops only at its scheduled stations, where its authority ends, and runs
  through the others (D020).

## Supersedes

- Who holds the dwell: previously the Train Controller, as the working assumption "for
  now" (Kevin Schillinger 2026-10-17); now scheduled by the CTC Office and enforced by
  the Train Controller (Kevin Schillinger 2026-10-20).
