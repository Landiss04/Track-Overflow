**Target:** truth/arbitration/brakes-apply-together.md
**Action:** replace
**Proposed by:** Codex on claude/quirky-fermi-sickg4
**Provenance:** Kevin Schillinger’s October 20, 2026 SDD review; documents/Railway_Sim_SDD_Train_Model.md v0.2 §4.9; direct documentation request 2026-10-20; simultaneous application previously asserted by Kevin Schillinger 2026-10-17; force summation selected in response to his review, SDD v0.2 §003-logical

---

# brakes-apply-together

**Status:** current
**Owner:** Train Controller
**Provenance:** Kevin Schillinger’s October 20, 2026 SDD review; documents/Railway_Sim_SDD_Train_Model.md v0.2 §4.9; direct documentation request 2026-10-20; simultaneous application previously asserted by Kevin Schillinger 2026-10-17; force summation selected in response to his review, SDD v0.2 §003-logical
**Aliases:** both brakes, service and emergency brake together, simultaneous braking, brake precedence
**Last updated:** 2026-10-20

## Definition

Service and emergency brakes may engage simultaneously. Neither suppresses the other.
Service engages when commanded unless service brake failure is active. Emergency
engages when the controller commands it or the passenger latch is set, regardless
of service failure.

## Force combination

Total brake force is the sum of the configured forces of the engaged brakes:
`F_brake = service_active * f_service_n + emergency_active * f_emergency_n`.
This physical realization was selected in response to Kevin’s review and is recorded
in SDD v0.2; simultaneous engagement itself was explicitly asserted by Kevin.

## Related signals

See [service-brake-command](../signals/service-brake-command.md),
[emergency-brake-command](../signals/emergency-brake-command.md), and
[brake-state](../signals/brake-state.md).

## Supersedes

- Previously allowed simultaneous application without defining force combination; the reviewed SDD specifies summing the engaged configured forces.
