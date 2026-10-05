**Target:** truth/signals/track-signal.md
**Action:** replace
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** authority as a count of blocks asserted by Kevin Schillinger 2026-10-05 in this chat ("Authority has been changed to be the number of blocks the train is able to travel before it must stop … update it to be an integer value"); not in the repository. Companion to the inbox proposal `20261005-0744-units-authority-block-count.md`.

---

# track-signal

**Status:** current
**Owner:** Track Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.3 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; authority as a count of blocks per `conventions/units.md`, asserted by Kevin Schillinger 2026-10-05
**Aliases:** Track Signal, track circuit signal, track circuit data
**Last updated:** 2026-10-05

## Definition

Track circuit data sent from the Track Model to the Train Model. It carries two
discrete values with no physical encoding: commanded speed (m/s) and authority (an
integer count of blocks). The Train Model passes both values through to the Train
Controller.

## Notes

- Commanded speed and authority are the only contents. Suggested speed goes from the
  CTC Office to the Track Controller and never reaches the train.
- Authority is the number of blocks the train may travel before it must stop, per
  `conventions/units.md` (Kevin Schillinger 2026-10-05). This overrides the design's
  reading of authority as a distance to the front of the train.
- Signal pickup failure affects this signal only. Track Info is terrain data and cannot
  fail.
- The source does not settle what the Train Model outputs while signal pickup has
  failed: zeros or stale values.
- The source is the Train Model design. The Track Model owner has not confirmed it.

## Supersedes

- Authority: previously the ID of the destination block the train may travel up to
  (Kevin 2026-09-30); now the number of blocks the train may travel before it must
  stop (Kevin Schillinger 2026-10-05).
