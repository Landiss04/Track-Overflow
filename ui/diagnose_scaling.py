"""Diagnose the 16:10 window lock on one machine.

Runs the real Train Model window with ``ui/aspect_lock.py``
instrumented, and writes ``scaling-report.txt`` to the current folder.
Nothing in the repository is changed. Run it from the repo root with
the Python used to launch the Train Model:

    TrainModel\\.venv\\Scripts\\python ui\\diagnose_scaling.py

See ``documents/SCALING_DIAGNOSTIC.md`` for the full run guide.
"""

from __future__ import annotations

import ctypes
import os
import platform
import runpy
import struct
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any, TextIO

REPORT = Path.cwd() / "scaling-report.txt"

_WM_ENTERSIZEMOVE = 0x0231
_WM_EXITSIZEMOVE = 0x0232
_WM_DPICHANGED = 0x02E0
_SM_REMOTESESSION = 0x1000
_SPI_GETDRAGFULLWINDOWS = 0x0026
_GWLP_WNDPROC = -4


class Report:
    """Timestamped lines written to the report file as they happen."""

    def __init__(self, out: TextIO) -> None:
        self._out = out
        self._start = time.perf_counter()

    def say(self, *parts: object) -> None:
        elapsed = time.perf_counter() - self._start
        text = " ".join(str(part) for part in parts)
        print(f"{elapsed:8.3f}  {text}", file=self._out, flush=True)


def find_root() -> Path:
    """Return the repo root: the current folder or above, else ours."""
    candidates = [Path.cwd(), *Path.cwd().parents,
                  Path(__file__).resolve().parents[1]]
    for base in candidates:
        if (base / "ui" / "aspect_lock.py").is_file() and (
            base / "TrainModel" / "main.py"
        ).is_file():
            return base
    sys.exit("Run this from the Track-Overflow repo root.")


def git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return "git unavailable"
    return result.stdout.strip()


def report_environment(report: Report, root: Path) -> Any:
    """Record the interpreter, Qt and Windows settings; return user32."""
    say = report.say
    say("== environment")
    say("sys.platform", sys.platform, "| os.name", os.name,
        "| bits", struct.calcsize("P") * 8)
    say("python", sys.version.replace("\n", " "))
    say("executable", sys.executable)
    say("os", platform.platform())
    say("repo", root)
    say("git", git(root, "rev-parse", "--abbrev-ref", "HEAD"), "|",
        git(root, "log", "-1", "--oneline"))
    for key in sorted(os.environ):
        if key.startswith(("QT_", "QSG_", "QML_")):
            say("env", key, "=", os.environ[key])

    import PySide6
    from PySide6 import QtCore

    say("PySide6", PySide6.__version__, "| Qt runtime", QtCore.qVersion())

    windll = getattr(ctypes, "windll", None)
    if windll is None:
        say("!! no ctypes.windll: this Python cannot call Windows APIs, "
            "so the lock can never install")
        return None
    user32 = windll.user32
    say("remote desktop session",
        bool(user32.GetSystemMetrics(_SM_REMOTESESSION)))
    drag_full = ctypes.c_int()
    user32.SystemParametersInfoW(
        _SPI_GETDRAGFULLWINDOWS, 0, ctypes.byref(drag_full), 0)
    say("show window contents while dragging", bool(drag_full.value))
    return user32


