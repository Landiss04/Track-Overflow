# door-state

**Status:** current
**Owner:** Train Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.6 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; also sent to the Track Model, asserted by Kevin Schillinger 2026-10-16
**Aliases:** Door State, doors state, door status, doors open
**Last updated:** 2026-10-16

## Definition

Two booleans, `bool[2]`, sent from the Train Model to the Train Controller and to the
Track Model. They report whether the left and right doors are actually open (true) or
closed (false).

## Notes

- This is the state the Train Model reports back in response to Door Command.

## Supersedes

- Consumers: previously the Train Controller only; now the Track Model too (Kevin
  Schillinger 2026-10-16).
