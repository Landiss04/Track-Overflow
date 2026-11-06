**Target:** truth/signals/beacon.md
**Action:** replace
**Proposed by:** Codex on claude/quirky-fermi-sickg4
**Provenance:** Kevin Schillinger’s October 20, 2026 SDD review; documents/Railway_Sim_SDD_Train_Model.md v0.2 §4.9; direct documentation request 2026-10-20; compact array encoding selected in response to Kevin’s request, rather than attributed to the earlier backend PDF

---

# beacon

**Status:** current
**Owner:** Track Model
**Provenance:** Kevin Schillinger’s October 20, 2026 SDD review; documents/Railway_Sim_SDD_Train_Model.md v0.2 §4.9; direct documentation request 2026-10-20; compact array encoding selected in response to Kevin’s request, rather than attributed to the earlier backend PDF
**Aliases:** Beacon, station beacon, beacon data
**Last updated:** 2026-10-20

## Definition

Station data delivered by the Track Model to the Train Model near a station and
passed through to the Train Controller: station name, platform side (`"L"`, `"R"`
or `"LR"` for both sides), and underground boolean.

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

## Supersedes

- Previously left serialization and between-beacon output open; the encoding selected in response to Kevin’s request is recorded in SDD v0.2, with current-tick output and consumer retention.
