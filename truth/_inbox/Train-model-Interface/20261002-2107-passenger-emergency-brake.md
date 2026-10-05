**Target:** truth/arbitration/passenger-emergency-brake.md
**Action:** replace
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** brake failure blocking only the service brake, clarified by the course instructor and relayed by Kevin Schillinger 2026-10-02 in this chat

---

# passenger-emergency-brake

**Status:** current
**Owner:** Train Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.8 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; brake failure blocking only the service brake clarified by the course instructor and relayed by Kevin Schillinger 2026-10-02; release by the Train Controller asserted by Kevin Schillinger 2026-10-02
**Aliases:** passenger e-brake, passenger emergency brake pull, emergency brake ownership
**Last updated:** 2026-10-02

## Definition

The Train Model owns the passenger emergency brake. Pulling it makes the Train Model
apply the emergency brake force. The Train Model reports Emergency Brake State to the
Train Controller, and that state is active when either the Train Controller's emergency
brake command or a passenger pull is active. A brake failure does not disable it.

The Train Controller releases the emergency brake. The Train Model UI offers no
release control (D011).

## Notes

- Brake failure blocks the service brake only, so a passenger pull still applies the
  emergency brake. See `signals/failure-status.md`.
- This entry does not settle the signal or mechanism by which the Train Controller
  releases a passenger pull.

## Supersedes

- Brake failure: previously disabled the passenger emergency brake; now the pull
  still applies it (instructor, relayed by Kevin Schillinger 2026-10-02).
- Release: previously left open by the source; now the Train Controller (Kevin
  Schillinger 2026-10-02).
