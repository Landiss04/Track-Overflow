**Target:** truth/signals/passengers-boarded.md
**Action:** create
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** `Train_Model_Backend_Design.pdf` §5.2 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; not in the repository

---

# passengers-boarded

**Status:** current
**Owner:** Track Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.2 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30
**Aliases:** Passengers Boarded, boarding count
**Last updated:** 2026-09-30

## Definition

An integer count of passengers boarding the train at a station, sent from the Track Model
to the Train Model.

## Notes

- The count is at most the Passenger Capacity the Train Model last reported. See
  `signals/passenger-capacity.md` for the station sequence.
- The Train Model recomputes its operating mass on every boarding event.
- The source is the Train Model design. The Track Model owner has not confirmed it.
