**Target:** truth/decisions/D016-shared-plc-language.md
**Action:** create
**Proposed by:** GitHub Copilot on feature/TrackCtrl-Module-Implementation
**Provenance:** asserted by Braden 2026-10-06; grammar from `TrackCtrlSW/track_ctrl/plc.py` on `Track-Ctrl-SW` (`b39fa06`)

Note for the promoter: Harry, who wrote the grammar, has not confirmed this. Do
not promote before he has.

---

# D016-shared-plc-language

**Status:** current
**Owner:** Braden
**Provenance:** asserted by Braden 2026-10-06; grammar from `TrackCtrlSW/track_ctrl/plc.py` on `Track-Ctrl-SW` (`b39fa06`)
**Aliases:** PLC language, wayside PLC grammar, .plc file format
**Last updated:** 2026-10-06

## Context

Both Track Controller variants run a Boolean PLC program written by the
programmer (REQ-FUNC-050, REQ-FUNC-051). The brief requires the program to be
specifiable separately from the controller's implementation, and the
implementation to be diverse; REQ-INTF-009 requires the two variants to expose
equivalent interfaces. The software variant had already defined a language.

## Decision

The hardware and software Track Controllers run one PLC language, the one the
software variant defined:

- `VAR_IN` and `VAR_OUT` declarations, with range shorthand such as `OCC_1..20`.
- One assignment per line, `NAME := expression`, run top to bottom once per scan.
- `NOT`, `AND`, `XOR` and `OR`, binding in that order, with parentheses and the
  constants `0` and `1`. Every value is one bit.
- `//` comments.

Each variant implements the language separately; they share the file format,
not code.

## Consequences

- One program file format serves both variants.
- The names a program reads and writes, its I/O, depend on each variant's
  interface; they are not fixed by this entry.
- Speed and authority are numbers and do not enter the program. The hardware
  variant decides per block whether the CTC Office's suggestion is passed on.
