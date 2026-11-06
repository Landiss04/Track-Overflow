**Target:** truth/modules/track-controller/track-controller-hw.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** `documents/module-owner-review-braden.md` (branch `feature/TrackCtrl-HW-vital`, `a5bd465`), SW-1 and HW-1: asserted by Braden Bosilovich 2026-10-26

---

# track-controller-hw

*Any difference observable to a consumer belongs in the contract shard or in the
relevant signal entry, not here.*

**Status:** current
**Owner:** Braden Bosilovich
**Provenance:** asserted by Braden Bosilovich 2026-10-26 (module owner review SW-1, HW-1), `documents/module-owner-review-braden.md` (branch `feature/TrackCtrl-HW-vital`, `a5bd465`)
**Aliases:** HW Track Controller, Track Controller HW, track_ctrl_hw
**Contract:** `truth/modules/track-controller/track-controller.md`
**Last updated:** 2026-10-27

## Import path and entry point

*Unpopulated.*

## Platform and dependencies

*Unpopulated.*

## Build and run

*Unpopulated.*

## Implementation-specific constraints

- The PLC program decides each block's speed, under the vital block's cap at the
  block's limit ([track-controller-vital-plc-block](../../decisions/track-controller-vital-plc-block.md)).
- No hand-set switch control: a switch moves only by the program or a CTC Office
  command.
- No yellow-aspect speed halving.
- The vital block is scanned on both channels; a disagreement between them is a
  latched channel fault.
