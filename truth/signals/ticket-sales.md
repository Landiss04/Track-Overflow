# ticket-sales

**Status:** current
**Owner:** Track Model
**Provenance:** `documents/srs-filled.md` REQ-FUNC-014, REQ-FUNC-017.1; per-line form `<int, string>` asserted by Landis 2026-10-03
**Aliases:** Ticket Sales, tickets sold, ticket sales per line
**Last updated:** 2026-10-03

## Definition

Tickets sold, reported per line by the Track Model to the CTC Office: a list of
`<int, string>` pairs, each the number of tickets sold and the line they were sold on
(for example `"Green"`).

## Notes

- The CTC Office derives its throughput metrics from it: tickets per hour on each
  line (REQ-FUNC-014).
- Open: whether each count is tickets sold since the previous report or a running
  total is not decided.
- The Track Model owner has not confirmed it.
