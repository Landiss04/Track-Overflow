# D005-central-harness

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin Schillinger 2026-09-30, approving the boundary-contract model stated in the Train Model `interface.py` module docstring
**Aliases:** central harness, integration harness, edge mapping functions
**Last updated:** 2026-09-30

## Context

Each module needs types for the data it exchanges with other modules. The alternative
is for each module to import the other modules' struct layouts. That couples every pair
of modules, so a field change in one module breaks its neighbors.

## Decision

A central harness sits between the modules.

- Each module defines only its own boundary types.
- The harness owns one pure mapping function per producer-to-consumer edge. The function
  translates the producer's output types into the consumer's input types.
- No module's interface contains another module's struct layouts.

## Consequences

- The harness is not one of the five modules in `conventions/naming.md`. It is
  integration infrastructure, like the shared clock and event logger in
  `conventions/files-and-paths.md`.
- Unit and type agreement between two modules is checked in one place: the mapping
  function for that edge.
- A module's boundary types can change without editing another module. Only the
  affected edge mapping changes.
