**Target:** truth/signals/switch-route-request.md
**Action:** create
**Proposed by:** Claude on integrate/quirky-into-development-resolved
**Provenance:** asserted by Landis 2026-11-03 (build the CTC side of route requests so Red trains can pass at the sidings, and send the request to Braden); the wire shape, PLC names and precedence as in Braden Bosilovich's plan "Route requests at the Red passing sidings — implementation plan", relayed by Landis 2026-11-04

---

# switch-route-request

**Status:** current
**Owner:** CTC Office
**Provenance:** asserted by Landis 2026-11-03 (the CTC Office asks the Track Controller to set switches for its routes, so trains can be routed into the Red passing sidings); wire shape, PLC input names and precedence from Braden Bosilovich's Track Controller HW plan, relayed by Landis 2026-11-04
**Aliases:** route requests, route_requests, switch route request, REQSW, REQREV
**Last updated:** 2026-11-04

## Definition

The position each switch should take for the train the CTC Office routes over it, sent
from the CTC Office to the Track Controller every step as the full list. A switch is
listed when a train's route crosses it within the train's authority, or where its
authority stops short of the switch; where two trains want the same switch, the request
of the train with dispatch priority stands. A switch no train is routed over is not
listed.

Each entry is a line, a switch ID per `conventions/identifiers.md` (the block the
layout file lists the switch on) and a position, `normal` or `reverse`, as in
[switch-command](switch-command.md): `{"line", "switch_id", "position"}`. A sender that
leaves the list out sends no requests.

## Notes

- A request, not a command. The Track Controller sets the switch for it only where its
  own rules allow, in this precedence: a train on the points block locks the switch
  where it reports; then the dispatcher's maintenance
  [switch-command](switch-command.md); then the request; then the program's own rule.
  A request never moves a switch into a closed leg.
- The Track Controller HW reads it in PLC programs as `REQSW_s` (a request exists for
  switch `s`) and `REQREV_s` (it is reverse). It does not change signal aspects.
- The harness carries it from the CTC Office to the Track Controller: not yet wired
  (Kevin Schillinger).
