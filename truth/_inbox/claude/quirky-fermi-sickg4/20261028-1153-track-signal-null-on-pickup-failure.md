**Target:** truth/signals/track-signal.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-28 ("modify the train model to send null for speed and authority on a signal pickup failure simulating invalid data"); builds on pending proposal `20261020-1342-track-signal-sdd-review.md`, whose pickup-failure note it supersedes; rest of the entry as there

---

# track-signal

**Status:** current
**Owner:** Track Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.3 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; authority as a count of blocks per D013 (team decision including Kevin, asserted by Landis 2026-10-06); commanded speed and authority sent by the Track Controller to a block and cleared by the Track Model after delivery, and commanded speed as a float, asserted by Kevin Schillinger 2026-10-16; the next block preloaded, agreed in the CTC Office's answers of 2026-10-20, relayed by Kevin Schillinger; a block not commanded on the latest tick reading zero, accepted by Kevin Schillinger 2026-10-20; null output under signal pickup failure, asserted by Kevin Schillinger 2026-10-28
**Aliases:** Track Signal, track circuit signal, track circuit data
**Last updated:** 2026-10-28

## Definition

Track circuit data sent from the Track Model to the Train Model. It carries two
discrete values with no physical encoding: commanded speed (m/s, a float) and
authority (a count of blocks). The Train Model passes both values through to the Train
Controller.

Both values come from the Track Controller, which sends them to a block: the block a
train occupies and, ahead of it, the next block that train will enter
([suggested-speed](suggested-speed.md)). The train in a block is assumed to be the one
its values are for. Once the Track Model has sent a block's commanded speed and
authority to the Train Model, it clears them back to zero. A block the Track Controller
did not command on the latest tick reads zero.

## Notes

- Commanded speed and authority are the only contents. Suggested speed goes from the
  CTC Office to the Track Controller and never reaches the train.
- Authority is the number of blocks ahead of the train's current block that it may
  still enter, as a non-negative integer; 0 means stop before leaving the current
  block. See [D013](../decisions/D013-authority-block-count.md). This overrides the
  design's reading of authority as a distance to the front of the train.
- Signal pickup failure affects this signal only. Track Info is terrain data and cannot
  fail.
- While signal pickup has failed, the Train Model passes on commanded speed and
  authority as null: invalid data, not a valid 0. Track Info terrain values remain
  unaffected.
- The source is the Train Model design. The Track Model owner has not confirmed it.

## Supersedes

- Pickup failure output: previously commanded speed 0 m/s and authority 0 blocks
  (Kevin Schillinger 2026-10-20); now null, so that a valid 0/0 cannot be taken for a
  pickup failure (Kevin Schillinger 2026-10-28).
