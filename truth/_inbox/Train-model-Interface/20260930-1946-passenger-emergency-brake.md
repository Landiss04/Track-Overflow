**Target:** truth/arbitration/passenger-emergency-brake.md
**Action:** create
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** `Train_Model_Backend_Design.pdf` §5.8 (Locked) and Interfaces table (Emergency Brake State), supplied by Kevin Schillinger 2026-09-30; brake failure disabling both brakes asserted by Kevin Schillinger 2026-09-30; not in the repository

---

# passenger-emergency-brake

**Status:** current
**Owner:** Train Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.8 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; brake failure disabling both brakes asserted by Kevin Schillinger 2026-09-30
**Aliases:** passenger e-brake, passenger emergency brake pull, emergency brake ownership
**Last updated:** 2026-09-30

## Definition

The Train Model owns the passenger emergency brake. Pulling it makes the Train Model
apply the emergency brake force. The Train Model reports Emergency Brake State to the
Train Controller, and that state is active when either the Train Controller's emergency
brake command or a passenger pull is active, unless the brakes have failed.

## Notes

- Brake failure disables the passenger emergency brake along with the others. See
  `signals/failure-status.md`.
- The source leaves open who releases the brake once it is pulled.
