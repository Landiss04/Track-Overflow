**Target:** truth/signals/train-position.md
**Action:** replace
**Proposed by:** Codex on claude/quirky-fermi-sickg4
**Provenance:** `Train_Model_Backend_Design.pdf` §5.3 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; Kevin Schillinger’s October 20, 2026 SDD review; documents/Railway_Sim_SDD_Train_Model.md v0.2 §4.9; direct documentation request 2026-10-20

---

# train-position

**Status:** current
**Owner:** Train Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.3 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; Kevin Schillinger’s October 20, 2026 SDD review; documents/Railway_Sim_SDD_Train_Model.md v0.2 §4.9; direct documentation request 2026-10-20
**Aliases:** Train Position, position, block and offset
**Last updated:** 2026-10-20

## Definition

The train's position as a block ID plus an offset in m, sent from the Train Model to the
Track Model for occupancy detection.

## Notes

- The block ID comes from Track Info. Block changes are detected from track circuit
  polarity reversal.
- The offset references the front of the 32.2 m train. It is signed.
- This reference-point decision adds no rollback or block-crossing rule; rollback
  block-transition handling remains outside this entry’s settled scope.
- The source is the Train Model design. The Track Model owner has not confirmed it.

## Supersedes

- Previously left the offset reference point open; Kevin’s review specifies the train’s front.
