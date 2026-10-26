**Target:** truth/signals/beacon.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** PR #50 (Landiss04/Track-Overflow, Jg-6865), `Train-Ctrl_HW/HARNESS_INTEGRATION.md` Inputs and `REQUIREMENTS.md` M6

---

# beacon

**Status:** current
**Owner:** Track Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.7 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; 128-character limit asserted by Kevin Schillinger 2026-09-30; platform side may be both left and right, encoded `"L"`, `"R"` or `"LR"`, asserted by Kevin Schillinger 2026-10-07; the Train Controller needs the beacon every tick the train is on the station's block, Train Controller HW `HARNESS_INTEGRATION.md` and `REQUIREMENTS.md` M6 in PR #50 (Jg-6865)
**Aliases:** Beacon, station beacon, beacon data
**Last updated:** 2026-10-25

## Definition

Station data broadcast from beacons mounted before and after each station. It has three
fields: station name, platform side, and whether the station is underground. The Track
Model delivers it to the Train Model, which passes it through to the Train Controller.

Platform side is one of three strings:

| Value | Meaning |
|---|---|
| `"L"` | Platform on the left |
| `"R"` | Platform on the right |
| `"LR"` | Platforms on both sides |

## Notes

- The train receives a beacon only near a station, through its antenna.
- The serialized beacon payload is limited to 128 characters.
- The Train Controller needs the beacon on every tick the train is on the station's
  block, and none otherwise: it takes arrival as the beacon received with authority 0,
  commanded speed 0 and the train at a stand.
- The source does not set a serialization format for the payload as a whole, or whether
  a beacon may carry no platform side.
- The source is the Train Model design. The Track Model owner has not confirmed it.

## Supersedes

- Platform side: previously L or R only; now `"L"`, `"R"` or `"LR"`, so that a station
  with platforms on both sides announces both (Kevin Schillinger 2026-10-07).
- Between beacons: previously unstated; now the Train Controller's need is recorded
  (PR #50, 2026-10-25).
