**Target:** truth/decisions/D019-wayside-runs-only-its-program.md
**Action:** create
**Proposed by:** GitHub Copilot on feature/TrackCtrl-Showcase-Feedback
**Provenance:** asserted by Braden 2026-10-16 (changes required after the Track Controller showcase)

Note for the promoter: D019 was not used on any pushed branch on 2026-10-16.
Renumber it if it has been taken since.

This conflicts with the pending proposal
`truth/_inbox/Track-Ctrl-SW/20261014-0950-track-controller-vital-restrictions.md`
on `Track-Ctrl-SW`, which gives the Track Controller a vital layer. The
`## Conflict` section records both. Do not promote either until it is resolved.

---

# D019-wayside-runs-only-its-program

**Status:** current
**Owner:** Braden
**Provenance:** asserted by Braden 2026-10-16 (changes required after the Track Controller showcase)
**Aliases:** no vital layer, nothing above the program, the OS only houses the PLC, speed capped in the PLC
**Last updated:** 2026-10-16

## Context

Both Track Controller variants were built with a vital layer: code outside the
PLC program that checked the program's outputs after every scan and made them
more restrictive (closed blocks, speed limits, switch locking, crossings).
After the showcase, Braden reported that a wayside controller does not work
that way: its operating system only houses the PLC.

## Decision

A wayside controller's operating system houses its PLC program and makes no
decisions without it. There is no vital layer.

- Every protection is written in the PLC program: separation, closed blocks,
  switch locking and correspondence, crossings, and capping the speed at the
  block's limit.
- What the program outputs goes to the track as it is.
- What the CTC Office sends (closed blocks, switch commands, suggested speed and
  authority) reaches the program as inputs, and the program decides what to do
  with it. That includes a switch command in maintenance mode.

## Consequences

- Programs get long. Speed is a number and the language has only bits
  ([D016](D016-shared-plc-language.md)), so capping it takes several
  statements per block. That is accepted.
- Every precedence rule the Track Controller must honour, such as
  `arbitration/maintenance-closure-lock.md` and
  `arbitration/no-switch-under-train.md`, is honoured by the program it runs,
  so it binds the program's author.
- Outputs are held at their fail-safe values only while no program is running.

## Conflict

- **No vital layer** (this entry): asserted by Braden 2026-10-16.
- **A vital layer that can only make an output more restrictive**, applying a
  list of restrictions after the program: pending proposal
  `arbitration/track-controller-vital-restrictions.md` on `Track-Ctrl-SW`
  (`20261014-0950-track-controller-vital-restrictions.md`), asserted by the
  user in the Track Controller UI chat 2026-10-14.

**Resolution owner:** Braden
