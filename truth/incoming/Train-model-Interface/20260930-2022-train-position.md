**Target:** truth/signals/train-position.md
**Action:** create
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** `Train_Model_Backend_Design.pdf` §5.3 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; not in the repository

---

# train-position

**Status:** current
**Owner:** Train Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.3 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30
**Aliases:** Train Position, position, block and offset
**Last updated:** 2026-09-30

## Definition

The train's position as a block ID plus an offset in m, sent from the Train Model to the
Track Model for occupancy detection.

## Notes

- The block ID comes from Track Info. Block changes are detected from track circuit
  polarity reversal.
- The source leaves open which point on the 32.2 m train the offset is measured from,
  and how block changes work during rollback.
- The source is the Train Model design. The Track Model owner has not confirmed it.
