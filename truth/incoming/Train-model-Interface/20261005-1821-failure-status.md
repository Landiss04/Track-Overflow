**Target:** truth/signals/failure-status.md
**Action:** replace
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** failure status no longer sent to the Train Controller, asserted by Kevin Schillinger 2026-10-05 in this chat ("the train model no longer is to send the failure mode status to the train controllers strip that out"); not in the repository. Replaces an earlier inbox proposal for this entry, deleted as duplicates on 2026-10-06 at Kevin Schillinger's request ("review all the proposals and dedupe"). Its brake failure scope (blocking only the service brake, clarified by the course instructor and relayed by Kevin Schillinger 2026-10-02) is kept in `modules/train-model.md`, inbox proposal `20261006-1218-train-model.md`.

---

# failure-status

**Status:** superseded
**Owner:** Train Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.95 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; withdrawn by Kevin Schillinger 2026-10-05
**Aliases:** Failure Status, train failures, Train Model failures
**Last updated:** 2026-10-05

## Definition

Withdrawn. The Train Model no longer sends failure status to the Train Controller.

## Notes

- The failures themselves are unchanged. Murphy still injects them, and their effects
  are recorded in `modules/train-model.md` under `## Failure modes`.

## Supersedes

- Previously three booleans, `bool[3]` (engine, signal pickup, brake), sent by the
  Train Model to the Train Controller; now not sent (Kevin Schillinger 2026-10-05).
