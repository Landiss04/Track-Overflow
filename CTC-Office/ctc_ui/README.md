# CTC Office UI (skeleton)

PySide6 + QML front-end for the CTC Office dispatcher console, converted
from the HTML mockups in `../CTC-pages/`. This is a **blank UI with no
backend**: every panel shows its empty state, and actions emit QML signals
that nothing handles yet.

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
  Automatic, Manual, and Maintenance views (mockup pages 1, 2, and 5).
- **Train occupancy** opens the occupancy window (page 3). "Keep open at
  bottom" or the minimize button docks it over the track view (page 4).
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
| Selected train | `SelectedTrainPanel.trainId`. A non-empty ID shows the detail layout (page 4). |
| Tables | `DataTable.rows`: an array of objects keyed by each column's `key`. |
| Selects | `model` on each `SelectField`, via the panel's `*Options` properties. |
| Test harness | `TestHarnessWindow.inputs` / `.outputs`: arrays of `{ name, kind, value, unit }`, where `kind` is `bool`, `int`, `float`, or `string`. Handle `inputEdited`, `sendInputsRequested`, and `resetInputsRequested`, and set `connected` once a backend is attached. |
| Header | `ModuleHeader.clock`, `.speedLabel` (e.g. `10× speed`, page 6), `.operatorName`. |

## Layout

```
__main__.py             entry point: builds theme, loads QML
theme.py                build_theme(): style guide tokens (light theme)
ui/Main.qml             window, fixed 1440×900 canvas, mode + window state
ui/views/*.qml          Automatic / Manual / Maintenance right-hand columns
ui/panels/*.qml         track view, dispatch, schedule, throughput,
                        closures, switch, close block, occupancy window/dock,
                        test harness
ui/components/*.qml     buttons, badges, fields, readouts, tables, …
```

`AppButton`, `FieldLabel`, `HelperText`, `MonoText`, `StatusBadge`,
`SegmentedToggle`, `SignalRow`, `TableHeader`, `TelemetryReadout` and
`ValueField` come from the Train Model branch. Changes made here:

- `StatusBadge`: the dot size is now a token (`badge_dot`).
- `ValueField`: the placeholder uses `text_muted`.
- `SignalRow`: added `pragma ComponentBehavior: Bound` for qmllint.
- `SegmentedToggle`: added keyboard focus, activation, and a focus ring
  (style guide 8), plus `currentIndex: -1` for "nothing selected".

## Checks

```bash
python -m flake8 --max-line-length=79 --max-doc-length=72 ctc_ui
python -m mypy --disallow-untyped-defs ctc_ui
pyside6-qmllint -I ctc_ui/ui -I ctc_ui/ui/components -I ctc_ui/ui/panels \
    $(find ctc_ui/ui -name '*.qml')
```

flake8 and mypy are clean. qmllint's only remaining warnings are
`[unqualified]` access to the `theme` context property. That is inherent to
the context-property pattern shared with the Train Model UI.

## Design notes

1. **No shadows.** QML has no cheap box-shadow, so `--shadow-1` is carried
   by `--border`, as in the Train Model UI.
2. **No dashed borders.** Empty states use a solid `--border-strong` frame.
3. **Scrim colour.** The style guide has no scrim token; `theme.SCRIM` is
   `--text-primary` at 40 % alpha.
4. **The occupancy window is not a `Popup`.** A Popup reparents to the
   window overlay and would escape the canvas scale transform.
