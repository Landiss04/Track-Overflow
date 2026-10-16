**Target:** truth/signals/track-controller-ready.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-16 in the team's review of `documents/system-integration-design.md` (decision 8): "Shape is 2d array : per line, per track controller. Action is fully gated per line until every track controller signals ready. One line can operate while the other is stalled but all track controllers on one line need to be ready for safe operation(i.e. no dispatch of trains until ready)". Same target as the pending `Track-Ctrl-SW/20261014-0950-track-controller-ready.md`, `Track-Ctrl-SW/20261016-1000-track-controller-ready-per-wayside.md` and PR #43's `feature/TrackCtrl-Showcase-Feedback/20261016-1430-track-controller-ready.md`, which hold every line while any wayside is not ready; this one gates each line on its own. The gate matches the pending arbitration `ctc-deployment/20261016-1354-nothing-sent-until-every-wayside-ready.md`.

---

# track-controller-ready

**Status:** current
**Owner:** Track Controller
**Provenance:** asserted by Kevin Schillinger 2026-10-16
**Aliases:** Track Controller ready, wayside ready, ready, readiness
**Last updated:** 2026-10-16

## Definition

Whether each Track Controller is ready, sent from the Track Controller to the CTC
Office as a 2-D array: per line, and per Track Controller on that line.

A line is ready once every Track Controller on it signals ready.

## Notes

- Action is gated per line. Until every Track Controller on a line signals ready, no
  train is dispatched on that line. One line can operate while the other is stalled.
- Open: what makes a Track Controller ready is not stated in this entry.
