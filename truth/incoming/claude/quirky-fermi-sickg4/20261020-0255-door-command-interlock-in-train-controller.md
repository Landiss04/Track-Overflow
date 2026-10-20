**Target:** truth/signals/door-command.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** Kevin Schillinger 2026-10-20, the owner of this entry's Pending item: "Adopt the door interlock", answering the proposal that the Train Controller command zero power whenever a door is open, with doors opening only when stopped, on the platform side. Settles the Pending section, which this replacement removes.

---

# door-command

**Status:** current
**Owner:** Train Controller
**Provenance:** `Train_Model_Backend_Design.pdf` §5.6 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; the door interlock not enforced by the Train Model, asserted by Kevin Schillinger 2026-10-06, pending the course instructor; the door interlock enforced by the Train Controller asserted by Kevin Schillinger 2026-10-20
**Aliases:** Door Command, doors command, open doors command
**Last updated:** 2026-10-20

## Definition

Two booleans, `bool[2]`, sent from the Train Controller to the Train Model. They command
the left and right doors: true opens a side and false closes it.

## Notes

- The Train Model enforces no door interlock. It opens and closes each door as
  commanded, at any speed, and reports the doors as Door State
  (`signals/door-state.md`), which therefore matches Door Command.
- The Train Controller enforces the door interlock. It opens a door only while the train
  is stopped, and only on the platform side, and it commands zero power whenever a door
  is open ([power-command](power-command.md)).
- The source is the Train Model design. The Train Controller owners have not confirmed
  it.

## Supersedes

- Door interlock: previously enforced by the Train Model, which opened a door only at
  0 mph (Kevin Schillinger 2026-10-01); now not enforced by it, pending the course
  instructor (Kevin Schillinger 2026-10-06).
- Door interlock owner: previously pending, with the course instructor asked; now the Train
  Controller (Kevin Schillinger 2026-10-20).
