**Target:** truth/signals/passenger-capacity.md
**Action:** replace
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** Kevin Schillinger 2026-10-07, in chat: "i said before and ill say again passengers hould be able to board when the trtain is stopped w doors open". Drops "Passengers board only at a station" and makes the station sequence a stop sequence. Companion to `20261007-1347-passengers-boarded.md`. Replaces the entry on the truth branch; no earlier proposal on this branch.

---

# passenger-capacity

**Status:** current
**Owner:** Train Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.2 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; alighting at any stop with a door open, asserted by Kevin Schillinger 2026-10-07; boarding at any stop with a door open, asserted by Kevin Schillinger 2026-10-07
**Aliases:** Passenger Capacity, remaining capacity, boarding capacity
**Last updated:** 2026-10-07

## Definition

An integer count of the passengers the train can still take on. The Train Model reports
it to the Track Model, computing it after it draws the disembark count.

## Notes

- Stop sequence:
  1. The Train Model draws a disembark count, bounded by the passengers onboard.
  2. The Train Model reports the remaining capacity.
  3. The Track Model sends Passengers Boarded, which is at most that capacity.
  4. The Train Model recomputes its mass.
- Passengers alight and board at any stop with a door open, at a station or not.
- Passengers onboard range from 0 to 222. Crew is fixed at 5, counted separately, and
  does not reduce passenger capacity.
- Disembark counts are not reported. Throughput is handled between the Track Model and
  the CTC Office.
- The source is the Train Model design. The Track Model owner has not confirmed it.

## Supersedes

- Where passengers board: previously only at a station; now at any stop with a door
  open (Kevin Schillinger 2026-10-07).
