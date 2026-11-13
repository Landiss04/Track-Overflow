**Target:** truth/signals/brake-state.md
**Action:** replace
**Proposed by:** Codex on claude/quirky-fermi-sickg4
**Provenance:** Kevin Schillinger’s October 20, 2026 SDD review; documents/Railway_Sim_SDD_Train_Model.md v0.2 §4.9; direct documentation request 2026-10-20

---

# brake-state

**Status:** current
**Owner:** Train Model
**Provenance:** Kevin Schillinger’s October 20, 2026 SDD review; documents/Railway_Sim_SDD_Train_Model.md v0.2 §4.9; direct documentation request 2026-10-20
**Aliases:** Brake State, Emergency Brake State, e-brake state, emergency brake active, service brake state
**Last updated:** 2026-10-20

## Definition

Two booleans, `bool[2]`, from the Train Model to the Train Controller: emergency
engaged at element 0, service engaged at element 1. These report actual engagement.

## Notes

- Emergency is active for the controller command or the passenger latch.
- Service is active for its command unless service brake failure is active.
- Both may be true. Service failure blocks only service; emergency remains available.
- Both engaged brakes contribute their configured force, per
  [brakes-apply-together](../arbitration/brakes-apply-together.md).
- A one-shot [passenger-brake-release](passenger-brake-release.md) clears only
  the passenger latch; an independently held controller emergency command remains active.

## Supersedes

- Previously left the service element during emergency engagement unspecified; the reviewed design defines independent engagement and summed forces.
