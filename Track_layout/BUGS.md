# Known bugs

Open bugs in the Track Model, in the format of the Train Model's
[`docs/bugs.md`](../TrainModel/docs/bugs.md): each has a way to reproduce it, its
cause, and a suggested fix. Fixed bugs are removed from this list; git holds their
history.

Severity:

- **Medium**: reachable in normal use, or on a real line.
- **Low**: needs a value no real producer sends, or is cosmetic.

| ID | Area | Severity | Summary |
|---|---|---|---|
| [B1](#b1) | Model | Medium | The light ahead reaches a train only as it enters a signal block |

## Bugs

### B1

**The light ahead reaches a train only as it enters a signal block.** Model,
Medium. Logged at Kevin Schillinger's direction on 2026-10-20, from Phase 2 of the
central harness (`documents/system-integration-design.md`, G-SIG-10).

- **Expected:** truth `signals/signal-aspect-ahead.md`: the state of the next signal
  light ahead of a train, sent to that train's Train Controller, standing for what
  the driver sees through the windshield. The Train Controller should always have
  the light ahead of the train.
- **Reproduce:** run the system (`python track_overflow.py`). G1 leaves block 63 and
  enters block 64, which has a light. On that one tick its Train Controller gets the
  light; on every other tick it gets nothing, and keeps the last light it was given,
  wherever the train has gone since. Change the light while the train is in block
  64 and the train never learns of it.
- **Cause:** `signal_seen` in `TrackModelOutputs` is the colour of the light on the
  block a train has just entered, on the tick it enters, and `None` on every other
  tick (`model._signal_seen`).
- **Second part:** the light shown is that of the block entered, whichever way the
  train runs. A light stands on the block before each switch, on its fixed side, and
  guards the switch for trains heading toward it (`layout._signal_blocks`): block
  64's light guards the switch at 63 for trains running 64 to 63. G1, running 63 to
  64, is shown that light although it faces away from it.
- **Fix:** each tick, for each train, walk the route ahead of it in its direction of
  travel (`Layout.next_block` with the switches as set), from its own block, and send
  the first light that faces it: a light block whose next block that way is the
  switch it guards. Send it on every tick, and `None` only where no light lies ahead
  before the yard or a dead end. The harness passes whatever the Track Model sends
  (`common/harness/track_edges.py`, `edges.py`), so no harness change is needed.
