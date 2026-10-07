**Target:** truth/signals/maintenance-mode.md
**Action:** replace
**Proposed by:** GitHub Copilot on feature/TrackCtrl-Module-Implementation
**Provenance:** asserted by Landis 2026-10-02 (unchanged); what the Track Controller does in maintenance mode asserted by Braden 2026-10-06

Note for the promoter: the only changes against the entry on `truth`
(`3f7de79`) are the `Provenance` and `Last updated` lines, a new `## Track
Controller` section, and the last note, which said the Track Controller owner had
not confirmed this. Landis's pending replacement on `ctc-interfacing`
(`20261002-1129-maintenance-mode.md`) has the same body as the entry on `truth`,
so this proposal does not conflict with it.

---

# maintenance-mode

**Status:** current
**Owner:** CTC Office
**Provenance:** asserted by Landis 2026-10-02 (CTC architecture diagram, `ctc-architecture.html`); types per `conventions/identifiers.md` and `conventions/units.md`, chosen by Landis 2026-10-02 over the diagram's int types; Track Controller behaviour asserted by Braden 2026-10-06
**Aliases:** Maintenance Mode, maintenance
**Last updated:** 2026-10-06

## Definition

A boolean sent from the CTC Office to the Track Controller: true while the dispatcher has the system in maintenance mode.

## Track Controller

- The CTC Office controls maintenance mode; the Track Controller obeys it and has
  no control of its own to enter or leave it.
- While it is true, the Track Controller sets each switch to the position the CTC
  Office commands ([switch-command](switch-command.md), pending), not the position
  its PLC program would choose.
- Block closures are also the CTC Office's; the Track Controller obeys them.

## Notes

- One value for the whole system, not one per block.