class LockProbe:
    """Wraps the aspect lock so every way it can fail is logged."""

    def __init__(self, report: Report, aspect_lock: Any, user32: Any):
        self._say = report.say
        self._al = aspect_lock
        self._user32 = user32
        self._install = aspect_lock.install_aspect_lock
        self.lock: Any = None
        self.sizing = 0
        self.errors = 0
        self.overridden = 0
        self.drags: list[tuple[int, int, float]] = []
        self.hwnd_changes = 0
        self.proc_lost = False
        self._timer: Any = None

    def patch(self) -> None:
        probe = self

        def window_proc(lock, hwnd, msg, wparam, lparam):
            return probe.window_proc(lock, hwnd, msg, wparam, lparam)

        self._al.WindowsAspectLock._window_proc = window_proc
        self._al.install_aspect_lock = self.install

    @staticmethod
    def _rect_size(lparam: int) -> tuple[int, int]:
        from ctypes import wintypes

        rect = wintypes.RECT.from_address(lparam)
        return rect.right - rect.left, rect.bottom - rect.top

    @staticmethod
    def _client_size(lock: Any, hwnd: int) -> tuple[int, int, float]:
        from ctypes import wintypes

        rect = wintypes.RECT()
        lock._user32.GetClientRect(hwnd, ctypes.byref(rect))
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        return width, height, round(width / height, 4) if height else 0.0

    def window_proc(self, lock, hwnd, msg, wparam, lparam):
        """Replacement for ``WindowsAspectLock._window_proc``."""
        call_qt = lock._user32.CallWindowProcW
        if msg == self._al._WM_SIZING:
            self.sizing += 1
            proposed = self._rect_size(lparam)
            try:
                lock._constrain(hwnd, wparam, lparam)
            except Exception:  # noqa: BLE001  logged, never raised
                self.errors += 1
                if self.errors <= 3:
                    self._say("!! _constrain raised:\n"
                              + traceback.format_exc())
            locked = self._rect_size(lparam)
            result = int(call_qt(lock._original, hwnd, msg, wparam, lparam))
            final = self._rect_size(lparam)
            if final != locked:
                self.overridden += 1
                if self.overridden <= 5:
                    self._say("!! rectangle changed after the lock:",
                              locked, "->", final)
            if self.sizing % 40 == 1:
                self._say("WM_SIZING edge", wparam, "proposed", proposed,
                          "locked", locked, "final", final)
            return result
        if msg == _WM_ENTERSIZEMOVE:
            self._say("drag start, client", self._client_size(lock, hwnd))
        if msg == _WM_DPICHANGED:
            self._say("WM_DPICHANGED, new dpi", wparam & 0xFFFF)
        result = int(call_qt(lock._original, hwnd, msg, wparam, lparam))
        if msg == _WM_EXITSIZEMOVE:
            size = self._client_size(lock, hwnd)
            self.drags.append(size)
            verdict = "OK 16:10" if abs(size[2] - 1.6) < 0.01 else (
                "!! NOT 16:10")
            window = lock._window
            self._say("drag end, client", size, verdict, "| qt",
                      window.width(), "x", window.height(),
                      "dpr", window.devicePixelRatio())
        return result

    def install(self, window: Any, ratio: tuple[int, int]) -> Any:
        """Replacement for ``install_aspect_lock``."""
        from PySide6.QtCore import QTimer
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtQuick import QQuickWindow

        say = self._say
        say("== install")
        for screen in QGuiApplication.screens():
            geo = screen.geometry()
            say("screen", screen.name(),
                f"{geo.width()}x{geo.height()}+{geo.x()}+{geo.y()}",
                "dpr", screen.devicePixelRatio(),
                "logical dpi", round(screen.logicalDotsPerInch()))
        say("high-dpi rounding policy",
            QGuiApplication.highDpiScaleFactorRoundingPolicy())
        say("graphics api", QQuickWindow.graphicsApi(),
            "| scene graph backend",
            QQuickWindow.sceneGraphBackend() or "default")
        say("window", type(window).__name__,
            "reference", window.property("referenceWidth"),
            window.property("referenceHeight"),
            "visibility", window.visibility(),
            "size", window.width(), window.height())
        try:
            self.lock = self._install(window, ratio)
        except Exception:
            say("!! install_aspect_lock raised:\n" + traceback.format_exc())
            raise
        if self.lock is None:
            say("!! LOCK NOT INSTALLED: sys.platform is", sys.platform)
            return None
        say("lock installed on hwnd", self.lock._hwnd, "ratio", ratio,
            "size after snap", window.width(), window.height())
        self._timer = QTimer(window)
        self._timer.timeout.connect(self.check_alive)
        self._timer.start(500)
        return self.lock

    def check_alive(self) -> None:
        """Log when the native window or its procedure is replaced."""
        window = self.lock._window
        try:
            # winId() on a closed window creates a new native one, so
            # only look while the window is up.
            if not window.isVisible() or window.handle() is None:
                return
            live = int(window.winId())
        except RuntimeError:
            return
        if live != self.lock._hwnd:
            self.hwnd_changes += 1
            self._say("!! native window recreated: hwnd", self.lock._hwnd,
                      "->", live, "(the lock stays on the old one)")
            self.lock._hwnd = live
        if self.proc_lost:
            return
        get_proc = self._user32.GetWindowLongPtrW
        get_proc.restype = ctypes.c_void_p
        get_proc.argtypes = (ctypes.c_void_p, ctypes.c_int)
        current = get_proc(live, _GWLP_WNDPROC)
        ours = ctypes.cast(self.lock._proc, ctypes.c_void_p).value
        if current != ours:
            self.proc_lost = True
            self._say("!! window procedure is no longer the lock's:",
                      hex(current or 0), "vs", hex(ours or 0))

    def summary(self) -> None:
        say = self._say
        not_locked = sum(1 for drag in self.drags if abs(drag[2] - 1.6)
                         >= 0.01)
        say("== summary")
        say("lock installed:", self.lock is not None)
        say("WM_SIZING messages:", self.sizing, "| lock errors:",
            self.errors, "| changed after the lock:", self.overridden)
        say("drags:", len(self.drags), "| not 16:10:", not_locked)
        say("native window recreated:", self.hwnd_changes,
            "| window procedure replaced:", self.proc_lost)


def main() -> int:
    root = find_root()
    entry = root / "TrainModel" / "main.py"
    with open(REPORT, "w", encoding="utf-8") as out:
        report = Report(out)
        user32 = report_environment(report, root)

        sys.path.insert(0, str(root))
        sys.path.insert(0, str(entry.parent))
        import ui.aspect_lock as aspect_lock

        probe = LockProbe(report, aspect_lock, user32)
        probe.patch()

        report.say("== running", entry)
        # The Train Model serves a link to its test UI; keep it off the
        # name a normally launched Train Model would use.
        os.environ.setdefault("TRAIN_MODEL_LINK", "scaling-diagnostic")
        os.chdir(entry.parent)
        try:
            runpy.run_path(str(entry), run_name="__main__")
        except SystemExit:
            pass
        except Exception:  # noqa: BLE001  the report must still finish
            report.say("!! the app raised:\n" + traceback.format_exc())
        probe.summary()
    print(f"Report written to {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
