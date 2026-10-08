# maintenance-closure-lock

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-06 (blocks closed in maintenance mode must not be overridden by the Track Controller; it queries the list, and regains control once a block is reopened)
**Aliases:** maintenance lock, closure precedence, closed block override
**Last updated:** 2026-10-06

## Definition

A block on the CTC Office's [closed-blocks](../signals/closed-blocks.md) list is closed,
and the CTC Office's closure takes precedence over the Track Controller. The Track
Controller checks the list before it changes a block and does not change a listed block.

When the dispatcher reopens the block, it comes off the list, and the Track Controller
controls it again.

## Notes

- The lock covers blocks only. Switch positions set in maintenance mode are not
  covered by this entry.
- A block is listed, and so locked, from the moment its closure is requested, even
  while a train is still in it.
