**Target:** truth/signals/ticket-sales.md
**Action:** replace
**Proposed by:** Claude on track-model
**Provenance:** asserted by the Track Model owner in a session on track-model, 2026-10-13 (the Track Model does not keep or send a running total of tickets sold; it only reports each sale as it happens); supersedes the 2026-10-08 proposal `20261008-1824-ticket-sales-direct-to-ctc.md` on the total only; per-line form `<int, string>` asserted by Landis 2026-10-03; `documents/srs-filled.md` REQ-FUNC-014, REQ-FUNC-017.1

---

# ticket-sales

**Status:** current
**Owner:** Track Model
**Provenance:** asserted by the Track Model owner in a session on track-model, 2026-10-13 (the Track Model does not keep or send a running total of tickets sold; it only reports each sale as it happens); ticket sales go to the CTC Office directly, not through the Track Controller, asserted by the Track Model owner 2026-10-08; per-line form `<int, string>` asserted by Landis 2026-10-03; `documents/srs-filled.md` REQ-FUNC-014, REQ-FUNC-017.1
**Aliases:** Ticket Sales, tickets sold, ticket sales per line
**Last updated:** 2026-10-13

## Definition

Tickets sold, reported per line by the Track Model to the CTC Office, directly. They do not pass through the Track Controller. Each report is a list of `<int, string>` pairs, each the number of tickets sold and the line they were sold on. The Track Model reports one list every tick:

- **sold now**: tickets sold on that tick.

The Track Model keeps no running total and sends none. A sale is an event. A consumer that wants a total adds the events up itself.

## Notes

- The CTC Office derives its throughput metrics from it: tickets per hour on each line (REQ-FUNC-014).
- The Track Model's own boundary type holds the list as a mapping from line to count. The harness edge turns it into the pairs above.
- The line is written as it appears in block IDs, for example `"GREEN"`, not `"Green"` (see `conventions/identifiers.md`).
- The Track Model owner has confirmed it.

## Supersedes

- Previous: the Track Model also sent the running total since it started or was reset (`sold total`). Now: it sends only the tickets sold this tick and keeps no total (Track Model owner, 2026-10-13).
