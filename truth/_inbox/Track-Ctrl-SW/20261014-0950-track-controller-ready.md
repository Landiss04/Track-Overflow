**Target:** truth/signals/track-controller-ready.md
**Action:** create
**Proposed by:** Claude Code on Track-Ctrl-SW
**Provenance:** asserted by the user in the Track Controller UI chat, 2026-10-14: the Track Controller is vital, so it must stall until its line and every wayside's PLC program are loaded, and tell the CTC Office with a ready signal

---

# track-controller-ready

**Status:** current
**Owner:** Track Controller
**Provenance:** asserted by the user 2026-10-14 (Track Controller UI chat); implemented in `TrackCtrlSW/track_ctrl/module.py` as `TrackControllerOutputs.ready`
**Aliases:** ready, Track Controller ready, startup complete, wayside ready
**Last updated:** 2026-10-14

## Definition

A boolean sent every tick from the Track Controller to the CTC Office, through the
central harness. It is true when the Track Controller has been started up and false
otherwise. It belongs to the whole module, not to one wayside.

The Track Controller is started up when both hold:

- a line is loaded, so every wayside has its territory; and
- a PLC program is loaded on every wayside of that line.

## Behaviour

- **Not ready.** No wayside runs its PLC program. Every wayside drives its fail-safe
  outputs whatever its inputs say: speed 0 and authority 0 on every track circuit,
  every signal red, every crossing active, every switch left where it stands. One
  wayside without a program is enough to stall all of them.
- **Ready.** The programs run and the outputs follow them, restricted by the vital
  layer.
- **Ready can be lost.** Loading a new line, or resetting the module, makes a ready
  Track Controller not ready again until every wayside has a program. Replacing the
  program on a wayside of a ready Track Controller does not.

## What the CTC Office does with it

The CTC Office dispatches no train and sends no suggested speed or suggested
authority while the Track Controller is not ready. When it goes false again the CTC
Office stops sending.

## Notes

- Startup is done by a person at the Track Controller UI. Neither the CTC Office nor
  the harness loads a line or a program.
- The HW and SW Track Controller each own one line (D014, proposed). Each reports
  its own ready. Whether the CTC Office needs both before it dispatches on either
  line is not decided here.
- Whether the central harness also holds the shared clock until every module is
  ready is not decided here.
- The CTC Office, HW Track Controller and harness owners have not confirmed it. The
  HW Track Controller has the same startup (it loads territories and programs) but
  reports no readiness today.

## Supersedes

None. A new signal.
