**Target:** truth/signals/failure-status.md
**Action:** replace
**Proposed by:** Claude Code on Train_ctrl_pr
**Provenance:** asserted by Kevin Schillinger 2026-11-02 ("inferring failures is required"), in reply to a proposal to restore failure status from the Train Model

---

# failure-status

**Status:** superseded
**Owner:** Train Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.95 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; withdrawn by Kevin Schillinger 2026-10-05; the Train Controller's inference of failures required, asserted by Kevin Schillinger 2026-11-02
**Aliases:** Failure Status, train failures, Train Model failures
**Last updated:** 2026-11-02

## Definition

Withdrawn. The Train Model no longer sends failure status to the Train Controller.

The Train Controller is required to infer each failure, and its resolution, from the
signals it does receive. Restoring this signal is not an option for meeting that
requirement.

## Notes

- The failures themselves are unchanged. Murphy still injects them, and their effects
  are recorded in `modules/train-model.md` under `## Failure modes`.

## Supersedes

- Previously three booleans, `bool[3]` (engine, signal pickup, brake), sent by the
  Train Model to the Train Controller; now not sent (Kevin Schillinger 2026-10-05).
