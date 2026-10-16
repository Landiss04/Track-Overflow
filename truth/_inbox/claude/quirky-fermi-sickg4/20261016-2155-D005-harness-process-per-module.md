**Target:** truth/decisions/D005-central-harness.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-16 in the team's review of `documents/system-integration-design.md`: "Central harness is one process that spawns processes for each module, the whole thing runs as one exe" (decision 4; process model option 2 chosen); "the single executable that will open the central harness and then from there each module can be opened" (G-RUN-2); "The Train Model test UI is removed at integration, and the harness becomes the Train Model's single driver. - this is true for all modules" (section 2.2); "No event logger is needed" (section 2.2).

---

# D005-central-harness

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin Schillinger 2026-09-30, approving the boundary-contract model stated in the Train Model `interface.py` module docstring; one harness process spawning a process per module, one executable, the harness as every module's single driver, and no event logger, asserted by Kevin Schillinger 2026-10-16
**Aliases:** central harness, integration harness, edge mapping functions
**Last updated:** 2026-10-16

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
- The harness is one process. It spawns a separate process for each module.
- The whole system runs as one executable. The executable opens the central harness,
  and each module is opened from there.
- At integration the harness is the single driver of every module, and every module's
  test UI is removed, as D010 already says for the Train Model.

## Consequences

- The harness is not one of the five modules in `conventions/naming.md`. It is
  integration infrastructure, like the shared clock in `conventions/files-and-paths.md`.
- Unit and type agreement between two modules is checked in one place: the mapping
  function for that edge.
- A module's boundary types can change without editing another module. Only the
  affected edge mapping changes.

## Supersedes

- Event logger: previously named beside the shared clock as integration infrastructure;
  no event logger is needed (Kevin Schillinger 2026-10-16).
