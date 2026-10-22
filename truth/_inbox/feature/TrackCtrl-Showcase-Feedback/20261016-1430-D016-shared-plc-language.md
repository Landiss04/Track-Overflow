**Target:** truth/decisions/D016-shared-plc-language.md
**Action:** create
**Proposed by:** GitHub Copilot on feature/TrackCtrl-Showcase-Feedback
**Provenance:** asserted by Braden 2026-10-06; grammar from `TrackCtrlSW/track_ctrl/plc.py` on `Track-Ctrl-SW` (`b39fa06`); speed entering the program as bits asserted by Braden 2026-10-16

Note for the promoter: this replaces the pending proposal
`truth/_inbox/feature/TrackCtrl-Module-Implementation/20261007-0110-D016-shared-plc-language.md`.
The decision is unchanged. Only the last consequence changed: speed now enters
the program, as bits, because the program caps it (D019, proposed alongside).
Promote this one and deny that one.

Harry, who wrote the grammar, has not confirmed this. Do not promote before he
has. The hardware variant's I/O names now differ from the software variant's
(`CTCSW_n`, `CTCREV_n`, `SPD_n_b` and `CMD_n_b` here; `MAINT` there), so one
program file no longer runs on both. That is a REQ-INTF-009 question for Braden
and Harry, not a change to the language.

---

# D016-shared-plc-language

**Status:** current
**Owner:** Braden
**Provenance:** asserted by Braden 2026-10-06; grammar from `TrackCtrlSW/track_ctrl/plc.py` on `Track-Ctrl-SW` (`b39fa06`); speed entering the program as bits asserted by Braden 2026-10-16
**Aliases:** PLC language, wayside PLC grammar, .plc file format
**Last updated:** 2026-10-16

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
- A number enters a program only bit by bit. The hardware variant feeds in the
  CTC Office's speed for each block as five bits and takes the speed to send
  out as five bits, so that the program can cap it (D019). Authority does not
  enter: the program decides per block whether the CTC Office's authority is
  passed on.
