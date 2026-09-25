# Train Model UI (stub)

PyQt6 + QML front-end for the ECE1140 Train Model, covering **page 3a** (main
operational view) and **page 3b** (test harness). This is a *stub*: it renders
both pages exactly as the mockup shows them and wires every value to bindable
Python state, but there is no simulation behind it — values are seeded to the
mockup and the interactive controls only flip that stub state.

QML owns all visuals; Python owns state. The two talk through QML context
properties (`theme`, `trainModel`, `harness`).

## Design sources

- **Tokens** — every color, font size, spacing, radius, and control dimension
  comes from `documents/UI_Style_Guide.md` (light theme), exposed as a single
  `theme` object built by `train_model/theme.py`. No QML file hard-codes a
  color or a token-sized dimension.
- **Dimensions & copy** — element sizes and the on-screen text are taken from
  the Figma CSS exports in `refrence-docs/` (`UIwireframe.css` = main page,
  `TestUIwireframe.css` = test UI).

## Run

```bash
cd TrainModel
source .venv/bin/activate        # PyQt6 6.11 + mypy; see "Setup" if missing
python main.py
```

Offscreen smoke test (no display needed):

```bash
QT_QPA_PLATFORM=offscreen timeout 8 python main.py   # clean = no output
```

## Type-check

```bash
cd TrainModel
.venv/bin/python -m mypy main.py train_model/        # → no issues found in 5 source files
```

`stubs/PyQt6/*.pyi` supply the `pyqtProperty`/`pyqtSignal` signatures PyQt6's
bundled stubs omit; `mypy.ini` points `mypy_path` at them.

## Layout

```
main.py                 entry point: builds theme, state objects, loads QML
train_model/theme.py    build_theme() → the design-token dict (80 tokens)
train_model/state.py    TrainModelState — page 3a bindable values + slots
train_model/harness.py  TestHarnessState — page 3b inputs/outputs/run control
ui/Main.qml             window shell, nav rail, 3a/3b view switcher
ui/MainView.qml         page 3a
ui/TestView.qml         page 3b
ui/components/*.qml     Badge, Card, Banner, MetricTile, TableRow/Header,
                        buttons, toggles, fields, NavRail, TopBar, …
stubs/PyQt6/*.pyi       local mypy stubs for the property/signal API
```

## Setup (if `.venv` is missing)

```bash
cd TrainModel
python3 -m venv .venv
.venv/bin/pip install "PyQt6==6.11.*" "mypy==2.3.*"
```

## Design discrepancies

Where the implementation and/or the mockup are internally inconsistent, the
code follows the mockup as drawn and the gap is flagged here (and at the
relevant call site). Numbered so in-code references resolve:

1. **Static stub** — no physics or controller; every value is a fixed seed
   matching the mockup. Only the tick counter and the interactive toggles
   change state.
2. **Nav-rail glyphs are placeholders** — the Figma export shows stub
   rectangles with per-item border insets, not real icons; reproduced as stroked
   outlines with no labels.
3. **Hamburger is a visual stub** — emits `menuClicked`, but the mockup defines
   no menu, so nothing opens.
4. **Card shadow is approximated** — `--shadow-1`'s blur is rendered as a 1 px
   offset dark rectangle; QML has no cheap true drop-shadow here.
5. **Banner surface** — the mockup's neutral grey maps to the `--bg-sunken`
   token rather than a dedicated grey.
6. **Toggles & secondary buttons are non-functional stubs** where the mockup
   implies live behavior; they only mutate the stub state.
7. **"SEND INPUTS TO TRAIN MODEL" is a no-op boundary** — there is no module
   under test to receive them yet.
8. **Output values embed units inline** (`32.4 MPH`) rather than a separate
   unit column, as drawn in the mockup.
9. **Failure-mode rows flip between two hardcoded labels** (normal/failed) and
   drive no downstream behavior.
10. **Signal pickup is seeded FAILED** on page 3a to match the "1 FAILED"
    badge; engine and brake are seeded NORMAL.
11. **Manual door control is rendered disabled** — the model displays door
    state but does not command it, so OPEN/CLOSE LEFT/RIGHT are inert (see
    `ui/MainView.qml`).
12. **Car count is inconsistent between panels** — Cabin & Load shows "3 CARS"
    / cars = 3, but the door-state table lists four cars (T-114-A…D).
13. **INPUTS badge reads "15" but the input table has 16 rows** — the badge
    count is kept as drawn in the mockup (see `train_model/harness.py`).
