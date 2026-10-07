# door-command

**Status:** current
**Owner:** Train Controller
**Provenance:** `Train_Model_Backend_Design.pdf` §5.6 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; the door interlock not enforced by the Train Model, asserted by Kevin Schillinger 2026-10-06, pending the course instructor
**Aliases:** Door Command, doors command, open doors command
**Last updated:** 2026-10-06

## Definition

Two booleans, `bool[2]`, sent from the Train Controller to the Train Model. They command
the left and right doors: true opens a side and false closes it.

## Notes

- The Train Model enforces no door interlock. It opens and closes each door as
  commanded, at any speed, and reports the doors as Door State
  (`signals/door-state.md`), which therefore matches Door Command.
- No module is recorded as keeping a door shut while the train moves. Kevin
  Schillinger accepts that gap until the interlock's owner is settled.
- The source is the Train Model design. The Train Controller owners have not confirmed
  it.

## Pending

Which module enforces the door interlock (a door opens only at 0 mph). Kevin
Schillinger believes it is not the Train Model and has asked the course instructor.
Owner: Kevin Schillinger, to record the answer here.

## Supersedes

- Door interlock: previously enforced by the Train Model, which opened a door only at
  0 mph (Kevin Schillinger 2026-10-01); now not enforced by it, pending the course
  instructor (Kevin Schillinger 2026-10-06).
