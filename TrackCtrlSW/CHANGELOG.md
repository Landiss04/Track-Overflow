# TrackCtrlSW — changes for review

Changes to the owners' module code during Phase 5 integration, for review.

---

## 2026-10-22 — Red yard and integration inputs

Correction commit: `5d51051` (course data restoration and reader agreement).

`track_ctrl/layout.py` gained the Red-9 interpretation in `f27ba4e`
(Phase 5 K2, Kevin Schillinger 2026-10-21). This changes Harry Tye's layout
reader so the physical yard connection is at block 9 in section C.

The 2026-10-22 correction preserves the course file exactly and interprets
the stale block-75 yard adjacency in the reader. The current assumption is
point 9, NORMAL to 8, REVERSE to yard, fixed side 10 and light on 10, so a
train leaving the yard proceeds 9 → 10. The Track Model owner and Braden
must confirm these legs; Kevin's statement establishes the yard location
and immutable data, not those detailed switch semantics.

The SW vital layer remains a separate follow-up requested by Kevin; this
entry records the reader change and does not remove that layer.
