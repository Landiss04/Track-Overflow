**Target:** truth/signals/passengers-boarded.md
**Action:** replace
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** Kevin Schillinger 2026-10-07, in chat: "i said before and ill say again passengers hould be able to board when the trtain is stopped w doors open". Drops the station restriction he asserted 2026-10-01. Replaces the entry on the truth branch; no earlier proposal on this branch.

---

# passengers-boarded

**Status:** current
**Owner:** Track Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.2 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; boarding only while the train is at rest with a door open, asserted by Kevin Schillinger 2026-10-07; boarding at any such stop, station or not, asserted by Kevin Schillinger 2026-10-07
**Aliases:** Passengers Boarded, boarding count
**Last updated:** 2026-10-07

## Definition

An integer count of passengers boarding the train, sent from the Track Model to the
Train Model.

## Notes

- Passengers board whenever the train is at rest with a door open, at a station or
  not. This is a rule in its own right: the Train Model enforces no door interlock
  (`signals/door-command.md`), so a door being open does not imply the train has
  stopped.
- The count is at most the Passenger Capacity the Train Model last reported. See
  `signals/passenger-capacity.md` for the stop sequence.
- The Train Model recomputes its operating mass on every boarding event.
- This entry does not settle which module enforces the at-rest restriction.
- The source is the Train Model design. The Track Model owner has not confirmed it.

## Supersedes

- Where passengers board: previously only at a station; now at any stop with a door
  open, station or not (Kevin Schillinger 2026-10-07).
