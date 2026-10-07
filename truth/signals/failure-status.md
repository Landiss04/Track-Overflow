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
