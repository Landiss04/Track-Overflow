# CTC Office UI (skeleton)

PySide6 + QML front-end for the CTC Office dispatcher console. This is a
**blank UI with no backend**: every panel shows its empty state, and
actions emit QML signals that nothing handles yet.

QML owns all visuals; Python owns startup and the design tokens. The
structure follows the Train Model UI on the `Train-Model-UI-experimental`
branch so the modules share one component vocabulary.

## Run

From the `CTC-Office` directory:

```bash
pip install -r ../requirements.txt
python -m ctc_ui
```

## What is interactive

With no backend, only window-level UI state works:

- The **Operating mode** toggle switches the right-hand column between the
  Automatic, Manual, and Maintenance views.
- **Train occupancy** opens the occupancy window. "Keep open at
  bottom" or the minimize button docks it over the track view.
  Escape, the close button, or clicking the scrim closes it.
- **Test harness** (header) opens a popup for forcing inputs and reading
  outputs, modeled on the Train Model test harness. No IO is declared yet,
  so both tables are empty and Reset / Send stay disabled until inputs
  exist. Escape, the close button, or clicking the scrim closes it.
- Dispatch, set authority, send to track controller, and close block
  enable once their selects have a value. The selects are empty, so these
  stay disabled until options are bound. Close block requires a
  confirmation step (style guide 7).

## Where things go

| Area | Hook |
| --- | --- |
| Track map | `panels/TrackViewPanel.qml` → `mapCanvas`. Set `mapAvailable` to enable zoom and fit. The legend goes below the canvas. |
| Selected train | `SelectedTrainPanel.trainId`. A non-empty ID shows the detail layout. |
| Tables | `DataTable.rows`: an array of objects keyed by each column's `key`. |
| Selects | `model` on each `SelectField`, via the panel's `*Options` properties. |
| Test harness | `TestHarnessWindow.inputs` / `.outputs`: arrays of `{ name, kind, value, unit }`, where `kind` is `bool`, `int`, `float`, or `string`. Handle `inputEdited`, `sendInputsRequested`, and `resetInputsRequested`, and set `connected` once a backend is attached. |
| Header | `CtcHeader.clock`, `.speedLabel` (e.g. `10× speed`), `.operatorName`. |

## Layout

```
__main__.py             entry point: builds theme, loads QML
ui/Main.qml             window, fixed 1440×900 canvas, mode + window state
ui/views/*.qml          Automatic / Manual / Maintenance right-hand columns
ui/panels/*.qml         track view, dispatch, schedule, throughput,
                        closures, switch, close block, occupancy window/dock,
                        test harness
ui/components/*.qml     CTC-only building blocks (see below)
```

### Shared components

Buttons, fields, badges, readouts, tables and the theme tokens come from
the repository-level [`ui/`](../../ui/README.md) folder shared by every
module. `__main__.py` puts the repository root on `sys.path` to import
`ui.theme`. QML files import the folder relatively: `import
"../../../../ui"` from `ui/panels/`, `ui/views/` and `ui/components/`.
Do not copy shared components into this module; change them in `ui/`.

`ui/components/` holds only what the shared library does not provide:

| Component | Why it is CTC-only |
| --- | --- |
| `ModeCallout` | Info and warning variants with a side bar; shared `Callout` is info-only, and matching it would restyle other modules |
| `CtcHeader` | Window buttons, mode toggle and clock; shared `ModuleHeader` has navigation tabs instead |

#### Moved to the shared library

These started here and were promoted to `ui/` on 2026-09-30 so other
modules can use them. They are catalogued in the shared
[`ui/README.md`](../../ui/README.md) and shown in `ui/gallery/`.

| Component | Was | Now |
| --- | --- | --- |
| `Panel` | `ctc_ui/ui/components/Panel.qml` | `ui/Panel.qml` |
| `EmptyState` | `ctc_ui/ui/components/EmptyState.qml` | `ui/EmptyState.qml` |
| `FormField` | `ctc_ui/ui/components/FormField.qml` | `ui/FormField.qml` |
| `LabeledDivider` | `ctc_ui/ui/components/LabeledDivider.qml` | `ui/LabeledDivider.qml` |

## Checks

```bash
python -m flake8 --max-line-length=79 --max-doc-length=72 ctc_ui
python -m mypy --disallow-untyped-defs ctc_ui
pyside6-qmllint -I ctc_ui/ui -I ctc_ui/ui/components -I ctc_ui/ui/panels \
    -I ../ui $(find ctc_ui/ui -name '*.qml')
```

flake8 and mypy are clean. qmllint's only remaining warnings are
`[unqualified]` access to the `theme` context property. That is inherent to
the context-property pattern shared with the Train Model UI.

## Design notes

1. **No shadows.** QML has no cheap box-shadow, so `--shadow-1` is carried
   by `--border`, as in the Train Model UI.
2. **No dashed borders.** Empty states use a solid `--border-strong` frame.
3. **Scrim colour.** The style guide has no scrim token, so `Main.qml`
   derives it from `theme.text_primary` at 40 % alpha.
4. **The occupancy window is not a `Popup`.** A Popup reparents to the
   window overlay and would escape the canvas scale transform.
5. **No placeholders on text fields.** The shared `ValueField` does not
   expose `placeholderText` or `inputMask`, so the search hint and the
   `HH:MM` arrival-time mask were dropped when migrating to it.
6. **Window sizing is shared.** `ui/Main.qml` is a `ScaledWindow` and
   `__main__.py` installs `ui.aspect_lock.install_window_scaling`. The CTC
   used to correct the window size from a QML timer after each resize,
   which fought the window manager and snapped the window back to its large
   size; that code is gone. See `documents/SCALING_GUIDE.md`.
