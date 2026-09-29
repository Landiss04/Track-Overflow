# ctc-office

**Status:** placeholder
**Owner:** unassigned
**Provenance:** none — this shard asserts no facts yet
**Aliases:** CTC
**Last updated:** 2026-09-29

> ## ⚠ PLACEHOLDER — NOT TRUTH
>
> This shard is a stub. It asserts **nothing**. Every line below is a pointer to a
> source that has not been read into the truth store yet, not a normative fact.
> Do not cite this file. Do not treat any value here as decided.
>
> An entry without provenance is unverified and must not be treated as truth
> (`AGENTS.md`, Entry rules). This shard has no provenance by design, until someone
> populates it.

## Module

**CTC Office** — dispatcher-facing central control point for the whole system.

Not stated vital, but it issues the authority that vital controllers rely on.

## To be populated

- Owner — who on the team owns this module. Required before this shard is truth.
- Interface contract — the signals it consumes and produces, as entries under
  `truth/signals/`, which is still empty.
- Configuration it owns at design time, and which other module may read it.
- Failure modes it simulates or must detect, and the fault-injection contract.
- Module-specific units, beyond the project-wide tables in `../conventions/units.md`.
- Territory / section assignment per dispatcher.
- Throughput metrics: what is measured and how.
- Whether it owns or only reads the track layout store — see arbitration §4.6 below.

## Sources not yet read into truth

- `common/interfaces.py` — `ICtcOffice`.
- `documents/requirements-matrix.md` §1, §2 — configuration, role, inputs, outputs.
- `documents/requirements-matrix.md` §4.6 — unresolved: this module and the Track
  Model both claim to own the track-layout database.
- `../decisions/D001-drop-mbo-from-scope.md` — the MBO used to supply this module a
  safe authority; it no longer exists.
