# files-and-paths

**Status:** current
**Owner:** Kevin
**Provenance:** `documents/srs-filled.md` §2.4, §3.1.3 (REQ-INTF-012), §3.5.1–3.5.6 (development, `c058082`); `documents/Coding Standards (Group).docx` §1.1, §2.1; `documents/PYTHON_STYLE_GUIDE.md` §1; `.gitattributes`; delivery as a prebuilt binary asserted by Kevin 2026-09-29; branch model per D003; `next_blocks` from `20572b1` (SeeingEyeTree, PR #24), adopted as the direction-of-travel format by Landis 2026-10-07
**Aliases:** File and path conventions, file layout, paths, repo layout, project structure
**Last updated:** 2026-10-07

## Paths

- Path handling is platform-neutral. The system runs on any developer's operating
  system and on Windows 11 lab machines; no OS-specific separators or absolute paths
  appear in source.
- Resources are opened with `with`, never left to the garbage collector — layout
  files, save-state files, and connections alike.

## File names

- Source files are short and all-lowercase. Underscores only where they improve
  readability: `track_layout.py`, `rolling_stock.py`.
- Track layout data is loaded from the course-provided JSON files at startup. Each
  file lists a line name and an array of blocks; each block carries block number,
  section letter, length (m), grade (%), speed limit (km/h), elevation and cumulative
  elevation (m), an optional `infrastructure` object, and an optional `next_blocks`.
- `next_blocks` is the block's direction of travel: the block numbers a train in the
  block may move on to, and `"yard"` where it may run into the yard. Each listed block
  must be one the layout joins to it, next to it in the file or through a switch. A
  line whose file has no `next_blocks` (the Red line, for now) is run both ways.

## Entry point and dependencies

- The system is turned in as a standalone executable binary, pre-compiled before delivery
  (REQ-DSN-001, REQ-DSN-002).
- `requirements.txt` pins package versions so the install is reproducible.
- Python, PySide6, and PyInstaller minimum versions are in [toolchain.md](toolchain.md).
- The whole system is submittable as one runnable executable; each subsystem is also
  independently installable.
- No external services or network connections are required at runtime.

## Module boundaries

- Modules interact through defined interfaces, never by reaching into another
  module's internal state.
- Shared utilities — the simulation clock and the event logger — are standalone
  modules usable by any part of the system.
- All components share a single simulation clock supporting real-time and
  fast-forward operation.

## UI token files

Defined in `truth/ui/style-guide.md` §9. Not restated here.

## Layout inside a file

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

## Repository

- `.gitattributes` normalizes text files to LF (`* text=auto eol=lf`). Binary
  formats — `.docx`, `.xlsx`, `.pdf`, `.gan`, images, archives, executables — are
  marked `binary` explicitly so git's auto-detection cannot corrupt them.
- `development` is the default branch and `main` is release-only; see
  [D003](../decisions/D003-branch-model.md).
- Source and documentation live in the course Git repository, with commits linked to
  issue tracker tickets. Each team member commits in every sprint.

## Linting

`flake8 --max-line-length=79` for layout, indentation, whitespace, and unused
variables; `pylint` for naming and missing docstrings; `pep8-naming` as a flake8
plugin. If `black` is used, it must be configured `line-length = 79` — its default
of 88 conflicts with the standard above.

## Supersedes

- Track layout files: previously CSV with a named column list, from `srs-filled.md`
  Appendix A before v1.0; the SRS now specifies JSON.
- Entry point: previously `python main.py` after `pip install -r requirements.txt`, from
  `srs-filled.md` §3.5.1 before v1.0 (`b14ae73`); the system is turned in as a prebuilt
  binary (REQ-DSN-001, REQ-DSN-002; Kevin 2026-09-29).
- Direction of travel: previously not in the layout files, so every block ran both
  ways; now `next_blocks` per block, on the Green line (PR #24, Landis 2026-10-07).
