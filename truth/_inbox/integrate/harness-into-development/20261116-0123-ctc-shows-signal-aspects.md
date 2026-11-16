**Target:** truth/decisions/D044-ctc-shows-signal-aspects.md
**Action:** create
**Proposed by:** Claude Code on integrate/harness-into-development
**Provenance:** asserted by Landis 2026-11-16 (design review feedback); `documents/signal-aspects-and-line-swap-plan-2026-11-13.md` R1 (Kevin Schillinger)

---

# D044-ctc-shows-signal-aspects

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-11-16 (design review feedback: the CTC needs to show the current light states on the track; the throughput metrics may be reduced to the per-line numbers); requirement R1 of `documents/signal-aspects-and-line-swap-plan-2026-11-13.md` (Kevin Schillinger 2026-11-13)
**Aliases:** signal markers, light states on the CTC map, CTC signal display, signal aspects to the CTC
**Last updated:** 2026-11-16

## Context

The design review found that the CTC Office did not show the state of the wayside
signal lights. The Track Controllers already reported each light's aspect, but it did
not reach the CTC Office. REQ-INTF-002.4 asks for the state of all signals on the CTC
map view.

## Decision

- The CTC Office shows the current aspect of every wayside signal light on its track
  map, drawn at the block where the light stands, and lists them per line.
- The aspect is shown by shape as well as colour, so it reads without colour.
- A light with no report yet is shown as unreported, not hidden.
- The aspects are for display only: they never change an authority or a suggested
  speed.
- The throughput metrics show tickets per hour per line only; the 12-hour history and
  the per-line table are removed.

## Consequences

- The Track Controller reports aspects to the CTC Office:
  [signal-aspect-report](../signals/signal-aspect-report.md).
- The CTC test UI's inputs include signal aspects
  ([D025](D025-ctc-test-ui-boundary.md)).
- The aspect colours need style-guide tokens.
