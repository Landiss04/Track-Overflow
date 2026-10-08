**Target:** truth/ui/component-kit.md
**Action:** create
**Proposed by:** GitHub Copilot on feature/TrackCtrl-UI-Implementation
**Provenance:** `ui/README.md` and `documents/SCALING_GUIDE.md` on `development` (`84336f9`)
**Edited:** 2026-10-01 by GitHub Copilot at Braden's request. **This proposal has changed
since it was first written — re-read it rather than relying on an earlier review.** The
Definition is unchanged. Changed: the kit now also supplies the module window and the
aspect lock, so a `## Window and scaling` section was added; the `## Pending` collision
example was corrected (`ModuleHeader` was renamed `TrackCtrlHeader` and the local `Panel`
was dropped for the shared one, so `DataTable` is now the only remaining collision), and a
practised naming convention is now recorded there. Original wording is in git history.

Note for the promoter: this is proposed as a new shard under `truth/ui/` because
`truth/ui/style-guide.md` governs visual rules and `truth/conventions/files-and-paths.md`
governs Python layout, and neither states where shared QML components live or how a
module imports them. If you would rather fold it into `files-and-paths.md` under a new
`## Shared QML component kit` heading, the body below transfers unchanged. Promoting it
as a new shard requires a row in `truth/INDEX.md`.

Ordering note: `## Window and scaling` cites `decisions/D004-shared-window-scaling.md`,
which is **not yet on `truth`** — it is still pending as
`truth/_inbox/CTC_UI_Implementation/20260930-1147-shared-window-scaling.md` (Landis) and
appears in neither `truth/decisions/` nor `truth/_promotions.md`. This entry deliberately
cites D004 rather than restating the aspect ratio and minimum size, so promote D004 first
or the citation dangles.

---

# component-kit

**Status:** current
**Owner:** unassigned
**Provenance:** `ui/README.md` and `documents/SCALING_GUIDE.md` on `development`
(`84336f9`); token provider and `theme` context property per `truth/ui/style-guide.md` §9
**Aliases:** shared UI kit, shared QML components, ui/ folder, component library
**Last updated:** 2026-10-01

## Definition

All reusable QML components live in a single `ui/` directory at the repository root.
Module-specific screens stay in their own module folders and consume the shared kit by
relative directory import. A module does not restyle a shared control locally.

## Notes

- Import paths are relative to the QML file containing the import, not to the working
  directory:

  | Importing file | Import |
  | --- | --- |
  | `<module>/ui/View.qml` | `import "../../ui"` |
  | `<module>/Main.qml` | `import "../ui"` |
  | `Main.qml` at the repository root | `import "ui"` |

- The token provider is `ui/theme.py`, in the same directory. The host exposes it as the
  `theme` context property before loading any QML, per style guide §9:

  ```python
  from ui.theme import build_theme
  engine.rootContext().setContextProperty("theme", build_theme())
  ```

  This requires the repository root on the host's `sys.path`. `ui/` carries no
  `__init__.py`; it resolves as a namespace package.
- `build_theme()` resolves the style guide's font fallback stacks against the installed
  families, so it must be called after the `QGuiApplication` exists.
- `ui/gallery/` renders every component in every variant and state. It is not a
  component, so it sits in a subfolder that `import "../../ui"` does not pick up.
- Host-facing signals request a change; the host updates the bound state. A component
  does not mutate its own bound state in response to user input.

## Window and scaling

The kit also supplies the module window, so every module resizes identically:

- `ui/ScaledWindow.qml` is the application window. Children declared inside it are placed
  on its fixed reference canvas.
- `ui/aspect_lock.py` constrains an interactive resize on Windows. The host calls
  `install_window_scaling(window)` after the QML loads and keeps the returned object
  alive for the life of the window; off Windows it returns `None` and the canvas
  letterboxes.

The resizing behaviour itself is a decision, not a kit fact: see
`decisions/D004-shared-window-scaling.md` for the aspect ratio, the minimum size and the
rule that no module implements its own window sizing, and `documents/SCALING_GUIDE.md`
for the reference-canvas dimensions and the prohibition on binding child geometry to the
live window size. Neither is restated here.

## Pending

Owner: unassigned — needs a decision, not an inference.

A module-local component directory and the shared kit are both plain directory imports,
so a module-local component that reuses a shared component's name collides with it and
must be disambiguated with an aliased import (`import "../../ui" as Shared`). Whether
module-local names are required to be distinct from shared ones, or whether the aliased
import is the standard form, is not stated anywhere.

Practice so far points at a module prefix: CTC Office keeps `CtcHeader` and the Track
Controller keeps `TrackCtrlHeader`, both module-local because they carry module-specific
header controls the shared `ModuleHeader` has no slot for. The one live collision left is
`DataTable`, defined by both `ui/` and `TrackCtrlHw/ui/components/`.
