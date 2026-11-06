**Target:** truth/arbitration/maintenance-closure-lock.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** Landis, reply to `documents/module-owner-review.md` INPUT-1, relayed by Kevin Schillinger 2026-10-25

---

# maintenance-closure-lock

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-06 (blocks closed in maintenance mode must not be overridden by the Track Controller; it queries the list, and regains control once a block is reopened); extended to switches set in maintenance mode, Landis's reply to module owner review INPUT-1, relayed by Kevin Schillinger 2026-10-25
**Aliases:** maintenance lock, closure precedence, closed block override, maintenance list, switch override lock
**Last updated:** 2026-10-25

## Definition

The CTC Office keeps the list of blocks and switches it controls in maintenance mode
and sends it to the Track Controller. A listed block or switch is the CTC Office's:
its closure or position takes precedence over the Track Controller. Before the Track
Controller sets a switch, or closes or opens a block, it checks the list, and it does
not change a listed block or switch.

Closures are set only in maintenance mode, and only the CTC Office reopens them, in
maintenance mode. When the dispatcher reopens a block, or releases a switch, it comes
off the list and the Track Controller controls it again.

## Notes

- A block is listed, and so locked, from the moment its closure is requested, even
  while a train is still in it.
- The Track Controller has no authority over a CTC Office closure.

## Supersedes

- Scope: previously blocks only, with switch positions set in maintenance mode not
  covered; now blocks and switches (Landis, relayed by Kevin Schillinger 2026-10-25).
