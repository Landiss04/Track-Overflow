**Target:** truth/arbitration/track-controller-zero-command-switch.md
**Action:** create
**Proposed by:** Codex on feat/windowed-view
**Provenance:** asserted by Kevin Schillinger 2026-11-12 in this chat, requesting that switch tests allow changes when speed/authority is zero

---

# track-controller-zero-command-switch

**Status:** current
**Owner:** Harry Tye
**Provenance:** asserted by Kevin Schillinger 2026-11-12 in this chat
**Aliases:** stopped-train switch release, zero-command switch change
**Last updated:** 2026-11-12

## Definition

A train held on a switch's listed block with commanded speed and authority zero
does not prevent the Track Controller from changing the switch for another train.
Regression tests must allow this switch change rather than requiring the previous
position solely because that block is occupied.

## Scope

This rule concerns the Track Controller. The CTC Office's manual switch-command
restriction is defined separately in `arbitration/no-switch-under-train.md`.
