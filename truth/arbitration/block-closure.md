# block-closure

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-05 (the dispatcher closes blocks only in maintenance mode; an occupied block closes once the train has left it)
**Aliases:** close block, reopen block, maintenance closure, pending closure
**Last updated:** 2026-10-05

## Definition

- The dispatcher can close and reopen blocks only in maintenance mode.
- Closing a block is maintenance, not a reaction to a failure, so a block with a train
  in it is not closed at once: the closure is pending, and the block closes by itself
  once the train has left it. Reopening a pending block cancels the closure.
- While a closure is pending, no train is given authority into the block, and orders
  whose destination is the block are cancelled as soon as the closure is requested.
- Leaving maintenance mode does not reopen closed blocks, and pending closures still
  close once their block is clear.

## Notes

- Authority into closed, closing and failed blocks:
  [no-authority-into-unusable-block](no-authority-into-unusable-block.md).
