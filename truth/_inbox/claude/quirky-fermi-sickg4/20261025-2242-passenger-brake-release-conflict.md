**Target:** truth/signals/passenger-brake-release.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** PR #50 (Landiss04/Track-Overflow, Jg-6865), `Train-Ctrl_HW/HARNESS_INTEGRATION.md` Outputs and `REQUIREMENTS.md` M2: "Not sent, by decision"; current entry asserted by Kevin Schillinger 2026-10-20

---

# passenger-brake-release

**Status:** current
**Owner:** Train Controller
**Provenance:** asserted by Kevin Schillinger 2026-10-20; not sent by decision, Train Controller HW `HARNESS_INTEGRATION.md` and `REQUIREMENTS.md` M2 in PR #50 (Jg-6865)
**Aliases:** passenger emergency brake release, release passenger brake, clear passenger brake, `clear_passenger_brake`
**Last updated:** 2026-10-25

## Definition

A one-shot boolean sent from the Train Controller to the Train Model. It is true on the
tick the Train Controller releases a passenger emergency brake pull, and false
otherwise. The Train Model then clears the pull.

## Notes

- It releases a passenger pull only. The Train Controller's own emergency brake follows
  [emergency-brake-command](emergency-brake-command.md).
- Who releases the pull: [passenger-emergency-brake](../arbitration/passenger-emergency-brake.md).

## Conflict

- **Sent:** the Train Controller sends the one-shot release when the driver releases a
  passenger pull (Kevin Schillinger 2026-10-20).
- **Not sent:** the Train Controller sends no release; clearing the Train Model's
  passenger latch is left to the Train Model's own detection (Train Controller HW,
  PR #50, `HARNESS_INTEGRATION.md` Outputs, `REQUIREMENTS.md` M2, `OPEN_ISSUES.md` #25).
- **Owner to resolve:** Kevin Schillinger.
