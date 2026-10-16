**Target:** truth/signals/switch-command.md
**Action:** create
**Proposed by:** Claude on ctc-interfacing
**Provenance:** `documents/srs-filled.md` REQ-FUNC-012; output added and normal position defined, asserted by Landis 2026-10-03

---

# switch-command

**Status:** current
**Owner:** CTC Office
**Provenance:** `documents/srs-filled.md` REQ-FUNC-012; output added and normal position defined, asserted by Landis 2026-10-03
**Aliases:** Switch Position Command (CTC), set switch position, switch override
**Last updated:** 2026-10-03

## Definition

A switch position set by the dispatcher, sent from the CTC Office to the Track
Controller: the switch, identified by line and switch ID per
`conventions/identifiers.md`, and its position, `normal` or `reverse`.

**Normal** is the first connection the track layout file lists for the switch, and
**reverse** the second: for Green switch `12` (`12-13; 1-13`), normal joins 12 to 13
and reverse joins 1 to 13.

## Notes

- The dispatcher can set switch positions only while in maintenance mode
  (REQ-FUNC-012; see [maintenance-mode](maintenance-mode.md)).
- Distinct from the Switch Position Command the Track Controller sends to the Track
  Model.
- The Track Controller owner has not confirmed it.
