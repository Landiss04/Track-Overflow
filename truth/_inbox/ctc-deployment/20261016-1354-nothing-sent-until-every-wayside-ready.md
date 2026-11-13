**Target:** truth/arbitration/nothing-sent-until-track-controller-ready.md
**Action:** create
**Proposed by:** Claude on ctc-deployment
**Provenance:** asserted by Landis 2026-10-14 (the wayside controllers are vital, so the CTC Office sends the Track Controller no inputs unless its ready signal is high; ready goes high once a PLC program is loaded); ready per line, and no dispatch while not ready, asserted by Landis 2026-10-15; ready reported per wayside, in each wayside's report to the CTC Office, asserted by Landis 2026-10-16 from the Track Controller's `CtcReport`

---

# nothing-sent-until-track-controller-ready

**Status:** current
**Owner:** CTC Office
**Provenance:** asserted by Landis 2026-10-14 (the wayside controllers are vital, so the CTC Office sends the Track Controller no inputs unless its ready signal is high; ready goes high once a PLC program is loaded); ready per line, and no dispatch while not ready, asserted by Landis 2026-10-15; ready reported per wayside, in each wayside's report to the CTC Office, asserted by Landis 2026-10-16 from the Track Controller's `CtcReport`
**Aliases:** track controller ready gate, ready gate, wait for ready, no output until ready, no dispatch until ready, ready per line, wayside ready
**Last updated:** 2026-10-16

## Definition

Each wayside controller reports to the CTC Office whether it is ready (a PLC program on
its territory) and, when it is not, why: the `ready` and `reason` of its report to the
CTC Office, with its wayside ID and line.

A line is ready when a wayside on it has reported and every wayside on it is ready.
While a line is not ready, the CTC Office:

- sends nothing for that line: no suggested speed or suggested authority, no closed
  blocks and no switch commands; and
- dispatches no train on that line. The dispatcher's dispatch is refused, and
  automatic dispatch waits.

It sends again, and dispatches again, from the first step on which the line is ready,
and stops again whenever the line stops being ready. The CTC Office shows the
dispatcher each wayside that is not ready, and why.

## Rationale

The wayside controllers are vital. The track is only safe with every wayside on it
running its PLC program, so nothing is sent to a line, and no train is set in motion on
it, until every wayside on it is ready.

## Notes

- Applies to everything the CTC Office sends the Track Controller:
  [suggested-speed](../signals/suggested-speed.md),
  [suggested-authority](../signals/suggested-authority.md),
  [closed-blocks](../signals/closed-blocks.md) and
  [switch-command](../signals/switch-command.md).
- One line being ready does not wait on the other.
- The signal itself is the Track Controller's: `signals/track-controller-ready`,
  proposed on `Track-Ctrl-SW`.
