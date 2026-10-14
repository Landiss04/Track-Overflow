**Target:** truth/arbitration/nothing-sent-until-track-controller-ready.md
**Action:** create
**Proposed by:** Claude on ctc-deployment
**Provenance:** asserted by Landis 2026-10-14 (the wayside controllers are vital, so the CTC Office sends the Track Controller no inputs unless its ready signal is high; ready goes high once a PLC program is loaded)

---

# nothing-sent-until-track-controller-ready

**Status:** current
**Owner:** CTC Office
**Provenance:** asserted by Landis 2026-10-14 (the wayside controllers are vital, so the CTC Office sends the Track Controller no inputs unless its ready signal is high; ready goes high once a PLC program is loaded)
**Aliases:** track controller ready gate, ready gate, wait for ready, no output until ready
**Last updated:** 2026-10-14

## Definition

The CTC Office sends the Track Controller nothing while the Track Controller's ready
signal is low: no suggested speed or suggested authority, no closed blocks and no
switch commands. It sends again from the first step on which ready is high, and stops
again whenever ready goes low.

The ready signal is an input to the CTC Office from the Track Controller. It goes high
once a PLC program is loaded on the wayside controllers (see
`signals/track-controller-ready`, proposed on `Track-Ctrl-SW`). Until the CTC Office has
received it, it counts as low.

## Rationale

The wayside controllers are vital. Without a PLC program loaded they cannot act on any
input safely, so none is sent to them.

## Notes

- Applies to everything the CTC Office sends the Track Controller:
  [suggested-speed](../signals/suggested-speed.md),
  [suggested-authority](../signals/suggested-authority.md),
  [closed-blocks](../signals/closed-blocks.md) and
  [switch-command](../signals/switch-command.md).
- Whether the CTC Office also refuses to dispatch while the Track Controller is not
  ready is not decided here. `signals/track-controller-ready`, proposed on
  `Track-Ctrl-SW`, says it dispatches no train.
- Whether one ready covers both lines, when the HW and SW Track Controllers each run
  one, is not decided here.
