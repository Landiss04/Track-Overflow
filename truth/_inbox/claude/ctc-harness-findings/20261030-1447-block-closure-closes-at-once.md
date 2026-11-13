**Target:** truth/arbitration/block-closure.md
**Action:** replace
**Proposed by:** Claude on claude/ctc-harness-findings
**Provenance:** asserted by Landis 2026-10-30, reviewing finding F32 of `documents/central-harness-windows-gui-2026-10-28.md` ("adding the closing in … logic bloats the code and is a bit unnecessary, lets just say its closed and leave it at that"), then choosing to remove the pending state from the CTC Office

---

# block-closure

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-05 (the dispatcher closes blocks only in maintenance mode); a block with a train in it closes at once, with no pending state, asserted by Landis 2026-10-30 (review of F32, `documents/central-harness-windows-gui-2026-10-28.md`)
**Aliases:** close block, reopen block, maintenance closure, pending closure
**Last updated:** 2026-10-30

## Definition

- The dispatcher can close and reopen blocks only in maintenance mode.
- A block closes as soon as the dispatcher confirms the closure, whether or not a train
  is in it. There is no pending or closing state.
- From then on no train is given authority into the block. A train already in it is
  not given authority back into it, but can still be given authority onward.
- Orders whose destination is the block are cancelled when it closes, and the
  dispatcher is told.
- Leaving maintenance mode does not reopen closed blocks.

## Notes

- Authority into closed and failed blocks:
  [no-authority-into-unusable-block](no-authority-into-unusable-block.md).
- The Track Controller is locked out of a closed block from the moment it closes:
  [maintenance-closure-lock](maintenance-closure-lock.md).

## Supersedes

- Occupied block: previously the closure stayed pending, shown as closing, until the
  train had left; now the block closes at once. The closing state was already locked
  and refused authority exactly like a closed block, so it added code and a second
  label with no safety difference (Landis 2026-10-30).
