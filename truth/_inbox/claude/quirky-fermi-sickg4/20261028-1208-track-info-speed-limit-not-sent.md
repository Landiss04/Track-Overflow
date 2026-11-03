**Target:** truth/signals/track-info.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** the Train Controller owner, relayed by Kevin Schillinger 2026-10-28 ("Remove the speed limit send that's something I don't know"; "The speed limit for me is the cmd speed"); `Train-Ctrl_HW/REQUIREMENTS.md` M1; rest of the entry as on origin/truth

---

# track-info

**Status:** current
**Owner:** Track Model
**Provenance:** `Train_Model_Backend_Design.pdf` §1 and §5.3 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; grade unit per `conventions/units.md` as resolved by Kevin 2026-09-30; station name as a sixth field asserted by Kevin Schillinger 2026-10-16; speed limit not sent on to the Train Controller, asserted by the Train Controller owner and relayed by Kevin Schillinger 2026-10-28
**Aliases:** Track Info, block info, terrain info
**Last updated:** 2026-10-28

## Definition

Terrain data for the block the train occupies, sent from the Track Model to the Train
Model on every tick. It has six fields: grade (deg), elevation (m), speed limit (m/s),
block polarity (`bool`), block ID, and station name.

## Notes

- Track Info is terrain data and cannot fail. Signal pickup failure affects the Track
  Signal only.
- The Train Model uses grade on every tick in its physics. Grade is carried here, not in
  the Beacon, because beacons exist only near stations.
- The Train Model does not pass the speed limit on to the Train Controller. The Train
  Controller takes commanded speed ([track-signal](track-signal.md)) as its speed
  limit.
- The Train Model detects block changes from polarity reversal. See
  `signals/block-change-event.md`.
- Grade is in degrees, the backend unit in `conventions/units.md`. Layout files give
  grade in percent, and the loader converts on read. Block ID follows
  `conventions/identifiers.md`.
- The source lists carrying grade in Track Info rather than the Beacon as needing the
  Track Model's agreement. The Track Model owner has not confirmed any of this entry.
- Open: the station name's value for a block with no station is not stated.

## Supersedes

- Fields: previously five, without the station name; now six (Kevin Schillinger
  2026-10-16).
- Speed limit: previously passed through to the Train Controller, provisionally
  (Train Model design); now not sent, as the Train Controller takes commanded speed as
  its limit (Train Controller owner, relayed by Kevin Schillinger 2026-10-28).
