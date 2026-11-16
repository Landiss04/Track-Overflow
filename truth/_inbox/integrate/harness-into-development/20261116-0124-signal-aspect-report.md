**Target:** truth/signals/signal-aspect-report.md
**Action:** create
**Proposed by:** Claude Code on integrate/harness-into-development
**Provenance:** `documents/signal-aspects-and-line-swap-plan-2026-11-13.md` Phase 0b item 3 (Kevin Schillinger 2026-11-12/13); display decision asserted by Landis 2026-11-16

---

# signal-aspect-report

**Status:** current
**Owner:** Track Controller
**Provenance:** `documents/signal-aspects-and-line-swap-plan-2026-11-13.md` Phase 0b item 3 and its review (Kevin Schillinger 2026-11-12/13); shown on the CTC map, asserted by Landis 2026-11-16
**Aliases:** signal aspects to the CTC, `signals`, light states to the CTC, wayside signal report
**Last updated:** 2026-11-16

## Definition

The aspect of each wayside signal light, sent from the Track Controller to the CTC
Office as a list of `{line, signal_id, aspect}`.

- `signal_id` is the ID of the light's switch (the block the switch is listed on), not
  the block the light stands on.
- `aspect` is one of `RED`, `YELLOW`, `GREEN` and `SUPER_GREEN`, all caps.
- The value is the lamp the Track Model reports lit. A light with no read-back is not
  reported.
- A repeated identical report is accepted; a contradictory one is rejected.

## Notes

- The producer is the Track Controller module, not a variant.
- The CTC Office uses it for display only:
  [D044](../decisions/D044-ctc-shows-signal-aspects.md).
- The aspect a train's driver sees comes separately from the Track Model:
  [signal-aspect-ahead](signal-aspect-ahead.md).
