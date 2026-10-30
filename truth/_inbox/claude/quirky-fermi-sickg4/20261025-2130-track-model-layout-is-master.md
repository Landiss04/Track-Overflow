**Target:** truth/decisions/track-model-layout-is-master.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** Landis, reply to `documents/module-owner-review.md` LAYOUT-1, relayed by Kevin Schillinger 2026-10-25

---

# track-model-layout-is-master

**Status:** current
**Owner:** Track Model
**Provenance:** Landis, reply to module owner review LAYOUT-1, relayed by Kevin Schillinger 2026-10-25
**Aliases:** master layout, layout authority, track layout reader, Red block 9 yard connection
**Last updated:** 2026-10-25

## Decision

- The Track Model's reading of the track layout (`TrackModel/track_model/layout.py`)
  is the master layout every other module follows.
- A module whose own reading of the layout differs from the Track Model's is wrong
  and is corrected to match.
- Where the Track Model's reading itself is in question (such as how Red block 9
  joins the yard), the question is the Track Model owner's. The CTC Office does not
  change track information; it uses the layout only to display and dispatch.

## Notes

- The course layout files themselves stay unchanged (see
  [files-and-paths](../conventions/files-and-paths.md)).
