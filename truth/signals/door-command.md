# door-command

**Status:** current
**Owner:** Train Controller
**Provenance:** `Train_Model_Backend_Design.pdf` §5.6 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; door interlock asserted by Kevin Schillinger 2026-10-01
**Aliases:** Door Command, doors command, open doors command
**Last updated:** 2026-10-01

## Definition

Two booleans, `bool[2]`, sent from the Train Controller to the Train Model. They command
the left and right doors: true opens a side and false closes it.

## Notes

- The Train Model enforces a door interlock: a door can only open while the train is
  stopped, at 0 mph. A command to open a door while the train is moving does not open
  it.
- The Train Model reports the actual door state back as Door State, a separate signal,
  so Door State can differ from Door Command while the interlock holds a door closed.
- The source is the Train Model design. The Train Controller owners have not confirmed
  it.
