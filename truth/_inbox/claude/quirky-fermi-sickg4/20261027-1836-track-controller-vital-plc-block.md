**Target:** truth/decisions/track-controller-vital-plc-block.md
**Action:** create
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** `documents/module-owner-review-braden.md` (branch `feature/TrackCtrl-HW-vital`, `a5bd465`), SW-1 and HW-1: decision by Braden Bosilovich and Harry Tye 2026-10-26

---

# track-controller-vital-plc-block

**Status:** current
**Owner:** Track Controller
**Provenance:** Braden Bosilovich and Harry Tye 2026-10-26 (module owner review SW-1, HW-1), `documents/module-owner-review-braden.md` (branch `feature/TrackCtrl-HW-vital`, `a5bd465`)
**Aliases:** vital block, vital PLC code, vital layer, vital supervision, OUT_ outputs
**Last updated:** 2026-10-27

## Context

The waysides' safety lived only in each user's PLC program (proposed D019, "no
vital layer"). A program could then grant anything. Both variant owners agreed to
put a fixed safety layer after it.

## Decision

- Both Track Controller variants append a generated, read-only vital PLC block after
  the user's program, on every scan.
- It is generated per wayside from that wayside's own territory, reads the program's
  outputs and writes the outputs the wayside actually drives (`OUT_*`).
- It can only restrict, never grant: no authority into a closed block, none while a
  block a train there could move into is occupied, speed capped at the block's limit
  and 0 without authority, a switch locked under a train, a signal red unless exactly
  one aspect is lit, a crossing active for a train on or beside it.
- The two variants' vital blocks may differ in detail; what each enforces is the
  variant's own.

## Consequences

- Supersedes the pending proposal D019 ("no vital layer",
  `20261016-1430-D019-wayside-runs-only-its-program.md` on
  `feature/TrackCtrl-Showcase-Feedback`, and
  `20261021-2237-track-controller-plc-only-both-variants.md` on
  `claude/quirky-fermi-sickg4`), which should be denied.
- A HW vital channel disagreement is a latched channel fault.
