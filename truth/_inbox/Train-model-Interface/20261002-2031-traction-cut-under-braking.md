**Target:** truth/arbitration/traction-cut-under-braking.md
**Action:** create
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** asserted by Kevin Schillinger 2026-10-02 in this chat ("the train controller is responsible for this decision"), declining a traction cut in the Train Model; consistent with the inbox proposal `20260930-2235-train-model-control-boundary.md`

---

# traction-cut-under-braking

**Status:** current
**Owner:** Train Controller
**Provenance:** asserted by Kevin Schillinger 2026-10-02
**Aliases:** traction interlock, propulsion cut on brake, power cut while braking, brake-traction interlock
**Last updated:** 2026-10-02

## Definition

When a brake is engaged, cutting traction is the Train Controller's decision. The Train
Controller sets Power Command to zero when it brakes. The Train Model applies the
commanded power and the engaged brakes as independent forces. It does not cut traction
on its own, for a service brake, an emergency brake, or a passenger pull.

## Notes

- A passenger pull originates in the Train Model. The Train Controller learns of it
  through Brake State and is responsible for removing power in response.
- Unlike the door interlock (`signals/door-command.md`), this is control logic, not a
  vehicle interlock enforced by the Train Model.
