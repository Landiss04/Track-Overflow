**Target:** truth/conventions/toolchain.md
**Action:** replace
**Proposed by:** Claude (Claude Code) on Train-model-Interface
**Provenance:** venv-only installation asserted by Kevin Schillinger 2026-09-30 ("system will never get pyside6 or pyinstaller venv only"); all other content unchanged from `origin/truth` fc2ff4e

---

# toolchain

**Status:** current
**Owner:** Kevin
**Provenance:** `documents/srs-filled.md` §2.4 (Python 3.10 or later) and §3.1.3 REQ-INTF-014 (PySide6 is the GUI framework), development `c058082`; PySide6 and PyInstaller versions asserted by Kevin 2026-09-29; scope limited to development machines because the system is turned in as a prebuilt binary (Kevin 2026-09-29); PySide6 and PyInstaller installed in a virtual environment only, never system-wide (Kevin 2026-09-30)
**Aliases:** dev environment, environment, toolchain versions, minimum versions
**Last updated:** 2026-09-30

Minimum versions every development machine must have. Lab machines run the prebuilt
binary (see [files-and-paths.md](files-and-paths.md)) and need none of them. The session-start
environment drift check verifies exactly these and nothing else.

PySide6 and PyInstaller are installed only in a project virtual environment, never in the
system Python. Run every check below with the virtual environment's interpreter. The system
interpreter lacking these packages is expected and is not drift.

| Tool    | Minimum | Check (run inside the virtual environment)       |
|---------|---------|--------------------------------------------------|
| Python  | 3.10    | `python --version` ≥ 3.10                        |
| PySide6 | 6.11    | `python -c "import PySide6; print(PySide6.__version__)"` ≥ 6.11 |
| PyInstaller | 6.22.2 | `pyinstaller --version` ≥ 6.22.2               |

All bounds are inclusive. Versions compare numerically per component: 3.9 is
below 3.10.

## Supersedes

- Install location: previously unstated, and the checks ran against whatever
  interpreter was on the path. PySide6 and PyInstaller now live in a virtual
  environment only (Kevin 2026-09-30).
