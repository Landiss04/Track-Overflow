**Target:** truth/signals/emergency-brake-command.md
**Action:** create
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** `Train_Model_Backend_Design.pdf` Interfaces table; command path vs passenger path asserted by Kevin Schillinger 2026-09-30; brake failure disabling both brakes asserted by Kevin Schillinger 2026-09-30

---

# emergency-brake-command

**Status:** current
**Owner:** Train Controller
**Provenance:** `Train_Model_Backend_Design.pdf` Interfaces table; split between the controller path and the passenger path asserted by Kevin Schillinger 2026-09-30; brake failure disabling both brakes asserted by Kevin Schillinger 2026-09-30
**Aliases:** Emergency Brake Command, e-brake command, controller emergency brake
**Last updated:** 2026-09-30

## Definition

A `bool` sent from the Train Controller to the Train Model. It engages the emergency
brake from the controller side.

## Notes

- This signal carries only the controller path. A passenger engages the emergency brake
  from the Train Model UI, and that pull never passes through this signal. See
  `arbitration/passenger-emergency-brake.md`.
- The Train Model reports the combined state back to the Train Controller as Emergency
  Brake State. That state is active when either path is active, unless the brakes have
  failed.

## Supersedes

- Description: previously "triggered by controller or passenger pull" in the design's
  Interfaces table. Passenger pulls originate in the Train Model UI, not in this signal
  (Kevin 2026-09-30).
