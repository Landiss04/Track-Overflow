**Target:** truth/signals/passengers-boarded.md
**Action:** create
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** `Train_Model_Backend_Design.pdf` §5.2 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; boarding restricted to a station with a door open, asserted by Kevin Schillinger 2026-10-01 in this chat ("passengers can only board at a station w door open"); not in the repository. Replaces the inbox proposal `20260930-2059-passengers-boarded.md`, which did not restrict when boarding can happen.

---

# passengers-boarded

**Status:** current
**Owner:** Track Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.2 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; station and open-door restriction asserted by Kevin Schillinger 2026-10-01
**Aliases:** Passengers Boarded, boarding count
**Last updated:** 2026-10-01

## Definition

An integer count of passengers boarding the train at a station, sent from the Track Model
to the Train Model.

## Notes

- Passengers can only board at a station, with a door open. Because a door can only
  open at 0 mph (`signals/door-command.md`), boarding also happens only while the train
  is stopped.
- The count is at most the Passenger Capacity the Train Model last reported. See
  `signals/passenger-capacity.md` for the station sequence.
- The Train Model recomputes its operating mass on every boarding event.
- This entry does not settle how the Train Model learns that it is at a station.
- The source is the Train Model design. The Track Model owner has not confirmed it.

## Supersedes

- Boarding conditions: previously unrestricted, so a count was applied whenever it
  arrived, including while moving with the doors closed. Kevin Schillinger restricted
  boarding to a station with a door open on 2026-10-01.
