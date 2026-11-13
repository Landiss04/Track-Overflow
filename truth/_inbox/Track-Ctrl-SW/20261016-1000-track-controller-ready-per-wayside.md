**Target:** truth/signals/track-controller-ready.md
**Action:** create
**Proposed by:** Claude Code on Track-Ctrl-SW
**Provenance:** asserted by the user in the Track Controller UI chat, 2026-10-16: the ready signal is per line and per wayside controller, so the CTC Office can see which waysides are not ready. Supersedes the unpromoted proposal `20261014-0950-track-controller-ready.md`, which made it one boolean for the whole module.

---

# track-controller-ready

**Status:** current
**Owner:** Track Controller
**Provenance:** asserted by the user 2026-10-16 (Track Controller UI chat); implemented in `TrackCtrlSW/track_ctrl/interface.py` as `CtcReport.ready`
**Aliases:** ready, Track Controller ready, wayside ready, startup complete
**Last updated:** 2026-10-16

## Definition

A boolean per wayside controller, sent every tick from the Track Controller to the CTC
Office, through the central harness, in that wayside's report. The report also names
the wayside's line and, when it is not ready, why. It is true when the wayside has been
started up and false otherwise.

A wayside is started up when its territory is loaded and a PLC program is loaded on it.

## Behaviour

- **The whole stalls with any part.** The track is only safe with every wayside running
  its program, so while any wayside is not ready, no wayside runs its program. Every
  wayside drives its fail-safe outputs whatever its inputs say: speed 0 and authority
  0 on every track circuit, every signal red, every crossing active, every switch left
  where it stands. A wayside that is ready is held too; its flag says it has been
  started up, not that it is running.
- **The system is ready when every wayside is.** There is no separate whole-module
  flag on the wire. The CTC Office takes the whole to be ready only when at least one
  wayside reports and every wayside of every line reports ready. A Track Controller that
  has loaded no territory sends no report, so it is not ready.
- **Ready can be lost.** Loading a new line, or resetting the module, makes the waysides
  of that line not ready until each has a program again. Replacing the program on a
  wayside that is ready does not.

## What the CTC Office does with it

The CTC Office dispatches no train and sends no suggested speed or suggested authority,
on any line, until every wayside is ready. It can show which waysides are not ready and
why. When any goes false again it stops sending.

## Notes

- Startup is done by a person at the Track Controller UI. Neither the CTC Office nor the
  harness loads a line or a program.
- The HW and SW Track Controller each own one line (D014, proposed). Each reports its
  own waysides' readiness; the CTC Office needs all of them.
- Whether the central harness also holds the shared clock until every module is ready is
  not decided here.
- The CTC Office, HW Track Controller and harness owners have not confirmed it. The HW
  Track Controller has the same startup (it loads territories and programs) but reports
  no readiness today.

## Supersedes

- The unpromoted proposal `20261014-0950-track-controller-ready.md` (same author, same
  branch) defined one boolean for the whole Track Controller. Changed on 2026-10-16 to
  one per wayside, with its line, so the CTC Office and a person debugging can see
  which wayside is holding the system. Withdrawn by this proposal, not edited: only a
  human edits or deletes an existing proposal.
