**Target:** truth/ui/component-kit.md
**Action:** create
**Proposed by:** GitHub Copilot on feature/TrackCtrl-UI-Implementation
**Provenance:** `ui/README.md` on `development` (`53586da`)

Note for the promoter: this is proposed as a new shard under `truth/ui/` because
`truth/ui/style-guide.md` governs visual rules and `truth/conventions/files-and-paths.md`
governs Python layout, and neither states where shared QML components live or how a
module imports them. If you would rather fold it into `files-and-paths.md` under a new
`## Shared QML component kit` heading, the body below transfers unchanged. Promoting it
as a new shard requires a row in `truth/INDEX.md`.

---

# component-kit

**Status:** current
**Owner:** unassigned
**Provenance:** `ui/README.md` on `development` (`53586da`); token provider and `theme`
context property per `truth/ui/style-guide.md` §9
**Aliases:** shared UI kit, shared QML components, ui/ folder, component library
**Last updated:** 2026-09-29

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

## Pending

Owner: unassigned — needs a decision, not an inference.

A module-local component directory and the shared kit are both plain directory imports,
so a module-local component that reuses a shared component's name collides with it and
must be disambiguated with an aliased import (`import "../../ui" as Shared`). Whether
module-local names are required to be distinct from shared ones, or whether the aliased
import is the standard form, is not stated anywhere. Encountered on
`feature/TrackCtrl-UI-Implementation`, where `TrackCtrlHw/ui/components/` defines
`DataTable` and `ModuleHeader` alongside the shared kit's own.
