# train-model

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

**Train Model** — simulated physical model of a train's dynamics.

Not vital: a physical simulation, not a controller.

## To be populated

- Owner — who on the team owns this module. Required before this shard is truth.
- Interface contract — the signals it consumes and produces, as entries under
  `truth/signals/`, which is still empty.
- Configuration it owns at design time, and which other module may read it.
- Failure modes it simulates or must detect, and the fault-injection contract.
- Module-specific units, beyond the project-wide tables in `../conventions/units.md`.
- Physical dimensions, mass, crew count, passenger capacity, car count for a single
  or multi-car consist, and acceleration / velocity limit parameters.
- Terrain-aware Newtonian point-mass dynamics, and the grade input it depends on —
  degrees, per `../conventions/units.md`.
- Tunnel light controller.
- Failure modes it simulates: engine failure, signal pickup failure, brake failure.

## Sources not yet read into truth

- `common/interfaces.py` — `ITrainModel`, `TrainState`, `TrainPosition`, `Beacon`.
- `documents/requirements-matrix.md` §1, §2 — static config and runtime data.
- `documents/requirements-matrix.md` §4.5 — unresolved: fault-injection contract with
  the Train Controller.
- `documents/srs-filled.md` Appendix B — safe braking distance formula.
- `documents/Project_Information/Blackpool_Flexity2.pdf`,
  `documents/Project_Information/Track Layout & Vehicle Data vF5.xlsx` — vehicle data, unread.
