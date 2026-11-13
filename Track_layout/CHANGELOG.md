# TrackModel — changes for review

Changes to the owners' module code during Phase 5 integration, for review.

---

## 2026-10-27 — Owner answers TM-1 and TM-3

From the Track Model owner's answers to `documents/module-owner-review.md`
(2026-10-26), relayed by Kevin.

- TM-1: ticket sales are time-based. `TrackConfig.ticket_probability` (a chance
  per tick) is replaced by `tickets_per_minute` (default 12 per station); each
  tick's chance is `min(1, tickets_per_minute * dt / 60)`, 0.02 at the 0.1 s
  tick as before. Tests pass rates (600 and 300 a minute for the old 1.0 and
  0.5), and a new test checks the rate at 0.1 s and 0.5 s ticks.
- TM-3: the Track Model switches the heaters itself (D026): every section's
  heater is on at or below 0 °C ambient (`HEATER_ON_AT_C`) and off above it,
  with no hysteresis; a tick with no ambient keeps them as they were. Heater
  commands are still accepted on the boundary but not applied. Heater tests
  and manual test TC-27 are rewritten for the rule.
- TM-2 (B1 fixed): signals sit at switches, one per switch at its point,
  named by the switch's ID (`layout._signal_blocks`), as Braden relayed from the
  professor. Every tick each train is sent the light ahead (`_signal_seen`): the
  first switch along its way, with the switches as set, that it comes onto from
  the point's fixed side, where the light faces. Tests are moved to the
  switch-named lights and rewritten for the every-tick light; the harness
  (`common/harness/track_devices.py`) now stands each light at its point.
  Neither Track Controller changes: both already name signals by switch.

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

## 2026-10-22 — Limit the yard-entry validation exception

The exception allowing an annotated yard return on a `from_yard` switch
is now limited to Red block 9. Green's entry-only switch at 63 still
rejects an added yard exit, while the unchanged course files load. Tests
also reject a missing Green-57 yard return. No track data changed.
