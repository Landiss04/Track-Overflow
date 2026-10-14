# Scaling Diagnostic Run Guide

## Purpose

On Windows, a module window should stay at 16:10 while you drag a border
(see [SCALING_GUIDE.md](SCALING_GUIDE.md)). If a window instead shows blank
bars at the sides or top while you resize it, run this diagnostic on that
machine and send back the report. It works out why the aspect lock did not act
there.

`ui/diagnose_scaling.py` opens the real Train Model window with
`ui/aspect_lock.py` instrumented, and writes `scaling-report.txt`. It does not
change any file in the repository.

## Before you start

- Windows, with the Train Model's virtual environment already set up in
  `TrainModel\.venv` (the same one you launch the Train Model with).
- Close any Train Model windows that are already open.
- Use the branch on which you saw the problem. If that branch does not have
  `ui\diagnose_scaling.py` yet, copy the file from
  `Train-model-Interface-ui-split` into your `ui` folder. Leave it
  uncommitted.

## Run it

1. Open PowerShell in the repository root (the folder that holds `TrainModel`
   and `ui`).
2. Start the diagnostic:

   ```powershell
   TrainModel\.venv\Scripts\python ui\diagnose_scaling.py
   ```

   If you normally launch the Train Model a different way (another Python, an
   IDE run button, Conda), run the script that way instead. The aim is to match
   how you saw the problem.
3. When the Train Model window opens, check that it is not maximized or
   snapped to half the screen. If it is, double-click the title bar to restore
   it.
4. Drag the right border slowly, then let go.
5. Drag the bottom-right corner slowly, then let go.
6. If you have a second monitor, move the window to it, then drag a border
   again.
7. Note whether blank bars appeared during any drag.
8. Close the window. The terminal prints where it wrote the report.

## Send back

- `scaling-report.txt` from the repository root.
- One line on what you saw: bars or no bars, and during which step.

Then delete `scaling-report.txt`. Git ignores it, so it cannot be committed by
accident.

## Reading the report

Lines starting `!!` are problems. The `== summary` block at the end gives the
verdict.

| Report shows | Meaning |
| --- | --- |
| `LOCK NOT INSTALLED` or `no ctypes.windll` | This Python does not report itself as Windows (WSL, Cygwin, MSYS). The lock never installs, and the window letterboxes. |
| `_constrain raised` | The lock is installed, but it fails on every drag. The traceback shows why. |
| `native window recreated` | Qt replaced the window after the lock was attached, for example after a display-scaling change or a graphics fallback. Later drags are not locked. |
| `window procedure is no longer the lock's` | Something replaced the lock's hook on the window. |
| `rectangle changed after the lock` | The lock set 16:10, and Qt or Windows changed the size afterwards. |
| `drag end ... NOT 16:10` with none of the above | The lock ran but did not hold. Send the report as is. |
| `WM_SIZING messages: 0` after dragging | The drags never reached the lock. Check that the window was not maximized or snapped. |

The environment block at the top (Python build, Qt version, monitors and their
scaling, Remote Desktop, graphics API, any `QT_` settings) is what to compare
between a machine that works and one that does not.
