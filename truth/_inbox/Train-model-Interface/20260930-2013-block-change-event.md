**Target:** truth/signals/block-change-event.md
**Action:** create
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** `Train_Model_Backend_Design.pdf` §5.3 (Locked: polarity-reversal detection) and Interfaces table; type asserted by Kevin Schillinger 2026-09-30

---

# block-change-event

**Status:** current
**Owner:** Train Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.3 (Locked) and Interfaces table; bool type asserted by Kevin Schillinger 2026-09-30
**Aliases:** Block Change Event, block changed, block_changed
**Last updated:** 2026-09-30

## Definition

A `bool` sent from the Train Model to the Track Model. It is true on the tick the train
detects that the track circuit polarity has reversed, which means it has entered a new
block.

## Notes

- The source leaves open whether this signal is redundant. The Track Model sets the
  polarity itself, so it may already know when a block changes. This needs the Track
  Model's agreement.
- The source also leaves open how a block change works during rollback, when the train
  moves backward into the previous block.

## Supersedes

- Type: previously `int` in the design's Interfaces table; changed to `bool` (Kevin
  2026-09-30).
