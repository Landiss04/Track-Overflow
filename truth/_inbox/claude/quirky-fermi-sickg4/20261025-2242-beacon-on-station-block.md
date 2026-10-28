**Target:** truth/signals/beacon.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** Replaces proposal `20261020-1341-beacon-sdd-review.md` (Codex), whose canonical payload, retention and between-beacon output are merged into this entry. PR #50 (Landiss04/Track-Overflow, Jg-6865), `Train-Ctrl_HW/HARNESS_INTEGRATION.md` Inputs and `REQUIREMENTS.md` M6; `documents/Railway_Sim_SDD_Train_Model.md` v0.2 §4.9, Kevin Schillinger's October 20, 2026 SDD review and direct documentation request 2026-10-20

---

# beacon

**Status:** current
**Owner:** Track Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.7 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; 128-character limit asserted by Kevin Schillinger 2026-09-30; platform side may be both left and right, encoded `"L"`, `"R"` or `"LR"`, asserted by Kevin Schillinger 2026-10-07; the Train Controller needs the beacon every tick the train is on the station's block, Train Controller HW `HARNESS_INTEGRATION.md` and `REQUIREMENTS.md` M6 in PR #50 (Jg-6865); compact array encoding selected in response to Kevin's request, rather than attributed to the earlier backend PDF; Kevin Schillinger's October 20, 2026 SDD review; `documents/Railway_Sim_SDD_Train_Model.md` v0.2 §4.9; direct documentation request 2026-10-20
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

## Canonical logical payload

The compact JSON array order is `[station_name, platform_side, underground]`.
Canonical Python serialization is:

```python
json.dumps(
    [name, side, underground],
    ensure_ascii=True,
    separators=(",", ":"),
    allow_nan=False,
)
```

The complete output must fit 128 characters, counting brackets, commas, quotes,
and escapes. Output is ASCII, so character and encoded byte counts coincide.
Producers and the Train Model reject invalid or overlength payloads without
truncation and before model mutation. Station-name length alone is insufficient.

## Boundary and retention

Keep the typed `Beacon` and named outer harness fields. The array defines the
bounded logical payload, not the entire harness envelope. Send and output `None`
between beacon ticks. The Train Controller retains prior beacon information when
its control logic needs it.

## Notes

- The train receives a beacon only near a station, through its antenna.
- The serialized beacon payload is limited to 128 characters.
- The Train Controller needs the beacon on every tick the train is on the station's
  block, and none otherwise: it takes arrival as the beacon received with authority 0,
  commanded speed 0 and the train at a stand.
- The Train_Model_Backend_Design.pdf does not set a serialization format for the payload
  as a whole, or whether a beacon may carry no platform side. The format above is from
  SDD v0.2 §4.9; the platform-side question is still open.
- The source is the Train Model design. The Track Model owner has not confirmed it.

## Supersedes

- Platform side: previously L or R only; now `"L"`, `"R"` or `"LR"`, so that a station
  with platforms on both sides announces both (Kevin Schillinger 2026-10-07).
- Between beacons: previously unstated; now the Train Controller's need is recorded
  (PR #50, 2026-10-25).
- Serialization and between-beacon output: previously left open by the source; now the
  compact array above, and `None` between beacon ticks (SDD v0.2 §4.9, 2026-10-20).
  Retention is the Train Controller's.
