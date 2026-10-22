# TrackModel — changes for review

Changes to the owners' module code during Phase 5 integration, for review.

---

## 2026-10-22 — Red yard and integration inputs

Correction commit: `5d51051` (course data restoration and reader agreement).

`track_model/layout.py` gained the Red-9 interpretation in `f27ba4e`
(Phase 5 K2, Kevin Schillinger 2026-10-21). The same commit moved the raw
`yard` adjacency from block 75 to block 9 in `red_line.json`.

Kevin superseded that data edit on 2026-10-22: "the track is a given data
point and can not be modified". The file is restored byte for byte to its
pre-`f27ba4e` course content (SHA-256
`42afbb5505d4cb16e9efb8a3d995409973cd53fdafed4104be997a52c123ca33`).
The reader interprets the yard at block 9. Regression checks enforce the
source bytes and agreement with the controller and harness readers.

Assumption for the Track Model owner and Braden: point 9, NORMAL to 8,
REVERSE to yard, fixed side 10 and light on 10. Yard arrivals can trail
through 9 toward 10; returning from 10, REVERSE selects the yard. This
needs owner confirmation; it is not a correction to the course source.
