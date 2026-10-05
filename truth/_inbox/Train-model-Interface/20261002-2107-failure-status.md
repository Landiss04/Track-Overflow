**Target:** truth/signals/failure-status.md
**Action:** replace
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** brake failure blocking only the service brake, clarified by the course instructor and relayed by Kevin Schillinger 2026-10-02 in this chat

---

# failure-status

**Status:** current
**Owner:** Train Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.95 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; element order asserted by Kevin Schillinger 2026-09-30; brake failure blocking only the service brake clarified by the course instructor and relayed by Kevin Schillinger 2026-10-02
**Aliases:** Failure Status, train failures, Train Model failures
**Last updated:** 2026-10-02

## Definition

Three independent booleans, `bool[3]`, reported by the Train Model to the Train
Controller. Element 0 is engine failure, element 1 is signal pickup failure, and element
2 is brake failure.

## Notes

- Failures are injected by Murphy from the Train Model UI. They are not a cross-module
  input.
- The three failures compose. Any combination is valid, including all three at once.
- Engine failure zeroes traction. Signal pickup failure affects the Track Signal only.
- Brake failure blocks the service brake only. The emergency brake, commanded or
  pulled by a passenger, still works.

## Supersedes

- Brake failure: previously disabled both the service and the emergency brake;
  now blocks the service brake only (instructor, relayed by Kevin Schillinger
  2026-10-02).
