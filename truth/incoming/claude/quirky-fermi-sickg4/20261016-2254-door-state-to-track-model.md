**Target:** truth/signals/door-state.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-16 in the team's review of `documents/system-integration-design.md` (G-SIG-9): "Train model should send the doors open signal", answering the design's note that the Track Model needs door state from the Train Model, which sends it nowhere but the Train Controller.

---

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
