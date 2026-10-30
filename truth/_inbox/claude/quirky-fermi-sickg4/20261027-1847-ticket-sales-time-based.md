**Target:** truth/signals/ticket-sales.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** Track Model owner (SeeingEyeTree), answers to `documents/module-owner-review.md`, commit `c92f58f`, 2026-10-26, TM-1

---

# ticket-sales

**Status:** current
**Owner:** Track Model
**Provenance:** `documents/srs-filled.md` REQ-FUNC-014, REQ-FUNC-017.1; per-line form `<int, string>` asserted by Landis 2026-10-03; sales time-based at about 12 tickets per simulated minute per station, and the interface unchanged, by the Track Model owner (SeeingEyeTree), answers to `documents/module-owner-review.md`, commit `c92f58f`, 2026-10-26 (TM-1)
**Aliases:** Ticket Sales, tickets sold, ticket sales per line, ticket rate
**Last updated:** 2026-10-27

## Definition

Tickets sold, reported per line by the Track Model to the CTC Office: a list of
`<int, string>` pairs, each the number of tickets sold and the line they were sold on
(for example `"Green"`).

## Notes

- The CTC Office derives its throughput metrics from it: tickets per hour on each
  line (REQ-FUNC-014).
- Sales are time-based, not per tick: about 12 tickets per simulated minute per
  station. The per-tick chance of a sale is derived from the tick length, so the rate
  holds at any tick length.
- Open: whether each count is tickets sold since the previous report or a running
  total is not decided.

## Supersedes

- Rate: previously unstated, and the generator was per tick; now time-based (Track
  Model owner 2026-10-26). The Track Model owner now confirms the interface.
