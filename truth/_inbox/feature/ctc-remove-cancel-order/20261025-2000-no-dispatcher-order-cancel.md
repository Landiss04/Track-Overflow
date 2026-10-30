**Target:** truth/decisions/D028-no-dispatcher-order-cancel.md
**Action:** create
**Proposed by:** Claude (Opus 5.5) on feature/ctc-remove-cancel-order
**Provenance:** asserted by Landis 2026-10-25

---

# D028-no-dispatcher-order-cancel

**Status:** current
**Owner:** CTC Office (Landis)
**Provenance:** asserted by Landis 2026-10-25
**Aliases:** cancel order, cancel dispatch, cancel_dispatch, cancelDispatch, withdraw order
**Last updated:** 2026-10-25

## Context

The CTC Office had a **Cancel order** action in Selected train (Manual mode) that let the
dispatcher withdraw a train's order. The customer did not ask for it.

## Decision

The dispatcher cannot cancel a train's order. An order can be replaced by a new one
(reroute), never withdrawn by the dispatcher. The CTC Office offers no cancel
action in its window, its interface or its test UI.

## Consequences

- The CTC Office still drops orders on its own where other rules require it: orders into
  a block that is closed or closing (`arbitration/block-closure.md`,
  `arbitration/no-authority-into-unusable-block.md`), and a scheduled run's order once
  the run is back in the yard (D020).
- A train that is lost or waiting in the yard keeps its order until it is replaced.
