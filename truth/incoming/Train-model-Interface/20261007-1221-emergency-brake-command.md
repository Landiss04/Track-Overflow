**Target:** truth/signals/emergency-brake-command.md
**Action:** replace
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** brake failure blocking only the service brake, clarified by the course instructor and relayed by Kevin Schillinger 2026-10-02 (the fact already carried by inbox proposals `20261002-2107-brake-state.md` and `20261006-1218-train-model.md`); this entry brought into line with it at Kevin Schillinger's request 2026-10-07 in this chat ("write the two brake fix proposals"). Only the brake failure clause, the provenance, the date and the supersedes line change.

---

# emergency-brake-command

**Status:** current
**Owner:** Train Controller
**Provenance:** `Train_Model_Backend_Design.pdf` Interfaces table; split between the controller path and the passenger path asserted by Kevin Schillinger 2026-09-30; brake failure blocking only the service brake clarified by the course instructor and relayed by Kevin Schillinger 2026-10-02
**Aliases:** Emergency Brake Command, e-brake command, controller emergency brake
**Last updated:** 2026-10-07

## Definition

A `bool` sent from the Train Controller to the Train Model. It engages the emergency
brake from the controller side.

## Notes

- This signal carries only the controller path. A passenger engages the emergency brake
  from the Train Model UI, and that pull never passes through this signal. See
  `arbitration/passenger-emergency-brake.md`.
- The Train Model reports the combined state back to the Train Controller as Emergency
  Brake State. That state is active when either path is active.
- Brake failure blocks the service brake only. While the brakes have failed, this
  command still engages the emergency brake. See `modules/train-model.md`
  `## Failure modes`.

## Supersedes

- Description: previously "triggered by controller or passenger pull" in the design's
  Interfaces table. Passenger pulls originate in the Train Model UI, not in this signal
  (Kevin 2026-09-30).
- Brake failure: previously disabled the emergency brake, so Emergency Brake State was
  inactive while the brakes had failed; now the emergency brake still works
  (instructor, relayed by Kevin Schillinger 2026-10-02).
