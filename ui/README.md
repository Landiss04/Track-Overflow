# Shared QML components

All reusable QML components are in this folder, at the repository root
alongside `truth/`. Module-specific screens stay in their own module folders.

## Import helper

QML directory imports are relative to the **QML file containing the import**,
not the terminal's working directory.

| Your QML file | Import for this folder |
| --- | --- |
| `TrainModel/ui/MainView.qml` or `<module>/ui/View.qml` | `import "../../ui"` |
| `<module>/Main.qml` | `import "../ui"` |
| `Main.qml` at the repository root | `import "ui"` |

For example, from `TrainModel/ui/MainView.qml`:

```qml
import QtQuick
import "../../ui" as Shared

Shared.AppButton {
    text: "Send"
    onClicked: backend.sendInputs()
}
```

The host supplies `backend` with the appropriate slot. An unaliased import
(`import "../../ui"`) also works; use `AppButton` directly in that case.
Components can reference one another without extra paths because they live
in the same directory. No absolute paths or extra QML import-path setup are
needed for these relative imports.

## Theme setup

The host must expose a `theme` context property before loading its QML.
The existing token provider is `TrainModel/train_model/theme.py`; the Train
Model entry point already configures it. From Python with the repository root
on its import path, after creating a `QGuiApplication`:

```python
from TrainModel.train_model.theme import build_theme

engine.rootContext().setContextProperty("theme", build_theme())
```

## Component catalog

| Component | Host-facing action / data |
| --- | --- |
| `AppButton` | Native `clicked()`; primary, secondary, ghost, danger, success |
| `ValueField` | `label`, `kind`, `text`; `committed(value)` sends a number for int/float, a string otherwise; invalid numbers never commit |
| `SelectField` | `model`, `textRole`, `valueRole`, `currentIndex`; `committed(value)` sends the selected model value |
| `SegmentedToggle`, `NavRail` | `activated(index)`; bind `currentIndex` to host state |
| `ModuleHeader` | `navigationActivated(index)`; bind navigation index, mode, clock and fault state |
| `SafetyButton` | `confirmed()` after confirmation; bind `applied` to acknowledged state; `confirmationRequired: false` is reserved for the Train Controller emergency brake |
| `SignalRow` | `edited(value)` forwards typed edits; bind `value` to host state |
| `DataTable` | `columns` (`key`, `label`, optional `numeric`, `mono`, `width`) and `rows`; `rowActivated(index, row)`; bind `currentIndex` to host state |
| `TrackBlock` | Read-only `blockId` and `occupancy` (`free`, `occupied`, `closed`, `failure`, `maintenance`) |
| `StatusBadge`, `TelemetryReadout`, `UsageBar` | Read-only presentation properties |
| `Card`, `Callout`, `FieldLabel`, `HelperText`, `KeyValueRow`, `MonoText`, `TableHeader` | Layout and text components |

Selection and toggle signals request changes; the host updates the bound
state. Programmatic updates do not emit user commands. Numeric input emits
numbers; string IDs preserve leading zeros. Read-only indicators need only
property bindings, not command handlers.

## Guides and checks

- [Normative UI style guide](../truth/ui/style-guide.md)
- [HTML review preview](../truth/ui/ui-style-guide-preview.html)
- [Truth index](../truth/INDEX.md)
- [Train Model integration and setup](../TrainModel/README.md)

Run the existing component and application checks from the repository root:

```bash
QT_QPA_PLATFORM=offscreen TrainModel/.venv/bin/python TrainModel/tests/test_ui_components.py
```
