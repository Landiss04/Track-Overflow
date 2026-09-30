**Target:** truth/decisions/D004-shared-window-scaling.md
**Action:** create
**Proposed by:** Claude on CTC_UI_Implementation
**Provenance:** asserted by Landis 2026-09-27 (minimum size) and 2026-09-30 (centralized resizing)

---

# D004-shared-window-scaling

**Status:** current
**Owner:** Landis
**Provenance:** asserted by Landis 2026-09-27 (minimum size) and 2026-09-30 (centralized resizing)
**Aliases:** window scaling, window resizing, aspect lock, minimum window size, scaled window
**Last updated:** 2026-09-30

## Context

Each module UI implemented its own window resizing. Two approaches diverged:
one corrected the window size from a QML timer after each resize, which
fought the window manager and snapped the window back to its previous size;
the other constrained the drag natively before Windows applied it. Modules
written by different people resized differently.

## Decision

- Every module UI uses one centralized window-resizing implementation in
  the repository-level `ui/` folder. No module implements its own window
  sizing or scaling.
- Module windows keep a 16:10 aspect ratio, with a minimum size of
  720 x 450 that the user cannot shrink below.
- A window already at its minimum size does not shrink when the user drags
  inward; it stays at the minimum. Dragging outward still enlarges it.

## Consequences

- Module windows share the same reference canvas, minimum size and resize
  behavior, whoever writes the module.
- A change to the shared resizing implementation changes every module and
  is reviewed with each module's owner.
