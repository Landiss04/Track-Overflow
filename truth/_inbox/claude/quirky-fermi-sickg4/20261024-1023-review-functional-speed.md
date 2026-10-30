**Target:** truth/decisions/review-functional-speed.md
**Action:** create
**Proposed by:** Integration on claude/quirky-fermi-sickg4
**Provenance:** Kevin Schillinger, 2026-10-24: "yes option a is better", accepting functional review at 1x with TIME_SLIPPED retained as a fault and 10x measured separately; earlier "wait for pi measurements" retained.

---

# review-functional-speed

**Status:** current
**Owner:** Kevin Schillinger
**Provenance:** asserted by Kevin Schillinger 2026-10-24: "yes option a is better", accepting functional review at 1x, retaining TIME_SLIPPED as a fault, and measuring 10x separately; "wait for pi measurements", 2026-10-22
**Aliases:** functional review speed, review 1x, TIME_SLIPPED review acceptance
**Last updated:** 2026-10-24

## Decision

The manual and scheduled functional review scenarios run at 1x. TIME_SLIPPED remains a
fault for functional review acceptance alongside the existing safety and protocol faults.

Measure 10x separately from functional acceptance. The speed decision and optimization
wait for measurements on real Raspberry Pis.
