# track-controller

**Status:** placeholder
**Owner:** unassigned
**Provenance:** none — this shard asserts no facts yet
**Aliases:** Wayside Controller, SW Track Controller, HW Track Controller, PLC
**Last updated:** 2026-09-25

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

**Track Controller** — vital wayside controller governing a section of track.

🔴 **VITAL** — explicitly stated. Exists as a software and a hardware instance.

## To be populated

- Owner — who on the team owns this module. Required before this shard is truth.
- Interface contract — the signals it consumes and produces, as entries under
  `truth/signals/`, which is still empty.
- Configuration it owns at design time, and which other module may read it.
- Failure modes it simulates or must detect, and the fault-injection contract.
- Module-specific units, beyond the project-wide tables in `../conventions.md`.
- What "diverse implementation" concretely means here, and whether a voting or
  arbitration layer is in scope — unresolved, see sources.
- The boundary against the Track Model: which module interprets a track-circuit
  signal and which only generates it.
- PLC scan timing, and how it behaves under 10x fast-forward.
- Crossing gate and light control.

## Sources not yet read into truth

- `common/interfaces.py` — `ISwTrackController`.
- `documents/requirements-matrix.md` §1, §2 — the user-written PLC program is required
  to be specifiable separately from the controller's own implementation.
- `documents/requirements-matrix.md` §4.1 — unresolved: a vital controller acting on
  data that arrives over a channel the deck calls non-vital.
- `documents/requirements-matrix.md` §4.2 — unresolved: overlapping ownership of
  presence and switch state with the Track Model.
- `documents/requirements-matrix.md` §4.3 — unresolved: scope of the diversity
  requirement.
- `documents/requirements-matrix.md` §4.5 — unresolved: fault-injection contract with
  the Track Model.
