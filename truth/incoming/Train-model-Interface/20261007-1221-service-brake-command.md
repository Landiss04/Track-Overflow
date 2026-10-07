**Target:** truth/signals/service-brake-command.md
**Action:** replace
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** brake failure blocking only the service brake, clarified by the course instructor and relayed by Kevin Schillinger 2026-10-02 (the fact already carried by inbox proposals `20261002-2107-brake-state.md` and `20261006-1218-train-model.md`); this entry brought into line with it, and its pointer to `signals/failure-status.md`, which inbox proposal `20261005-1821-failure-status.md` withdraws, moved to `modules/train-model.md`, at Kevin Schillinger's request 2026-10-07 in this chat ("write the two brake fix proposals"). Only the brake failure note, the provenance, the date and the supersedes section change.

---

# service-brake-command

**Status:** current
**Owner:** Train Controller
**Provenance:** `Train_Model_Backend_Design.pdf` §5.9 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; brake failure blocking only the service brake clarified by the course instructor and relayed by Kevin Schillinger 2026-10-02
**Aliases:** Service Brake Command, service brake
**Last updated:** 2026-10-07

## Definition

A `bool` sent from the Train Controller to the Train Model. True engages the service
brake and false releases it.

## Notes

- While engaged, the Train Model applies the service brake force. That force is derived
  from the 2/3-load reference mass.
- Brake failure blocks the service brake only. While the brakes have failed, this
  command applies no force and Brake State reports the service brake as not engaged.
  The emergency brake still works. See `modules/train-model.md` `## Failure modes`.
- The source leaves open whether deceleration scales with train mass.
- The source is the Train Model design. The Train Controller owners have not confirmed
  it.

## Supersedes

- Brake failure: previously disabled the service brake and the emergency brake alike;
  now it blocks the service brake only (instructor, relayed by Kevin Schillinger
  2026-10-02).
