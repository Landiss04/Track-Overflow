**Target:** truth/decisions/D008-interfaces-harness-catalog.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-16 in the team's review of `documents/system-integration-design.md`: "Common/interfaces.py is stale and should not be treated as true" (section 2.2); "common/interfaces.py has been superseded" (section 3.4).

---

# D008-interfaces-harness-catalog

**Status:** superseded
**Owner:** Kevin
**Provenance:** asserted by Kevin Schillinger 2026-09-30; superseded by Kevin Schillinger 2026-10-16
**Aliases:** common/interfaces.py, interfaces.py, signal catalog, shared interface contracts
**Last updated:** 2026-10-16

## Context

`common/interfaces.py` defines one dataclass per cross-module signal and one abstract
interface per module. No module imports it. The central-harness decision (D005) has each
module define only its own boundary types, with the harness mapping each
producer-to-consumer edge, so the file cannot be a contract that modules import. The
choice was to delete it, keep it as reference only, or give it a role the central
harness can use.

## Decision

`common/interfaces.py` is stale. It is not treated as true and is no longer the
system-level signal catalog. Modules never import it.

## Consequences

- The central harness's edge mappings (D005) do not map through
  `common/interfaces.py`.
- Open: whether another catalog replaces it is not stated.

## Supersedes

- Previously `common/interfaces.py` was kept as the system-level signal catalog on the
  harness side, and each edge mapping translated through it (Kevin Schillinger
  2026-09-30). Superseded because the file is stale (Kevin Schillinger 2026-10-16).
