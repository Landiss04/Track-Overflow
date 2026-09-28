# Train Model UI

PySide6 + QML preview for the operational view and test harness. Python owns
observable state; QML owns presentation. The physics backend is not implemented.
The harness updates preview pass-through values and emits a complete input
payload for a backend receiver.

## Run and verify

```bash
cd TrainModel
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
QT_QPA_PLATFORM=offscreen .venv/bin/python tests/test_ui_components.py
```

The checks exercise keyboard activation, disabled controls, typed input and
invalid input, selection values, safety confirmation, complete Python input
submission, and loading/rendering both application views.

## Design and source

- [UI style guide](../truth/ui/style-guide.md) and
  [HTML review preview](../truth/ui/ui-style-guide-preview.html).
- [Units and naming](../truth/conventions.md).
- `refrence-docs/` holds the original Figma CSS wireframes.
- Components and theme were reconciled with `development` at
  `c0580825e7b9f72f289cecdc1618b6136557d44b` without importing its unrelated
  window-sizing changes. The newer D002 display-unit decision is retained.

## Component wiring

All reusable QML components live in the root-level [`ui/`](../ui/README.md)
folder, alongside `truth/`. From a view in `TrainModel/ui/`, use:

```qml
import "../../ui"
```

See the [shared component catalog and import helper](../ui/README.md) for
all components and their signals. The module's three views remain here in
`TrainModel/ui/`.

For example, connect `harness.inputsSubmitted` to a backend slot accepting a
`QVariantMap`. `sendInputs()` emits a snapshot containing **all** input rows,
including fields with no preview pass-through. The existing field names are
harness keys, not a newly defined cross-module contract. The backend adapter
must honor the agreed interfaces and canonical units.

```python
harness.inputsSubmitted.connect(backend.receive_inputs)
```

Selection and toggle signals request a change; the host updates the bound
state. Programmatic state updates do not emit user commands. Input validators
use the C locale (decimal point) and preserve string IDs such as `"001"`.
Give each `ValueField` and `SelectField` a visible `label`. Space `TrackBlock`
instances by at least 2 px. Put `DataTable` in a scrolling container as needed.

## Current limits

- Seeded model values and run counters are preview behavior, not simulation.
- The harness still exposes backend units; the display conversion required by
  D002 is not yet applied consistently to that page.
- The optional dark theme is documented and previewed in HTML, not enabled
  in the QML application.
- The table uses a Repeater for small operator tables; use Qt TableView if
  large datasets require virtualization.
