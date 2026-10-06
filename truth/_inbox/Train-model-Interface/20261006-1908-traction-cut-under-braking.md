**Target:** truth/arbitration/traction-cut-under-braking.md
**Action:** replace
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** the door interlock taken out of the Train Model pending the course instructor, asserted by Kevin Schillinger 2026-10-06 in this chat (quoted in `20261006-1908-door-command.md`); not in the repository. Only the note contrasting this rule with the door interlock changes; the rule itself is unchanged.

---

# traction-cut-under-braking

**Status:** current
**Owner:** Train Controller
**Provenance:** asserted by Kevin Schillinger 2026-10-02; the door interlock no longer the Train Model's, asserted by Kevin Schillinger 2026-10-06, pending the course instructor
**Aliases:** traction interlock, propulsion cut on brake, power cut while braking, brake-traction interlock
**Last updated:** 2026-10-06

## Definition

When a brake is engaged, cutting traction is the Train Controller's decision. The Train
Controller sets Power Command to zero when it brakes. The Train Model applies the
commanded power and the engaged brakes as independent forces. It does not cut traction
on its own, for a service brake, an emergency brake, or a passenger pull.

## Notes

- A passenger pull originates in the Train Model. The Train Controller learns of it
  through Brake State and is responsible for removing power in response.
- This is control logic, not a vehicle interlock. The Train Model enforces no door
  interlock either (`signals/door-command.md`, pending the course instructor).

## Supersedes

- Note on the door interlock: previously the contrast, a vehicle interlock enforced by
  the Train Model; the Train Model no longer enforces it (Kevin Schillinger
  2026-10-06).
