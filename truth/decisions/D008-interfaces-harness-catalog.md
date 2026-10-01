# D008-interfaces-harness-catalog

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin Schillinger 2026-09-30
**Aliases:** common/interfaces.py, interfaces.py, signal catalog, shared interface contracts
**Last updated:** 2026-09-30

## Context

`common/interfaces.py` defines one dataclass per cross-module signal and one abstract
interface per module. No module imports it. The central-harness decision (D005) has each
module define only its own boundary types, with the harness mapping each
producer-to-consumer edge, so the file cannot be a contract that modules import. The
choice was to delete it, keep it as reference only, or give it a role the central
harness can use.

## Decision

`common/interfaces.py` is kept as the system-level signal catalog on the harness side.

- It holds one canonical type per cross-module signal, in backend units per
  `conventions/units.md`.
- The central harness maps through it: each edge mapping translates the producer's
  boundary types into the catalog type and the catalog type into the consumer's.
- Modules never import it. A module's boundary types stay its own.

## Consequences

- Compatible with the central-harness decision (D005): no module's interface contains
  another module's struct layouts, including the catalog's.
- The catalog must agree with truth. When a `signals/` entry or a unit convention
  changes, the catalog changes with it.
- A module's boundary types can still change without touching the catalog. Only that
  module's edge mappings change.
