# D006-fixed-time-step

**Status:** current
**Owner:** Kevin
**Provenance:** `Train_Model_Backend_Design.pdf` §1 (Locked), supplied by Kevin Schillinger 2026-09-30
**Aliases:** fixed dt, sample period, tick model, step(dt)
**Last updated:** 2026-09-30

## Context

The Train Model integrates its physics with trapezoidal integration over a sample
period T (course material, slide 62). The simulation also runs at 10x fast-forward and
can pause (`conventions/files-and-paths.md`: one shared clock supporting real time and
fast-forward). If the time step changed with the simulation speed, the physics would
behave differently at different speeds.

## Decision

- The Train Model is stepped from outside through `step(dt)`, with dt constant.
- Fast-forward (10x) and pause change the tick rate, never dt.
- The Train Model does not sub-step.
- Validating dt is a defensive check only.

## Consequences

- A given input sequence produces the same train behaviour at any simulation speed.
- The shared clock sets how often ticks happen, not how long each tick is.
- This decision comes from the Train Model design. The other modules' owners have not
  confirmed that they step the same way.
