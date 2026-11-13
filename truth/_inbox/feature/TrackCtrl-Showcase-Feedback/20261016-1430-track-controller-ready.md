**Target:** truth/signals/track-controller-ready.md
**Action:** create
**Proposed by:** GitHub Copilot on feature/TrackCtrl-Showcase-Feedback
**Provenance:** asserted on `Track-Ctrl-SW` 2026-10-16 (proposal `20261016-1000-track-controller-ready-per-wayside.md`); adopted for the HW Track Controller by Braden 2026-10-16

Note for the promoter: the same entry as the pending proposal
`truth/_inbox/Track-Ctrl-SW/20261016-1000-track-controller-ready-per-wayside.md`
on `Track-Ctrl-SW`, with three changes. Promote one of the two and deny the
other.

1. Notes record that the HW Track Controller owner adopted it (Braden
   2026-10-16), replacing "the HW Track Controller owner has not confirmed it".
2. "Resetting the module" no longer drops ready under Behaviour: the HW
   Track Controller's test UI reset keeps its programs. It is under
   `## Pending` instead.
3. `## Conflict` records that the CTC Office's pending proposal
   `arbitration/nothing-sent-until-track-controller-ready.md` on
   `ctc-deployment` gates each line on its own, where this entry gates every
   line on every wayside.

---

# track-controller-ready

**Status:** current
**Owner:** Track Controller
**Provenance:** asserted on `Track-Ctrl-SW` 2026-10-16 (proposal `20261016-1000-track-controller-ready-per-wayside.md`); adopted for the HW Track Controller by Braden 2026-10-16
**Aliases:** ready, Track Controller ready, wayside ready, startup complete
**Last updated:** 2026-10-16

## Definition

A boolean per wayside controller, sent every tick from the Track Controller to
the CTC Office, through the central harness, in that wayside's report. The
report also names the wayside's line and, when it is not ready, why. It is true
when the wayside has been started up and false otherwise.

A wayside is started up when its territory is loaded and a PLC program is
loaded on it.

## Behaviour

- **The whole stalls with any part.** The track is only safe with every wayside
  running its program, so while any wayside is not ready, no wayside runs its
  program. Every wayside drives its fail-safe outputs whatever its inputs say:
  speed 0 and authority 0 on every track circuit, every signal red, every
  crossing active, every switch left where it stands. A wayside that is ready
  is held too; its flag says it has been started up, not that it is running.
- **The system is ready when every wayside is.** There is no separate
  whole-module flag on the wire. The CTC Office takes the whole to be ready only
  when at least one wayside reports and every wayside of every line reports
  ready. A Track Controller that has loaded no territory sends no report, so it
  is not ready.
- **Ready can be lost.** Loading a new line makes the waysides of that line not
  ready until each has a program again. Replacing the program on a wayside that
  is ready does not.

## What the CTC Office does with it

The CTC Office dispatches no train and sends no suggested speed or suggested
authority, on any line, until every wayside is ready. It can show which
waysides are not ready and why. When any goes false again it stops sending.

## Notes

- Startup is done by a person at the Track Controller UI. Neither the CTC Office
  nor the harness loads a line or a program.
- The HW and SW Track Controller each own one line (D014, proposed). Each
  reports its own waysides' readiness; the CTC Office needs all of them.
- The HW Track Controller runs its program on two diverse channels. A wayside
  whose channels disagree is not ready until a new program is loaded.
- Whether the central harness also holds the shared clock until every module is
  ready is not decided here.
- The HW and SW Track Controller owners have adopted it. The CTC Office and
  harness owners have not confirmed it.

## Pending

- Whether resetting the module from a test UI makes its waysides not ready. The
  SW Track Controller's reset unloads its programs, so they are not ready; the
  HW Track Controller's keeps them, so they stay ready. Owner: Braden and Harry
  to agree.

## Conflict

- **Every line waits on every wayside** (this entry, from the `Track-Ctrl-SW`
  proposal of 2026-10-16): the CTC Office dispatches and sends nothing on any
  line until every wayside of every line is ready.
- **Each line waits only on its own** (`arbitration/nothing-sent-until-track-controller-ready.md`,
  pending on `ctc-deployment`, asserted by Landis 2026-10-15): the Track
  Controller reports ready per line, and one line being ready does not wait on
  the other.

**Resolution owner:** Landis

## Supersedes

- The unpromoted proposal `20261014-0950-track-controller-ready.md` on
  `Track-Ctrl-SW` defined one boolean for the whole Track Controller. Changed on
  2026-10-16 to one per wayside, with its line, so the CTC Office and a person
  debugging can see which wayside is holding the system.
