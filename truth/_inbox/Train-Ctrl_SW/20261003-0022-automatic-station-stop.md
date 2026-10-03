**Target:** truth/decisions/D012-automatic-station-stop.md
**Action:** create
**Proposed by:** Claude on Train-Ctrl_SW
**Provenance:** asserted by Jonathan Tsang 2026-10-02

---

# D012-automatic-station-stop

**Status:** current
**Owner:** Train Controller
**Provenance:** asserted by Jonathan Tsang 2026-10-02
**Aliases:** automatic station stop, station stop, dwell includes doors
**Last updated:** 2026-10-02

## Context

D007 fixes the station dwell at 45 s but does not say which module enforces it, whether
an automatic train stops at every station, or how the doors fit inside the dwell.

## Decision

- In Automatic mode the train stops at every station.
- While stopped it waits for the D007 dwell of 45 s.
- The 45 s includes the time to open and to close the doors.

## Consequences

- Door opening and closing happen within the dwell, not before or after it.
- In Automatic mode the train stopping at the station is Train Controller behaviour,
  consistent with D009 (control belongs to the Train Controller).
- This entry does not change the D007 value.
