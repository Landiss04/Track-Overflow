**Target:** truth/decisions/D034-authoritative-green-plc-programs.md
**Action:** create
**Proposed by:** Integration on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-22: "Our branch's (PR #43)"; "Three that actually went into the waysides and examples/ has ones that give warnings and errors"

---

# D034-authoritative-green-plc-programs

**Status:** current
**Owner:** Braden (Track Controller HW)
**Provenance:** asserted by Kevin Schillinger 2026-10-22: "Our branch's (PR #43)"; "Three that actually went into the waysides and examples/ has ones that give warnings and errors"
**Aliases:** Braden's Green PLC programs, green_wayside_1..3.plc, PR #43 PLC programs, PLC examples, errors.plc, warnings.plc
**Last updated:** 2026-10-22

## Context

Two versions of Braden's Green wayside PLC programs existed: older copies on
`development`, and the copies merged from PR #43. The PLC directory also holds
`examples/`.

## Decision

- Braden's authoritative Green wayside programs are
  `TrackCtrlHw/data/plc/green_wayside_1.plc`, `green_wayside_2.plc` and
  `green_wayside_3.plc` as merged from PR #43. Those copies include the
  no-vital-layer, speed-bit and CTC maintenance changes. The older copies on
  `development` are not authoritative.
- These three are the programs that went into the waysides.
- `TrackCtrlHw/data/plc/examples/` (`errors.plc`, `warnings.plc`) holds
  demonstration programs that show diagnostics: one gives warnings and one
  gives errors. They are not wayside programs.

## Consequences

- Where the two versions of a Green wayside program differ, the PR #43 copy
  holds.
- The `examples/` programs are not loaded into a wayside.
