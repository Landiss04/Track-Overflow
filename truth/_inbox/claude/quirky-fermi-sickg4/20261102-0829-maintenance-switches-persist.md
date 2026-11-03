**Target:** truth/arbitration/maintenance-closure-lock.md
**Action:** replace
**Proposed by:** Integration on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-11-02, answering Landis's open question on whether the switch list persists after maintenance mode ends: "any switch that is set in maintence mode should hold even if mode is switched to manual or automatic, meaning the only time that that list does not persist is when the CTC has removed all of the manually set switch states. waysides should be querying these switch values (if they exist) before they make any updates to the switch states." Replaces the unpromoted proposal 20261025-2129-maintenance-closure-lock-switches.md on this branch, adding persistence.

---

# maintenance-closure-lock

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-10-06 (blocks closed in maintenance mode must not be overridden by the Track Controller; it queries the list, and regains control once a block is reopened); extended to switches set in maintenance mode, Landis's reply to module owner review INPUT-1, relayed by Kevin Schillinger 2026-10-25; switch positions persist after maintenance mode ends, asserted by Kevin Schillinger 2026-11-02
**Aliases:** maintenance lock, closure precedence, closed block override, maintenance list, switch override lock, manually set switches, maintenance switch list
**Last updated:** 2026-11-02

## Definition

The CTC Office keeps the list of blocks and switches it controls in maintenance mode
and sends it to the Track Controller. A listed block or switch is the CTC Office's:
its closure or position takes precedence over the Track Controller. Before the Track
Controller sets a switch, or closes or opens a block, it checks the list, and it does
not change a listed block or switch. A switch with no listed position is the Track
Controller's to set.

Closures and switch positions are set only in maintenance mode. Both persist when
the dispatcher leaves maintenance mode for Manual or Automatic: changing mode does
not remove anything from the list. An entry comes off the list only when the CTC
Office removes it: the dispatcher reopens the block, or removes the switch's
manually set position. The Track Controller then controls it again.

## Notes

- A block is listed, and so locked, from the moment its closure is requested, even
  while a train is still in it.
- The Track Controller has no authority over a CTC Office closure or a listed
  switch position.

## Supersedes

- Scope: previously blocks only, with switch positions set in maintenance mode not
  covered; now blocks and switches (Landis, relayed by Kevin Schillinger 2026-10-25).
- Switch persistence: not previously stated; switch positions now outlast maintenance
  mode and leave the list only when the CTC Office removes them (Kevin Schillinger
  2026-11-02).
