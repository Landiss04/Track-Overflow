**Target:** truth/signals/track-controller-ready.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** as `20261020-0039-track-controller-ready-loaded-by-hand.md` on this branch, which this proposal supersedes (deny that one), plus the Track Controller answers relayed by Kevin Schillinger 2026-10-20: a wayside is ready exactly when its database and PLC program are both loaded ("yes"); every wayside of the line is reported from startup, "not ready until ready".

---

# track-controller-ready

**Status:** current
**Owner:** Track Controller
**Provenance:** asserted by Kevin Schillinger 2026-10-16; programs and databases not loaded by default, and readiness not holding the clock, relayed by Kevin Schillinger 2026-10-20 from the Track Controller answers; what makes a wayside ready, and every wayside reported from startup, from the same answers
**Aliases:** Track Controller ready, wayside ready, ready, readiness
**Last updated:** 2026-10-20

## Definition

Whether each Track Controller is ready, sent from the Track Controller to the CTC
Office as a 2-D array: per line, and per Track Controller on that line.

A line is ready once every Track Controller on it signals ready.

## Notes

- Action is gated per line. Until every Track Controller on a line signals ready, no
  train is dispatched on that line. One line can operate while the other is stalled.
- PLC programs and wayside databases are not loaded by default. A person loads them at
  the Track Controller, and the ready signal reports when that is done.
- A wayside is ready exactly when both its database and its PLC program are loaded.
- Each Track Controller reports every wayside of its line from startup. A wayside that
  is not loaded yet reports not ready, so a line cannot read ready before all its
  waysides are loaded.
- Readiness gates dispatch, not time. A Track Controller that is not ready does not
  hold the shared clock.
