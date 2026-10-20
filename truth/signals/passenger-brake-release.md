# passenger-brake-release

**Status:** current
**Owner:** Train Controller
**Provenance:** asserted by Kevin Schillinger 2026-10-20
**Aliases:** passenger emergency brake release, release passenger brake, clear passenger brake, `clear_passenger_brake`
**Last updated:** 2026-10-20

## Definition

A one-shot boolean sent from the Train Controller to the Train Model. It is true on the
tick the Train Controller releases a passenger emergency brake pull, and false
otherwise. The Train Model then clears the pull.

## Notes

- It releases a passenger pull only. The Train Controller's own emergency brake follows
  [emergency-brake-command](emergency-brake-command.md).
- Who releases the pull: [passenger-emergency-brake](../arbitration/passenger-emergency-brake.md).
