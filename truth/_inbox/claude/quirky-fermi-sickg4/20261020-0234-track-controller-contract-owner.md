**Target:** truth/modules/track-controller/track-controller.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** the Track Controller answers relayed by Kevin Schillinger 2026-10-20, naming the owner of the Track Controller contract shard: "Harry", taken as Harry Tye (Track Controller SW). AGENTS.md requires one named owner for a contract shard. Only the owner, provenance, date and placeholder notice change.

---

# track-controller

*This shard is shared by all variants of this module. It is the definition they
conform to.*

**Status:** placeholder
**Owner:** Harry Tye
**Provenance:** owner only, relayed by Kevin Schillinger 2026-10-20 from the Track Controller answers; the shard asserts no other fact yet
**Aliases:** Wayside Controller
**Variants:** `truth/modules/track-controller/track-controller-sw.md`, `truth/modules/track-controller/track-controller-hw.md`
**Last updated:** 2026-10-20

> ## ⚠ PLACEHOLDER — NOT TRUTH
>
> This shard is a stub. It asserts **nothing** except its owner. Every line below is a pointer to a
> source that has not been read into the truth store yet, not a normative fact.
> Do not cite this file. Do not treat any value here as decided.
>
> An entry without provenance is unverified and must not be treated as truth
> (`AGENTS.md`, Entry rules). Apart from its owner, this shard has no provenance by
> design, until its owner populates it.

## Purpose

**Track Controller** — vital wayside controller governing a section of track.

🔴 **VITAL** — explicitly stated. Exists as a software and a hardware instance.

To be populated:

- What "diverse implementation" concretely means here, and whether a voting or
  arbitration layer is in scope — unresolved, see sources.

## Protocol methods

*Unpopulated.*

## Owns

To be populated:

- Configuration it owns at design time, and which other module may read it.
- Crossing gate and light control.

## Consumes

To be populated:

- Interface contract — the signals it consumes and produces, as entries under
  `truth/signals/`, which is still empty.

## Enforced parameters

To be populated:

- Module-specific units, beyond the project-wide tables in `../../conventions/units.md`.
- PLC scan timing, and how it behaves under 10x fast-forward.

## Failure modes

To be populated:

- Failure modes it simulates or must detect, and the fault-injection contract.

## Does not own

To be populated:

- The boundary against the Track Model: which module interprets a track-circuit
  signal and which only generates it.

## To be populated

- Owner — who on the team owns this module. Required before this shard is truth.

## Sources not yet read into truth

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
