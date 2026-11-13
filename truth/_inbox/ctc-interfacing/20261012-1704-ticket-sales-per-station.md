**Target:** truth/signals/ticket-sales.md
**Action:** replace
**Proposed by:** Claude on ctc-interfacing
**Provenance:** `documents/srs-filled.md` REQ-FUNC-014, REQ-FUNC-017.1; per-station form keyed by station name, with counts since the previous report, asserted by Landis 2026-10-12 (each station knows only its own sales)

---

# ticket-sales

**Status:** current
**Owner:** Track Model
**Provenance:** `documents/srs-filled.md` REQ-FUNC-014, REQ-FUNC-017.1; per-station form keyed by station name, with counts since the previous report, asserted by Landis 2026-10-12 (each station knows only its own sales)
**Aliases:** Ticket Sales, tickets sold, ticket sales per station, station ticket sales
**Last updated:** 2026-10-12

## Definition

Tickets sold at each station, reported by the Track Model to the CTC Office as a map
from station name to the number of tickets sold there since the previous report, for
example `{"DORMONT": 12, "GLENBURY": 4}`. A station that sold none may be left out.

- A station is named as in the track layout files (`infrastructure.station`). A
  station listed on two blocks reports one count. On the Green line these are the
  two platforms of CENTRAL, INGLEWOOD, OVERBROOK, GLENBURY and DORMONT.
- No station name is used on both lines, so a name also says which line its sales
  are on.

## Notes

- The CTC Office derives its throughput metrics from it: tickets per hour on each
  line (REQ-FUNC-014), the sum over the line's stations.
- Green block 16 is a station with no name in the layout file. It cannot report
  until it has one.
- The Track Model owner has not confirmed it.

## Supersedes

- Form: previously one count per line, a list of `<int, string>` pairs (Landis
  2026-10-03). Now one count per station, because each station knows only its own
  sales (Landis 2026-10-12). This also settles the open question of each count's
  meaning: tickets sold since the previous report, not a running total.
