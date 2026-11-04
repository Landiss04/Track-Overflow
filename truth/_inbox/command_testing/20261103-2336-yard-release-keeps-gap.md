**Target:** truth/decisions/D022-yard-black-box.md
**Action:** replace
**Proposed by:** Claude on command_testing
**Provenance:** asserted by Landis 2026-11-03 (asked for the yard release to wait for the blocks next to the exit block, after a train released next to another deadlocked Green 63/64 under `utils/schedule_v4.json`)

---

# D022-yard-black-box

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin Schillinger 2026-10-16; the CTC Office creating the trains asserted by Kevin Schillinger 2026-10-17; creation on release from the yard, the release conditions, and retirement at the yard entry block, agreed in the CTC Office's answers of 2026-10-20, relayed by Kevin Schillinger; a return-to-yard action for manual trains asserted by Kevin Schillinger 2026-10-20; the gap around the yard exit block asserted by Landis 2026-11-03
**Aliases:** yard, train yard, yard black box, dispatch from the yard, train creation, spawn, release from the yard, new_trains, retired_trains
**Last updated:** 2026-11-03

## Context

Each line's layout joins the yard (`next_blocks` lists `"yard"`, per
`conventions/files-and-paths.md`). No entry said what the yard is or who moves trains
into and out of it.

## Decision

- The yard is a black box with unlimited capacity.
- The CTC Office pulls trains from the yard and sends them back into the yard.
- The CTC Office creates each train when it releases it from the yard, not when it is
  dispatched. A dispatch only creates an order, and the train waits in the yard.
- It releases one train per line at a time, the waiting train most behind schedule
  first, and only when all of these hold: the line's yard exit block is clear, no train
  is authorized into that block, the blocks next to it are clear and no train is
  authorized into them, every wayside on the line is ready, and the scheduler is not
  holding that run.
- A released train enters the track at its line's yard exit block: Green 63, Red 9.
- A train sent back to the yard is retired when it reaches its line's yard entry block
  (Green 57, Red 9) and stops there, with authority 0 at its destination. The yard is
  not a block, so no authority is given into it. The harness removes the train, which
  clears the block. The CTC Office then sees the block clear, marks the run done and
  drops its order.
- The CTC Office reports both as one-time events in its outputs: each train it released
  on that tick, with its ID and line (`new_trains`), and each train it retired
  (`retired_trains`). The harness applies every tick's events exactly once.
- A "return to yard" action in the CTC Office sends a manual train back to the yard,
  where it is retired the same way as a scheduled run.

## Consequences

- The CTC Office knows which train enters a yard exit block, so it does not have to
  infer that from occupancy.

## Supersedes

- Release conditions: previously only the yard exit block itself had to be clear and unauthorized; a train released next to another deadlocked both, because a wayside holds any train whose neighbouring block is occupied.
