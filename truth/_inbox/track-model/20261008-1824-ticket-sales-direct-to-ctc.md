**Target:** truth/signals/ticket-sales.md
**Action:** replace
**Proposed by:** Claude on track-model
**Provenance:** asserted by the Track Model owner in a session on track-model, 2026-10-08 (ticket sales go to the CTC Office directly, not through the Track Controller; the Track Model keeps the total sold); per-line form `<int, string>` asserted by Landis 2026-10-03; `documents/srs-filled.md` REQ-FUNC-014, REQ-FUNC-017.1

---

# ticket-sales

**Status:** current
**Owner:** Track Model
**Provenance:** asserted by the Track Model owner in a session on track-model, 2026-10-08 (ticket sales go to the CTC Office directly, not through the Track Controller; the Track Model keeps the total sold); per-line form `<int, string>` asserted by Landis 2026-10-03; `documents/srs-filled.md` REQ-FUNC-014, REQ-FUNC-017.1
**Aliases:** Ticket Sales, tickets sold, ticket sales per line
**Last updated:** 2026-10-08

## Definition

Tickets sold, reported per line by the Track Model to the CTC Office, directly. They do not pass through the Track Controller. Each report is a list of `<int, string>` pairs, each the number of tickets sold and the line they were sold on. The Track Model reports two lists every tick:

- **sold now**: tickets sold on that tick.
- **sold total**: the running total since the Track Model started or was reset. The Track Model keeps this total.

## Notes

- The CTC Office derives its throughput metrics from it: tickets per hour on each line (REQ-FUNC-014).
- The Track Model's own boundary type holds each list as a mapping from line to count. The harness edge turns it into the pairs above.
- The line is written as it appears in block IDs, for example `"GREEN"`, not `"Green"` (see `conventions/identifiers.md`).
- The Track Model owner has confirmed it.

## Supersedes

- Previous: whether each count is tickets sold since the previous report or a running total was open. Now: both are sent, and the Track Model keeps the total.
