**Target:** truth/decisions/D005-central-harness.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** as `20261016-2155-D005-harness-process-per-module.md` on this branch, which this proposal supersedes (deny that one), plus points proposed in the per-module questions of `documents/system-integration-design.md` and accepted by Kevin Schillinger 2026-10-20 ("any other open question that was not directly addressed is that your suggestions were accepted"): direct producer-to-consumer mappings; newline-delimited JSON with a request ID and tick number and one driver; a ready message, windows that hide rather than close, and shutdown by the harness; changes between ticks in the next outputs, with pause read from the CTC Office's state; starting every module at once; showing rejected ticks in the harness window. Exactly-once delivery from the CTC Office's answers of 2026-10-20, relayed by Kevin Schillinger: "these are one-time events, so the harness must apply every tick's outputs exactly once".

---

# D005-central-harness

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin Schillinger 2026-09-30, approving the boundary-contract model stated in the Train Model `interface.py` module docstring; one harness process spawning a process per module, one executable, the harness as every module's single driver, and no event logger, asserted by Kevin Schillinger 2026-10-16; the harness protocol, module readiness and shutdown, and changes made between ticks, proposed in the design doc's per-module questions and accepted by Kevin Schillinger 2026-10-20; every tick's outputs passed on exactly once, agreed in the CTC Office's answers of 2026-10-20, relayed by Kevin Schillinger
**Aliases:** central harness, integration harness, edge mapping functions
**Last updated:** 2026-10-20

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
- Each mapping function goes straight from the producer's types to the consumer's;
  there is no catalog in between (D008).
- The harness and the modules exchange newline-delimited JSON messages. Each carries an
  integer request ID and the tick number. A module accepts one driver: the harness.
- The harness passes each module's outputs from a tick on exactly once.
- Each module process tells the harness when it is ready. Closing a module's window
  hides it; only the harness ends a module process.
- A change a person makes in a module's window reaches the other modules through that
  module's next outputs. While the clock is paused no tick runs, so the harness reads
  the CTC Office's `clock_paused` from the CTC Office's state instead.

## Consequences

- The harness is not one of the five modules in `conventions/naming.md`. It is
  integration infrastructure, like the shared clock in `conventions/files-and-paths.md`.
- Unit and type agreement between two modules is checked in one place: the mapping
  function for that edge.
- A module's boundary types can change without editing another module. Only the
  affected edge mapping changes.
- The harness starts every module process at once, and allows Run once each has said
  it is ready.
- On exit the harness tells every module to quit, and ends any that do not.
- The harness shows each rejected tick in its own window, with the module, the tick and
  the reason.

## Supersedes

- Event logger: previously named beside the shared clock as integration infrastructure;
  no event logger is needed (Kevin Schillinger 2026-10-16).
