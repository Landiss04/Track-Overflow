**Target:** truth/signals/block-occupancy.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4 (re-filed; first proposed by Claude on ctc-deployment)
**Provenance:** re-filed at the CTC Office's request in the CTC Office's answers of 2026-10-20, relayed by Kevin Schillinger. First proposed as `ctc-deployment/20261012-2122-block-occupancy-only-train-information.md`. Commit `61f4a28` removed it from the inbox as promoted, but `truth/_promotions.md` has no record of it and `truth` does not hold it. The entry is unchanged.

---

# block-occupancy

**Status:** current
**Owner:** Track Controller
**Provenance:** asserted by Landis 2026-10-02 (CTC architecture diagram, `ctc-architecture.html`); occupancy as all the CTC Office learns about trains, with failures reported as occupancy, asserted by Landis 2026-10-12 (CTC module feedback)
**Aliases:** Block Occupancy, occupancy
**Last updated:** 2026-10-12

## Definition

Occupancy of each block as a boolean, keyed by line and block ID, sent from the Track
Controller to the CTC Office.

It is all the CTC Office learns about trains. It carries no train IDs, no position
within a block and no speed. A failed block (broken rail, track circuit or power) is
reported as occupied, so occupancy does not say whether a train or a failure occupies a
block.

## Notes

- The CTC Office works out which of its trains occupies which block, and which
  occupied blocks are failures:
  [train-tracking-from-occupancy](../arbitration/train-tracking-from-occupancy.md).
- How the Track Controller learns occupancy from the Track Model is outside this entry.
- The Track Controller owner has not confirmed it.

## Supersedes

- What the CTC Office receives: previously, alongside occupancy, each train's ID,
  block, position in the block and speed, and a list of failed blocks with their kind
  (on the CTC's own boundary, never recorded in this store). Now occupancy only (Landis
  2026-10-12).
