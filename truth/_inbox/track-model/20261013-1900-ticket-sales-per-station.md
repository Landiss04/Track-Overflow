**Target:** truth/signals/ticket-sales.md
**Action:** replace
**Proposed by:** Claude on track-model
**Provenance:** asserted by the Track Model owner in a session on track-model, 2026-10-13 (tickets are tracked per station, as events, with no running total); ticket sales go to the CTC Office directly, asserted by the Track Model owner 2026-10-08; `<int, string>` pair form asserted by Landis 2026-10-03; `documents/srs-filled.md` REQ-FUNC-014, REQ-FUNC-017.1

---

# ticket-sales

**Status:** current
**Owner:** Track Model
**Provenance:** asserted by the Track Model owner in a session on track-model, 2026-10-13 (tickets are tracked per station, as events, with no running total); ticket sales go to the CTC Office directly, asserted by the Track Model owner 2026-10-08; `<int, string>` pair form asserted by Landis 2026-10-03; `documents/srs-filled.md` REQ-FUNC-014, REQ-FUNC-017.1
**Aliases:** Ticket Sales, tickets sold, ticket sales per station
**Last updated:** 2026-10-13

## Definition

Tickets sold, reported per station by the Track Model to the CTC Office, directly. They do not pass through the Track Controller. Each report is a list of `<int, string>` pairs, each the number of tickets sold and the name of the station they were sold at. The Track Model reports one list every tick, with one pair per station (a station that sold none reports 0):

- **sold now**: tickets sold on that tick.

The Track Model keeps no running total and sends none. A sale is an event. A consumer that wants a total, or a total per line, adds the events up itself.

## Notes

- The CTC Office derives its throughput metrics from it: tickets per hour on each line (REQ-FUNC-014). It maps each station to its line itself.
- The Track Model's own boundary type holds the list as a mapping from station name to count. The harness edge turns it into the pairs above.
- The station is written as its name appears in the track layout, for example `"SHADYSIDE"`. Station names are unique across the three lines.
- The Track Model owner has confirmed it.

## Supersedes

- Previous: the pairs were per line (for example `"GREEN"`). Now: per station (Track Model owner, 2026-10-13).
