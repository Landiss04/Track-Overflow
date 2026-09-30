**Target:** truth/signals/service-brake-command.md
**Action:** create
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** `Train_Model_Backend_Design.pdf` §5.9 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; not in the repository

---

# service-brake-command

**Status:** current
**Owner:** Train Controller
**Provenance:** `Train_Model_Backend_Design.pdf` §5.9 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30
**Aliases:** Service Brake Command, service brake
**Last updated:** 2026-09-30

## Definition

A `bool` sent from the Train Controller to the Train Model. True engages the service
brake and false releases it.

## Notes

- While engaged, the Train Model applies the service brake force. That force is derived
  from the 2/3-load reference mass.
- The source leaves the scope of brake failure open (service brake only, or the
  emergency brake as well), and also whether deceleration scales with train mass.
- The source is the Train Model design. The Train Controller owners have not confirmed
  it.
