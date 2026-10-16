**Target:** truth/decisions/D0NN-train-model-fleet.md
**Action:** create
**Proposed by:** Claude (Claude Code) on train-model-instance-mgmt
**Provenance:** asserted by Kevin Schillinger 2026-10-08, choosing among process, UI, ownership and test UI options for running many trains; the selector's place in the header asserted by Kevin Schillinger 2026-10-08

The decision number is a placeholder. The promoter assigns the next free
`D` number and renames the target before promotion.

---

# D0NN-train-model-fleet

**Status:** current
**Owner:** Kevin Schillinger
**Provenance:** asserted by Kevin Schillinger 2026-10-08, choosing among process, UI, ownership and test UI options for running many trains; the selector's place in the header asserted by Kevin Schillinger 2026-10-08
**Aliases:** Train Model fleet, TrainModelFleet, parallel train models, multiple trains, train roster, train selector
**Last updated:** 2026-10-08

## Context

The Train Model simulates one train (`modules/train-model.md`). Once the
system is integrated, many trains run at once, so something must create,
hold, step and retire one Train Model per train, and the Train Model UI must
be able to show any of them. The options were one process per train or
many instances in one process; one window per train or one window with a
selector; the set of trains held by the Train Model module or by the
central harness (D005); and whether the test UI (D010) drives several trains.

## Decision

- Every train's Train Model runs in the system process as its own
  instance. There is no process per train and no IPC between them.
- The Train Model module owns the container that holds one instance per
  train, keyed by train ID. The central harness decides when a train is
  dispatched or retired and calls the container. The module's protocol
  stays one train per `step(dt, inputs)`.
- One Train Model window shows every train. A train selector in the
  window header picks which train the window shows, and the window's
  actions (failure injection, passenger emergency brake) act on that train
  only.
- The selector sits right after the header's status badges. The open middle
  of the header is reserved for advertisements.
- The test UI stays single-train: it drives one train, as D010 states.

## Consequences

- Every Train Model instance is stepped on the shared clock's tick, with the
  same fixed dt (D006, D017).
- Each train keeps its own state, including its own disembark draws.
- D010 is unchanged.
- How the system treats a step one train rejects is still the harness's
  policy (D005).
