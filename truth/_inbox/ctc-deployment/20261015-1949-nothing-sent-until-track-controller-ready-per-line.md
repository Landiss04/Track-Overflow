**Target:** truth/arbitration/nothing-sent-until-track-controller-ready.md
**Action:** create
**Proposed by:** Claude on ctc-deployment
**Provenance:** asserted by Landis 2026-10-14 (the wayside controllers are vital, so the CTC Office sends the Track Controller no inputs unless its ready signal is high; ready goes high once a PLC program is loaded); ready per line, and no dispatch while not ready, asserted by Landis 2026-10-15

---

# nothing-sent-until-track-controller-ready

**Status:** current
**Owner:** CTC Office
**Provenance:** asserted by Landis 2026-10-14 (the wayside controllers are vital, so the CTC Office sends the Track Controller no inputs unless its ready signal is high; ready goes high once a PLC program is loaded); ready per line, and no dispatch while not ready, asserted by Landis 2026-10-15
**Aliases:** track controller ready gate, ready gate, wait for ready, no output until ready, no dispatch until ready, ready per line
**Last updated:** 2026-10-15

## Definition

The Track Controller reports ready per line. While a line's Track Controller is not
ready, the CTC Office:

- sends it nothing for that line: no suggested speed or suggested authority, no closed
  blocks and no switch commands; and
- dispatches no train on that line. The dispatcher's dispatch is refused, and
  automatic dispatch waits.

It sends again, and dispatches again, from the first step on which the line is ready,
and stops again whenever the line stops being ready. A line counts as not ready until
the CTC Office has received its ready signal.

A line's ready signal goes high once a PLC program is loaded on its wayside controllers
(see `signals/track-controller-ready`, proposed on `Track-Ctrl-SW`).

## Rationale

The wayside controllers are vital. Without a PLC program loaded they cannot act on any
input safely, so none is sent to them, and no train is set in motion on their line.

## Notes

- Applies to everything the CTC Office sends the Track Controller:
  [suggested-speed](../signals/suggested-speed.md),
  [suggested-authority](../signals/suggested-authority.md),
  [closed-blocks](../signals/closed-blocks.md) and
  [switch-command](../signals/switch-command.md).
- One line being ready does not wait on the other.
