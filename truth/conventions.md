# Conventions

## Naming

**Status:** current
**Owner:** Kevin
**Provenance:** `documents/Coding Standards (Group).docx` §1; `documents/PYTHON_STYLE_GUIDE.md` §5, §8; `documents/requirements-matrix.md` §1–2 (module names)
**Aliases:** naming conventions, style guide naming, PEP 8 naming
**Last updated:** 2026-09-25

The baseline is PEP 8. `Coding Standards (Group).docx` is the graded group standard
and wins where it is specific. `PYTHON_STYLE_GUIDE.md` extends PEP 8 for this
codebase and wins over bare PEP 8 where the two differ. Where all three are silent,
PEP 8 applies.

### Module names

The system has five modules. These spellings are canonical in prose, UI headers, and
documentation.

| Module | Aliases |
|--------|---------|
| CTC Office | CTC |
| Track Controller | Wayside Controller |
| Train Controller | none |
| Track Model | none |
| Train Model | none |

Track Controller and Train Controller each exist as a software and a hardware
instance; the instance is named alongside the module, not as a separate module.

The Moving Block Overlay (MBO Controller, MBO Scheduler) is out of scope and is not a
module of this system.

### Python names

| Element | Convention | Example |
|---|---|---|
| Module / package | lowercase, short; underscores only where they help | `track_layout.py`, `signals/` |
| Class | CapWords, no underscores | `TrainController`, `TrackBlock` |
| Acronym in a class name | all letters capitalized | `CTCOffice`, `HTTPServerError` |
| Exception | CapWords + `Error` suffix | `InvalidBlockError` |
| Function / method | lowercase_with_underscores | `set_speed_limit()` |
| Instance attribute | lowercase_with_underscores | `current_speed` |
| Non-public attribute / method | one leading underscore | `_authority`, `_check_switch()` |
| Name-mangled attribute | two leading underscores, only to avoid a subclass clash | `__speed` |
| Local / global variable | lowercase_with_underscores | `block_number` |
| Constant | UPPER_CASE_WITH_UNDERSCORES, module level, after imports | `MAX_SPEED_MPS` |
| Enum class / members | CapWords class, UPPER_CASE members | `SignalAspect.STOP` |
| Type variable | CapWords, short; `_co` / `_contra` for variance | `T`, `RollingStockT` |
| First arg | `self` on instance methods, `cls` on class methods | `def stop(self):` |

Rules that apply on top of the table:

- Identifiers are ASCII, English words.
- Never `l`, `O`, or `I` as a single-character name. Use `L` if you want `l`.
- A name that clashes with a keyword takes a single trailing underscore: `class_`,
  `from_`. Never a misspelling.
- Method names start with a verb: `set_speed_limit`, `calculate_braking_distance`,
  `is_block_occupied`.
- A quantity with units carries the unit in the name: `speed_mph`, `distance_m`,
  `mass_kg`, `grade_percent`. A bare `speed` or `distance` is not acceptable where
  the unit is not obvious. See `## Units` for which unit belongs on which side of the
  display boundary.
- No magic numbers. A literal with meaning becomes a named constant.
- Short names (`i`, `x`, `dt`, `v0`) are for loop counters and short-lived locals
  inside a single function. Public APIs are descriptive.
- Properties are named like the attribute they represent — `speed`, never
  `get_speed`. The backing attribute takes a leading underscore: `_speed`.
- Prefer plain public attributes over getter/setter pairs. Convert to `@property`
  later if validation is needed; the caller-facing name does not change.
- `mixedCase` appears in new code only to match an external library's callback names.
- Do not invent `__dunder__` names.

### Docstrings and comments

- Docstrings on every public module, class, function, and method. Triple double
  quotes. Non-public helpers take a short comment after the `def` line instead.
