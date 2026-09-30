**Target:** truth/signals/failure-status.md
**Action:** create
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** `Train_Model_Backend_Design.pdf` §5.95 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; not in the repository

---

# failure-status

**Status:** current
**Owner:** Train Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.95 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30
**Aliases:** Failure Status, train failures, Train Model failures
**Last updated:** 2026-09-30

## Definition

Three independent booleans — engine failure, signal pickup failure, brake failure —
reported by the Train Model to the Train Controller as `bool[3]`.

## Notes

- Failures are injected by Murphy from the Train Model UI. They are not a cross-module
  input.
- The three failures compose. Any combination is valid, including all three at once.
- Engine failure zeroes traction. Signal pickup failure affects the Track Signal only.
- The source does not state the index order of the `bool[3]`.
- The source leaves the scope of brake failure open: service brake only, or the
  emergency brake as well.
