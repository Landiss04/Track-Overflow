**Target:** truth/signals/track-controller-ready.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** as `20261016-2254-track-controller-ready-per-line.md` on this branch, which this proposal supersedes (deny that one), plus the Track Controller answers relayed by Kevin Schillinger 2026-10-20: "PLC programs and databases are not loaded by default. This is the purpose of using a ready signal. Unready system does not gate clock advancement". The competing proposals that gate every line stay as noted in the superseded file.

---

# track-controller-ready

**Status:** current
**Owner:** Track Controller
**Provenance:** asserted by Kevin Schillinger 2026-10-16; programs and databases not loaded by default, and readiness not holding the clock, relayed by Kevin Schillinger 2026-10-20 from the Track Controller answers
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
- Readiness gates dispatch, not time. A Track Controller that is not ready does not
  hold the shared clock.