- One-line docstring: imperative phrase ending in a period — "Return the speed limit
  for a block.", not "Returns ...". Closing `"""` on the same line.
- Multi-line docstring: one-line summary, blank line, detail. Closing `"""` on its
  own line.
- Args / Returns / Raises use **Google style** project-wide.
- Comments are complete sentences in English, capitalized, and explain *why*, not
  *what*. A comment that contradicts the code is worse than no comment.
- Block comments are indented to the code they describe; `#` then one space; `#`
  alone separates paragraphs.
- Inline comments are used sparingly, at least two spaces after the statement.

## Units

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin 2026-09-25; quantity list migrated from `common/Units.md`; cross-checked against `common/interfaces.py` unit suffixes and `documents/srs-filled.md`
**Aliases:** units, unit conventions, measurement units
**Last updated:** 2026-09-25

Two unit systems exist and they are not interchangeable. Everything that is stored,
computed, or passed across a module boundary is metric SI, with temperature as the
single exception — temperature is Fahrenheit everywhere, backend included. Everything
a user sees is imperial, with power as the single exception — power is displayed in
watts.

Conversion happens at the display layer only. State, signals, and interface payloads
are never converted. A value that crosses a module boundary is always in its backend
unit.

### Backend units

Canonical units for state, computation, and all cross-module signals.

| Quantity        | Unit            | Symbol | Notes                                              |
|-----------------|-----------------|--------|----------------------------------------------------|
| Speed           | meters/second   | m/s    |                                                    |
| Speed limit     | meters/second   | m/s    |                                                    |
| Distance        | meters          | m      |                                                    |
| Time            | seconds         | s      |                                                    |
| Gradient        | degrees         | deg    | Positive = uphill in direction of travel           |
| Elevation       | meters          | m      | Above datum                                        |
| Temperature     | Fahrenheit      | F      | Ambient and cabin temperature. Exception to metric |
| Authority       | meters          | m      | Distance the train may travel. **See Conflict**    |
| Acceleration    | meters/second²  | m/s^2  |                                                    |
| Force           | Newtons         | N      |                                                    |
| Mass            | kilograms       | kg     |                                                    |
| Power           | Watts           | W      |                                                    |
| Passenger count | integer         | persons|                                                    |

### UI display units

What every UI renders. Converted from the backend unit at the display layer.

| Quantity        | Unit            | Symbol | Notes                                                |
|-----------------|-----------------|--------|------------------------------------------------------|
| Speed           | miles/hour      | mph    |                                                      |
| Speed limit     | miles/hour      | mph    |                                                      |
| Distance        | feet            | ft     |                                                      |
| Time            | seconds         | s      | No imperial equivalent; unchanged                    |
| Gradient        | degrees         | deg    | No imperial equivalent; unchanged                    |
| Elevation       | feet            | ft     |                                                      |
| Temperature     | Fahrenheit      | F      | Already Fahrenheit in the backend; no conversion     |
| Authority       | feet            | ft     | Distance. **See Conflict**                           |
| Acceleration    | feet/second²    | ft/s^2 |                                                      |
| Force           | pound-force     | lbf    |                                                      |
| Mass            | short tons      | ton    |                                                      |
| Power           | kilowatts       | kW     | Exception to imperial. Never horsepower              |
| Passenger count | integer         | persons| Not a measurement; unchanged                         |

### Conversion factors

Backend → UI. Multiply by the factor unless the formula column says otherwise.

| Quantity     | From  | To     | Factor / formula          |
|--------------|-------|--------|---------------------------|
| Speed        | m/s   | mph    | × 2.236936                |
| Distance     | m     | ft     | × 3.280840                |
| Elevation    | m     | ft     | × 3.280840                |
| Acceleration | m/s^2 | ft/s^2 | × 3.280840                |
| Authority    | m     | ft     | × 3.280840                |
| Force        | N     | lbf    | × 0.2248089               |
| Mass         | kg    | ton    | × 0.001102311             |
| Power        | W     | kW     | × 0.001                   |
| Temperature  | F     | F      | none — Fahrenheit already |

Reverse conversion (UI → backend) divides by the same factor. Conversions are exact
to the digits shown; do not round the factor before applying it, round the displayed
result instead.

Supporting factors, for reference when a value arrives in a non-canonical unit:

| From         | To    | Factor       |
|--------------|-------|--------------|
| Celsius      | F     | × 9/5, + 32  |
| metric tonne | kg    | × 1000       |
| metric tonne | ton   | × 1.102311   |
| kg           | lb    | × 2.204623   |
| m            | mi    | × 0.000621371|

### Conflict

Owner: Kevin.

**Authority — distance vs. block ID. Open.**

| Value | Provenance |
|-------|-----------|
| meters (distance) | `srs-filled.md` §1.3 glossary ("the maximum distance a train is permitted to travel before stopping"); `requirements-matrix.md` §2 ("Authority (distance) from Wayside Controller"); `common/interfaces.py` — `TrackSignal.authority_m`, `set_commanded_signal`, `receive_suggestion`, `get_commanded_signal` all carry `authority_m: float` |
| block ID (string) | `common/Units.md` as migrated into this entry — "Destination block up to which the train may travel" |

The backend and UI tables above carry meters, because that is what three sources
including the agreed interface contract transport. The block-ID reading is recorded
here rather than discarded: it is the only source that said so, and it may reflect a
superseded design rather than an error. These are not the same kind of value — one is
a measurement that converts to feet for display, the other is an identifier that does
not convert at all — so this must be resolved, not left ambiguous.

**Gradient — degrees vs. percent. Open.**

| Value | Provenance |
|-------|-----------|
| degrees | `common/Units.md` as migrated into this entry; `common/interfaces.py` — `BlockState.grade_deg` |
| percent | `srs-filled.md` Appendix A (layout CSV column "Grade (%)") |

Degrees and percent are not the same quantity, so no conversion factor between them
is recorded here until the resolution says which one the backend stores. The agreed
interface contract carries `grade_deg`, which favors degrees; the percent claim is
confined to the layout file format, which is itself unresolved below.

**Track layout file format — unresolved.**

`srs-filled.md` §3.1.3 and Appendix A specify CSV, loaded at startup, with the
columns named under `## File and path conventions`. The layout files actually in the
repository are JSON. One of the two is out of date. This blocks the gradient conflict
above, since the file format determines whether "Grade (%)" is a column name that
still exists.

### Resolved

**Speed — m/s.** `srs-filled.md` Appendix A names the layout CSV column "Speed Limit
(km/h)". That is an input-format difference only: the loader converts on read and
nothing downstream sees km/h. The backend unit for speed is m/s, as recorded above.

The style documents are not a source of unit conflicts. `MAX_SPEED_KMH`,
`speed_kmh`, and `grade_percent` in `Coding Standards (Group).docx` and
`PYTHON_STYLE_GUIDE.md` illustrate the naming format — that a unit belongs in the
name — and do not assert which unit a quantity carries.

## Identifiers

**Status:** current
**Owner:** Kevin
**Provenance:** `documents/PYTHON_STYLE_GUIDE.md` §8; `documents/Coding Standards (Group).docx` §1.1, §2.2; `documents/srs-filled.md` §1.3, §5 Appendix A; `truth/ui/style-guide.md` §3, §6.7
**Aliases:** IDs, ID formats, key formats
**Last updated:** 2026-09-27

### ID values

- **All IDs are strings**, never integers, even when they look numeric. This applies
  to train IDs, block IDs, and station codes. The rule exists to make arithmetic on
  an identifier a type error rather than a silent bug.
- Track layout files carry a Block Number column. The value is read as a string.
- **Authority is a distance, not an ID.** `common/interfaces.py` transports it as
  `authority_m: float` on every interface that carries it, and the SRS glossary
  defines it as a distance. One source calls it a destination block ID; that reading
  is recorded as an open conflict under `## Units` and is not settled here.
- Every ID, train ID, block ID, and timestamp **shall** render in the mono face in
  any UI.

### Requirement IDs

`REQ-<AREA>-<NNN>` — uppercase area, three-digit zero-padded number. Example:
`REQ-FUNC-007`.

### Exception identifiers

- Every custom exception derives from `Exception`, never `BaseException`.
- Each module defines one base exception so callers can catch the whole project's
  errors in one clause — e.g. `TrainControllerError`, with `InvalidBlockError`
  deriving from it.
- The hierarchy is designed around what the catching code needs to know: "what went
  wrong", not "a problem occurred".
- Re-raising uses explicit chaining: `raise NewError("...") from original_error`.

### Design token identifiers

UI design tokens use the `--kebab-case` names in `truth/ui/style-guide.md`
Sections 4, 5, and 10. The key names are identical between the light and dark
palettes, which is what makes the optional dark theme a drop-in token swap. A token
that does not exist is added to the style guide first, then used.

### Pending

The only train ID format appearing in a normative document is `TRN-014`, as an
example in `truth/ui/style-guide.md` §6.7 (`Train Controller — TRN-014`). It is an
illustration, not a stated format. Block and station ID formats are not stated
anywhere. Owner: Kevin — decide and record, or record that IDs are opaque strings
with no enforced shape.

## File and path conventions

**Status:** current
**Owner:** Kevin
**Provenance:** `documents/srs-filled.md` §2.3, §3.1.3, §3.5.1–3.5.6; `documents/Coding Standards (Group).docx` §1.1, §2.1; `documents/PYTHON_STYLE_GUIDE.md` §1; `truth/ui/style-guide.md` §9, §11; `.gitattributes`
**Aliases:** file layout, paths, repo layout, project structure
**Last updated:** 2026-09-27

### Paths

- Path handling is platform-neutral. The system runs on any developer's operating
  system and on Windows 11 lab machines; no OS-specific separators or absolute paths
  appear in source.
- Resources are opened with `with`, never left to the garbage collector — layout
  files, save-state files, and connections alike.

### File names

- Source files are short and all-lowercase. Underscores only where they improve
  readability: `track_layout.py`, `rolling_stock.py`.
- Track layout data is loaded from the course-provided CSV files at startup. Columns:
  Block Number, Block Length (m), Grade (%), Speed Limit (km/h), Infrastructure type,
  Station Name, Door Side.

### Entry point and dependencies

- The system launches with `python main.py` after `pip install -r requirements.txt`,
  with no additional configuration.
- `requirements.txt` pins package versions so the install is reproducible.
- Python 3.10 or later.
- The whole system is submittable as one runnable executable; each subsystem is also
  independently installable.
- No external services or network connections are required at runtime.

### Module boundaries

- Modules interact through defined interfaces, never by reaching into another
  module's internal state.
- Shared utilities — the simulation clock and the event logger — are standalone
  modules usable by any part of the system.
- All components share a single simulation clock supporting real-time and
  fast-forward operation.

### UI token files

- Design tokens are defined once, in a single module (for example `ui/theme.py`), as
  named constants imported by every view. **No literal hex value appears in widget
  code.**
- Under PyQt, tokens are injected into one application-wide QSS stylesheet built from
  those constants, so a theme change is a one-line swap of the token dictionary.
- `truth/ui/ui-style-guide-preview.html` is the visual source of truth for review.
  A token change **shall** land in both `truth/ui/style-guide.md` and the preview in the
  same commit.

### Layout inside a file

- Order: module docstring, then module-level dunders (`__all__`, `__version__`), then
  imports, then constants, then functions and classes. `from __future__` imports
  precede the dunders.
- Imports: one per line, three groups separated by a blank line — standard library,
  third-party, local. Absolute imports preferred over deep relative ones; relative
  imports only within a tightly-coupled subpackage. No wildcard imports.
- 4 spaces per indent level, never tabs.
- 79 characters max for code, 72 for docstrings and comments. Extending code lines to
  99 requires team agreement and has not been agreed; docstrings and comments stay at
  72 regardless.
- Wrapping happens inside brackets, not with backslashes. Closing bracket on its own
  line, aligned with the start of the statement (PEP 8 "Option B"), everywhere.
- Break *before* a binary operator in new code.
- Two blank lines around top-level classes and functions; one between methods.
- Quote style is consistent within a module; docstrings always `"""`.

### Repository

- `.gitattributes` normalizes text files to LF (`* text=auto eol=lf`). Binary
  formats — `.docx`, `.xlsx`, `.pdf`, `.gan`, images, archives, executables — are
  marked `binary` explicitly so git's auto-detection cannot corrupt them.
- Source and documentation live in the course Git repository, with commits linked to
  issue tracker tickets. Each team member commits in every sprint.

### Linting

`flake8 --max-line-length=79` for layout, indentation, whitespace, and unused
variables; `pylint` for naming and missing docstrings; `pep8-naming` as a flake8
plugin. If `black` is used, it must be configured `line-length = 79` — its default
of 88 conflicts with the standard above.
