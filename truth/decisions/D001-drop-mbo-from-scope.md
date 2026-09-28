# D001-drop-mbo-from-scope

**Status:** current
**Owner:** Team 3
**Provenance:** `documents/requirements-matrix.md` scope note (source: `documents/Project_Information/Final Project vF.pdf`, 81-slide course deck)
**Aliases:** drop MBO, MBO out of scope, moving block overlay
**Last updated:** 2026-09-28

## Context

The course deck specifies a Moving Block Overlay consisting of two components: the
MBO Controller and the MBO Scheduler. In the deck's architecture the overlay computes
a safe authority from live train positions and supplies it to the CTC Office,
bypassing fixed-block authority for trains it covers.

## Decision

Both MBO components are **out of scope** for this implementation. Neither the MBO
Controller nor the MBO Scheduler will be built. The MBO is not a module of this
system and does not appear in the canonical module list in
[`../conventions.md`](../conventions.md) `## Naming`.

## Consequences

- Authority is fixed-block only. Nothing in the system computes a moving-block safe
  authority.
- Dropping the overlay removes some requirements outright and **silently transfers
  others onto the remaining modules**. `requirements-matrix.md` states this and its
  table of contents links to a "Scope gaps created by dropping MBO" section, but that
  section was never written — §4 is "Points of Tension / Conflicts" instead. **The
  transferred requirements have not been enumerated anywhere.** Owner: Team 3.
- `common/interfaces.py` still declares `IMboOverlay`, and its module docstring still
  diagrams the MBO Overlay supplying Safe Authority to the CTC Office. The interface
  contract has not caught up with this decision. Deciding whether to delete
  `IMboOverlay` or keep it as a documented no-op is open.
