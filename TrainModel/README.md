# Train Model UI

PySide6 + QML front-end for the ECE1140 Train Model, covering **page 3a** (main
operational view) and **page 3b** (test harness). `TrainModelState` wraps the
real `TrainModel` in `train_model/model.py`: the test harness sends it inputs
and drives the clock, and the views show the model's state. A few header
fields that the model does not produce (train ID, line, mode, clock, arrival)
remain seeded to the mockup.

QML owns all visuals; Python owns state. The two talk through QML context
properties (`theme`, `trainModel`, `harness`).

## Design sources

- **Tokens** — every color, font size, spacing, radius, and control dimension
  comes from `documents/UI_Style_Guide.md` (light theme), exposed as a single
  `theme` object built by the shared [`ui/theme.py`](../ui/theme.py) at the
  repository root. No QML file hard-codes a
  color or a token-sized dimension.
- **Dimensions & copy** — element sizes and the on-screen text are taken from
  the Figma CSS exports in `refrence-docs/` (`UIwireframe.css` = main page,
  `TestUIwireframe.css` = test UI).

## Run

```bash
cd TrainModel
source .venv/bin/activate        # PySide6 6.11 + mypy; see "Setup" if missing
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

PySide6 ships its own type stubs, so no local stubs are needed.

## Layout

```
main.py                 entry point: builds theme, state objects, loads QML
train_model/state.py    TrainModelState — page 3a bindable values + slots
train_model/harness.py  TestHarnessState — page 3b inputs/outputs/run control
ui/Main.qml             window shell, nav rail, 3a/3b view switcher
ui/MainView.qml         page 3a
ui/TestView.qml         page 3b
```

Reusable QML components are not in this folder. They live in the shared
root-level [`ui/`](../ui/README.md) library and are imported from each view
with `import "../../ui"`.

## Setup (if `.venv` is missing)

```bash
cd TrainModel
python3 -m venv .venv
.venv/bin/pip install "PySide6==6.11.*" "mypy==2.3.*"
```

## Design discrepancies

Where the implementation and/or the mockup are internally inconsistent, the
code follows the mockup as drawn and the gap is flagged here (and at the
relevant call site). Numbered so in-code references resolve:

1. **Header fields are seeded** — train ID, line, mode, clock and arrival are
   fixed values from the mockup; the model does not produce them. Power
   consumption shows the commanded power capped at P_max, because the model
   does not report power.
2. **Nav-rail glyphs are placeholders** — the Figma export shows stub
   rectangles with per-item border insets, not real icons; reproduced as stroked
   outlines with no labels.
3. **Hamburger is a visual stub** — emits `menuClicked`, but the mockup defines
   no menu, so nothing opens.
4. **Card shadow is approximated** — `--shadow-1`'s blur is rendered as a 1 px
   offset dark rectangle; QML has no cheap true drop-shadow here.
5. **Banner surface** — the mockup's neutral grey maps to the `--bg-sunken`
   token rather than a dedicated grey.
6. **Releasing the passenger emergency brake does nothing** — the model
   latches the pull (design §5.8 leaves release open), so the brake stays
   applied until **Reset module**.
7. **"SEND INPUTS TO TRAIN MODEL" also advances one tick**, so the outputs
   respond at once. Later ticks reuse the last sent inputs, except that
   `passengers_boarded` applies once per send. The harness `grade` row is in
   degrees and is converted to the percent the model takes.
8. **Output values embed units inline** (`32.4 MPH`) rather than a separate
   unit column, as drawn in the mockup.
9. **Failure modes apply from the next tick**, as the model's
   `set_failures` defines.
10. **All failure modes start cleared**, not with signal pickup failed as the
    mockup's "1 FAILED" badge shows, so the harness's commanded speed and
    authority reach the model from the first tick.
11. **Manual door control is rendered disabled** — the model displays door
    state but does not command it, so OPEN/CLOSE LEFT/RIGHT are inert (see
    `ui/MainView.qml`).
12. **Car count is inconsistent between panels** — Cabin & Load shows "3 CARS"
    / cars = 3, but the door-state table lists four cars (T-114-A…D).
13. **INPUTS badge reads "15" but the input table has 21 rows** — the badge
    count is kept as drawn in the mockup (see `train_model/harness.py`).
