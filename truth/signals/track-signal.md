# track-signal

**Status:** current
**Owner:** Track Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.3 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; authority as a block ID per `conventions/units.md` as resolved by Kevin 2026-09-30
**Aliases:** Track Signal, track circuit signal, track circuit data
**Last updated:** 2026-09-30

## Definition

Track circuit data sent from the Track Model to the Train Model. It carries two
discrete values with no physical encoding: commanded speed (m/s) and authority (block
ID). The Train Model passes both values through to the Train Controller.

## Notes

- Commanded speed and authority are the only contents. Suggested speed goes from the
  CTC Office to the Track Controller and never reaches the train.
- Authority is the ID of the destination block up to which the train may travel, per
  `conventions/units.md` and `conventions/identifiers.md` (Kevin 2026-09-30). This
  overrides the design's reading of authority as a distance to the front of the train.
- Signal pickup failure affects this signal only. Track Info is terrain data and cannot
  fail.
- The source does not settle what the Train Model outputs while signal pickup has
  failed: zeros or stale values.
- The source is the Train Model design. The Track Model owner has not confirmed it.
