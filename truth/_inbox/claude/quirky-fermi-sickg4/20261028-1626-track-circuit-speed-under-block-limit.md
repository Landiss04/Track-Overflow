**Target:** truth/arbitration/track-circuit-speed-under-block-limit.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** Harry Tye, relayed by Kevin Schillinger 2026-10-28 ("My current vital code will either send CTC speed, half speed, or nothing, it does not perform any clamping, I will change to match Braden")

---

# track-circuit-speed-under-block-limit

**Status:** current
**Owner:** Harry Tye (Track Controller)
**Provenance:** Harry Tye, relayed by Kevin Schillinger 2026-10-28 ("... it does not perform any clamping, I will change to match Braden"): the SW variant's vital code takes the HW variant's clamp
**Aliases:** vital speed clamp, posted-limit clamp, speed clamp, `speed_clamped`
**Last updated:** 2026-10-28

## Definition

A Track Controller never sends a commanded speed above the posted speed limit of the
block it is for. Its vital layer clamps a suggested speed over that limit down to the
limit, in whole m/s, before the track circuit goes to the Track Model. Both variants do
this.

A yellow signal still halves the block's speed, applied to the clamped speed.

## Notes

- This is the Track Controller's own check. It does not replace the CTC Office's rule
  that its suggested speed stays under the block limit
  ([suggested-speed-under-block-limit](suggested-speed-under-block-limit.md)).
- A user PLC program never sees or sets a speed. Only the vital layer reads the
  suggested speed.
