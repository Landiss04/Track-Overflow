**Target:** truth/arbitration/track-controller-vital-restrictions.md
**Action:** create
**Proposed by:** Codex on Track-Ctrl-SW
**Provenance:** asserted by the user in the Track Controller UI chat, 2026-10-08

---

**Status:** current
**Owner:** Track Controller SW
**Provenance:** asserted by the user 2026-10-08: implement authority truncation, caution-aspect speed restriction, and maintenance authority hold
**Aliases:** authority_truncated, aspect_speed_cap, maintenance_hold
**Last updated:** 2026-10-08

## Vital restrictions

- Authority is restricted to the clear blocks before the first occupied or closed
  block ahead on the travel route. The current block is excluded from the count
  as specified in D013. Authority never increases above the CTC suggestion.
- A Yellow signal halves the commanded speed for its block after the speed-limit
  clamp, rounding down to whole m/s. Yellow replaces the former Orange aspect.
- Maintenance mode holds commanded authority at zero, independently of the PLC.
  The existing zero-authority rule consequently holds commanded speed at zero.

## Supersedes

- Maintenance merely changing switch control without restricting authority:
  superseded by the user's explicit request to enforce a maintenance hold.
