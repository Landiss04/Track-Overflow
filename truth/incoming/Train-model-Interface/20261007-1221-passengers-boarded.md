**Target:** truth/signals/passengers-boarded.md
**Action:** replace
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** boarding only while the train is at rest with a door open, asserted by Kevin Schillinger 2026-10-07 in this chat ("the boarding should only be able to happen while the train is at rest and the door is open"), after the door interlock was taken out of the Train Model pending the course instructor (Kevin Schillinger 2026-10-06, inbox proposal `20261006-1908-door-command.md`). Written at Kevin Schillinger's request 2026-10-07 ("write one for the third the removal of the door interlock"); not in the repository. Only the first note, the provenance, the date and the supersedes section change.

---

# passengers-boarded

**Status:** current
**Owner:** Track Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.2 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; station and open-door restriction asserted by Kevin Schillinger 2026-10-01; boarding only while the train is at rest with a door open, asserted by Kevin Schillinger 2026-10-07
**Aliases:** Passengers Boarded, boarding count
**Last updated:** 2026-10-07

## Definition

An integer count of passengers boarding the train at a station, sent from the Track Model
to the Train Model.

## Notes

- Passengers board only at a station, while the train is at rest with a door open. This
  is a rule in its own right: the Train Model enforces no door interlock
  (`signals/door-command.md`), so a door being open does not imply the train has
  stopped.
- The count is at most the Passenger Capacity the Train Model last reported. See
  `signals/passenger-capacity.md` for the station sequence.
- The Train Model recomputes its operating mass on every boarding event.
- This entry does not settle how the Train Model learns that it is at a station, or
  which module enforces the at-rest restriction.
- The source is the Train Model design. The Track Model owner has not confirmed it.

## Supersedes

- At-rest restriction: previously implied by the door interlock, a door opening only at
  0 mph; now stated directly, since the Train Model no longer enforces the interlock
  (Kevin Schillinger 2026-10-07).
