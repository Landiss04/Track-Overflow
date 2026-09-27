# train-controller

**Status:** placeholder
**Owner:** unassigned
**Provenance:** none — this shard asserts no facts yet
**Aliases:** SW Train Controller, HW Train Controller, onboard controller
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

**Train Controller** — vital onboard controller governing a single train.

🔴 **VITAL** — explicitly stated. Exists as a software and a hardware instance.

## To be populated

- Owner — who on the team owns this module. Required before this shard is truth.
- Interface contract — the signals it consumes and produces, as entries under
  `truth/signals/`, which is still empty.
- Configuration it owns at design time, and which other module may read it.
- Failure modes it simulates or must detect, and the fault-injection contract.
- Module-specific units, beyond the project-wide tables in `../conventions.md`.
- Control-law tuning constants `Kp`, `Ki`, `T`, `Pmax`. The deck requires they be
  chosen so the system is stable but supplies **no default values**. Nothing is
  recorded anywhere; the team must derive and verify them.
- How `T` is derived under 10x fast-forward rather than assumed from wall clock.
- Whether the diversity requirement stated for the Track Controller also applies
  here — both carry the same vital bar, the deck states it only for the other.
- Station announcements, door sequencing, and light scheduling.

## Sources not yet read into truth

- `common/interfaces.py` — `ISwTrainController`.
- `documents/requirements-matrix.md` §1 — `Kp`, `Ki`, `T`, `Pmax` with no defaults.
- `documents/requirements-matrix.md` §4.1 — unresolved: vital logic on a non-vital
  communication channel.
- `documents/requirements-matrix.md` §4.4 — unresolved: control-law timing under
  fast-forward.
- `documents/requirements-matrix.md` §5 — names the tuning constants as needing team
  sign-off before implementation.
- `documents/UI_Style_Guide.md` §7 — this module's emergency brake is the only
  unconfirmed destructive control in the system.
