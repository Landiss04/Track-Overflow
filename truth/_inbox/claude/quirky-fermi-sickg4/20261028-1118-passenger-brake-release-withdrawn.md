**Target:** truth/signals/passenger-brake-release.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-28, in chat: "it is latched until the train controller sends ebreak = false"; replaces proposal `20261025-2242-passenger-brake-release-conflict.md` and resolves its Conflict. The "not sent" side is Train Controller HW `HARNESS_INTEGRATION.md` Outputs and `REQUIREMENTS.md` M2 ("Not sent, by decision") and `OPEN_ISSUES.md` #25 in PR #50 (Jg-6865)

---

# passenger-brake-release

**Status:** superseded
**Owner:** Train Controller
**Provenance:** asserted by Kevin Schillinger 2026-10-20 (the Train Controller sends the one-shot release when the driver releases a passenger pull); "not sent, by decision" in Train Controller HW `HARNESS_INTEGRATION.md` Outputs, `REQUIREMENTS.md` M2 and `OPEN_ISSUES.md` #25 (PR #50, Jg-6865); withdrawn by Kevin Schillinger 2026-10-28
**Aliases:** passenger emergency brake release, release passenger brake, clear passenger brake, `clear_passenger_brake`
**Last updated:** 2026-10-28

## Definition

Withdrawn. The Train Controller sends no separate release for a passenger pull. A pull
stays latched until the Train Controller sends emergency brake false; see
[emergency-brake-command](emergency-brake-command.md) and
[passenger-emergency-brake](../arbitration/passenger-emergency-brake.md).

## Supersedes

- Previously a one-shot boolean from the Train Controller to the Train Model that
  cleared a passenger pull (Kevin Schillinger 2026-10-20); now not sent, and the pull
  clears on the Train Controller's emergency brake going false (Kevin Schillinger
  2026-10-28).
- Conflict between "sent" (Kevin Schillinger 2026-10-20) and "not sent" (Train
  Controller HW, PR #50) resolved as not sent (Kevin Schillinger 2026-10-28).
