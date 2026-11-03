**Target:** truth/decisions/D041-ctc-not-told-of-track-failures.md
**Action:** create
**Proposed by:** Integration on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-11-02, answering whether the CTC Office should learn of track failures from the Track Model or not at all (TrackCtrlSW discrepancy C1): "ctc doesn't learn of failures at all"

---

# D041-ctc-not-told-of-track-failures

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin Schillinger 2026-11-02, answering whether the CTC Office should learn of track failures from the Track Model or not at all (TrackCtrlSW discrepancy C1): "ctc doesn't learn of failures at all"
**Aliases:** C1, track failure report, TrackFailureReport, CTC failure input, FAIL_n to CTC
**Last updated:** 2026-11-02

## Context

The SW Track Controller has no failure input: it sees a track failure only as an
occupied block. The HW variant reads a failure per block and includes it in its
report to the CTC Office. The open question was whether the CTC Office should learn
of track failures from the Track Model instead, or not at all.

## Decision

The CTC Office does not learn of track failures at all. No module sends it a track
failure, from either Track Controller variant or the Track Model.

## Consequences

- The harness passes no track failure to the CTC Office, whatever a Track
  Controller variant reports.
- The CTC Office has no track failure input.
