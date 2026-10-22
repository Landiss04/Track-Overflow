**Target:** truth/decisions/D006-fixed-time-step.md
**Action:** replace
**Proposed by:** Codex on claude/quirky-fermi-sickg4
**Provenance:** Kevin Schillinger’s October 20, 2026 SDD review; documents/Railway_Sim_SDD_Train_Model.md v0.2 §4.9; direct documentation request 2026-10-20

---

# D006-fixed-time-step

**Status:** current
**Owner:** Kevin
**Provenance:** Kevin Schillinger’s October 20, 2026 SDD review; documents/Railway_Sim_SDD_Train_Model.md v0.2 §4.9; direct documentation request 2026-10-20
**Aliases:** fixed dt, sample period, tick model, step(dt)
**Last updated:** 2026-10-20

## Context

Changing the physical sample duration with simulation speed would change the
computed response. Internal event handling is compatible with a fixed external tick.

## Decision

- The harness supplies a constant external dt to `step(dt, inputs)` throughout a run.
- Fast-forward (10x) and pause change tick frequency only, never dt.
- Retain the numerical algorithm in `TrainModel/train_model/model.py`: exact
  constant-force segments and midpoint power-limited integration. Internal boundaries
  resolve stops and traction-regime transitions; stability limits may split segments
  further. Their durations sum to the external dt.
- Position uses each segment’s average endpoint velocity. Midpoint power evaluation
  accounts for commanded work over a power-limited segment without artificial energy
  gain, including work opposing rollback. Event boundaries handle stops and regime
  changes accurately and keep the integration stable.
- dt validation is defensive; it does not permit varying the external dt during a run.

## Consequences

The same dt and input sequence produces the same motion at either simulation speed.
The harness owns the shared clock and fans out dt and time to every module (D017).

## Supersedes

- Previously required trapezoidal integration without internal substeps; Kevin’s October 20 review retains the existing segmented algorithm while preserving fixed external dt.
