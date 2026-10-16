**Target:** truth/signals/track-signal.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-16, in the system integration design session: "commanded speed and authority come from Track Controller"

---

# track-signal

**Status:** current
**Owner:** Track Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.3 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; authority as a count of blocks per D013 (team decision including Kevin, asserted by Landis 2026-10-06); commanded speed and authority coming from the Track Controller asserted by Kevin Schillinger 2026-10-16
**Aliases:** Track Signal, track circuit signal, track circuit data
**Last updated:** 2026-10-16

## Definition

Track circuit data sent from the Track Model to the Train Model. It carries two
discrete values with no physical encoding: commanded speed (m/s) and authority (a count
of blocks). The Train Model passes both values through to the Train Controller.

Both values come from the Track Controller.

## Notes

- Commanded speed and authority are the only contents. Suggested speed goes from the
  CTC Office to the Track Controller and never reaches the train.
- Authority is the number of blocks ahead of the train's current block that it may
  still enter, as a non-negative integer; 0 means stop before leaving the current
  block. See [D013](../decisions/D013-authority-block-count.md). This overrides the
  design's reading of authority as a distance to the front of the train.
- Signal pickup failure affects this signal only. Track Info is terrain data and cannot
  fail.
- The source does not settle what the Train Model outputs while signal pickup has
  failed: zeros or stale values.
- The source is the Train Model design. The Track Model owner has not confirmed it.
- Open: how the values get from the Track Controller onto the track circuit (form,
  keying per block or per train, and timing) is not settled.

## Supersedes

- Authority: previously a block ID naming the destination block (Kevin 2026-09-30); now
  a count of blocks, per D013 (2026-10-06).
