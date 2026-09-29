# track-model

**Status:** placeholder
**Owner:** unassigned
**Provenance:** none — this shard asserts no facts yet
**Aliases:** none
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

**Track Model** — simulated physical model of the track layout.

Not vital: a physical simulation, not a controller.

## To be populated

- Owner — who on the team owns this module. Required before this shard is truth.
- Interface contract — the signals it consumes and produces, as entries under
  `truth/signals/`, which is still empty.
- Configuration it owns at design time, and which other module may read it.
- Failure modes it simulates or must detect, and the fault-injection contract.
- Module-specific units, beyond the project-wide tables in `../conventions/units.md`.
- Track layout ingestion. The file format is JSON — see `../conventions/units.md`
  `## Resolved`.
- Configurable block size, and the track layout input method.
- Whether this module owns the canonical layout store — see sources.
- Railway crossings, stations, power limitations, track heater.
- Failure modes it simulates: broken rail, track circuit failure, power failure.

## Sources not yet read into truth

- `common/interfaces.py` — `ITrackModel`, `BlockState`, `SwitchState`,
  `CrossingState`, `TrackSignal`, `FailureMode`.
- `documents/requirements-matrix.md` §1, §2 — static config and runtime data.
- `documents/requirements-matrix.md` §4.2 — unresolved: detection and switch-state
  ownership shared with the Track Controller.
- `documents/requirements-matrix.md` §4.6 — unresolved: this module and the CTC Office
  both claim to own the track-layout database.
- `documents/srs-filled.md` Appendix A — the JSON block fields, including "grade (%)",
  which conflicts with `grade_deg`.
- `TrackModel/blue_line.json`, `red_line.json`, `green_line.json` — layout data in the
  repo.
