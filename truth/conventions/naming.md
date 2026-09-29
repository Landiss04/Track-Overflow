# naming

**Status:** current
**Owner:** Kevin
**Provenance:** `documents/Coding Standards (Group).docx` §1; `documents/PYTHON_STYLE_GUIDE.md` §5, §8; `documents/requirements-matrix.md` §1–2 (module names)
**Aliases:** naming conventions, style guide naming, PEP 8 naming
**Last updated:** 2026-09-29

The baseline is PEP 8. `Coding Standards (Group).docx` is the graded group standard
and wins where it is specific. `PYTHON_STYLE_GUIDE.md` extends PEP 8 for this
codebase and wins over bare PEP 8 where the two differ. Where all three are silent,
PEP 8 applies.

## Module names

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

## Python names

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
  the unit is not obvious. See [units.md](units.md) for which unit belongs on which side of the
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

## Docstrings and comments

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

## Conflict

Owner: Kevin.

**Unit-suffix examples vs. backend units. Open.**

| Value | Provenance |
|-------|------------|
| `speed_mph` and `grade_percent` are the examples of a unit-suffixed name | This entry, `## Python names` |
| The backend stores speed in m/s and gradient in degrees; D002's example is `speed_mps` | [units.md](units.md) backend table; D002 |

The examples name a display unit (`mph`) and the percent side of the open gradient
conflict in [units.md](units.md).
