"""Measure a ScaledWindow going full screen on one machine.

Opens a test window built on ``ui/ScaledWindow.qml``, sends it full
screen the way the harness's tiled view does, and prints its size as Qt
and as Windows see it. A line marked ``!!`` means the window is larger
than the monitor. Also saves a capture of the real screen while full
screen to the temp folder. Nothing in the repository is changed.

Run from the repo root:

    TrainModel\\.venv\\Scripts\\python ui\\diagnose_fullscreen.py

Options isolate the cause: ``--no-lock`` skips ``ui.aspect_lock``,
``--hidden`` closes the window before going full screen, ``--no-grab``
skips the tile snapshot.
"""
import argparse
import ctypes
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.getcwd())

from PySide6.QtCore import QTimer, QUrl, qVersion
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from ui.aspect_lock import install_window_scaling
from ui.theme import build_theme
from utils.module_window import (
    keep_windows_open, save_window_snapshot, show_module_windows,
)

QML = b"""
import QtQuick
ScaledWindow {
    title: "fs-probe"
    Rectangle {
        anchors.fill: parent; color: "white"
        border.color: "red"; border.width: 12
        Text { anchors.centerIn: parent; font.pixelSize: 40
               text: "red border = canvas edge, must be fully visible" }
    }
}
"""


def rect(r):
    return f"({r.x()},{r.y()} {r.width()}x{r.height()})"


def native(hwnd):
    """Physical-pixel facts straight from Windows."""
    from ctypes import wintypes

    u = ctypes.windll.user32

    class MonitorInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.c_void_p]
    u.GetClientRect.argtypes = [wintypes.HWND, ctypes.c_void_p]
    u.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    u.MonitorFromWindow.restype = ctypes.c_void_p
    u.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    u.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    u.GetDpiForWindow.argtypes = [wintypes.HWND]
    win, client, info = wintypes.RECT(), wintypes.RECT(), MonitorInfo()
    info.cbSize = ctypes.sizeof(MonitorInfo)
    u.GetWindowRect(hwnd, ctypes.byref(win))
    u.GetClientRect(hwnd, ctypes.byref(client))
    u.GetMonitorInfoW(u.MonitorFromWindow(hwnd, 2), ctypes.byref(info))
    mon = info.rcMonitor
    size = (win.right - win.left, win.bottom - win.top)
    mon_size = (mon.right - mon.left, mon.bottom - mon.top)
    over = size[0] > mon_size[0] or size[1] > mon_size[1]
    return (
        f"native window=({win.left},{win.top} {size[0]}x{size[1]}) "
        f"client={client.right}x{client.bottom} "
        f"monitor=({mon.left},{mon.top} {mon_size[0]}x{mon_size[1]}) "
        f"dpi={u.GetDpiForWindow(hwnd)} "
        f"style=0x{u.GetWindowLongW(hwnd, -16) & 0xFFFFFFFF:08X}"
        + (" !! WINDOW LARGER THAN MONITOR" if over else "")
    )


def measure(label, window):
    screen = window.screen()
    canvas = window.property("canvas")
    scale = window.property("canvasScale")
    print(
        f"[{label}] visibility={window.visibility().name} "
        f"qt geometry={rect(window.geometry())} "
        f"frame={rect(window.frameGeometry())} "
        f"min={window.minimumWidth()}x{window.minimumHeight()} "
        f"screen={rect(screen.geometry())} "
        f"available={rect(screen.availableGeometry())} "
        f"dpr={window.devicePixelRatio()} "
        f"canvasScale={scale:.4f} "
        f"canvas at ({canvas.x():.1f},{canvas.y():.1f}) "
        f"drawn {1440 * scale:.0f}x{900 * scale:.0f}"
    )
    if sys.platform == "win32":
        print(f"[{label}] {native(int(window.winId()))}")
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-lock", action="store_true",
                        help="skip ui.aspect_lock")
    parser.add_argument("--hidden", action="store_true",
                        help="close the window before going full screen")
    parser.add_argument("--no-grab", action="store_true",
                        help="skip the tile snapshot while full screen")
    args = parser.parse_args()

    app = QGuiApplication(sys.argv[:1])
    keep_windows_open(app)
    import PySide6
    print("platform", sys.platform, "| PySide6", PySide6.__version__,
          "| Qt", qVersion(), "| qpa", app.platformName(), "| args", vars(args))
    for key in sorted(os.environ):
        if key.startswith(("QT_", "QSG_", "QML_")):
            print("env", key, "=", os.environ[key])
    for screen in app.screens():
        print("screen", screen.name(), rect(screen.geometry()),
              "dpr", screen.devicePixelRatio(),
              "logical dpi", round(screen.logicalDotsPerInch()))
    if sys.platform == "win32":
        u = ctypes.windll.user32
        u.GetThreadDpiAwarenessContext.restype = ctypes.c_void_p
        u.GetAwarenessFromDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        print("dpi awareness (0 unaware, 1 system, 2 per-monitor)",
              u.GetAwarenessFromDpiAwarenessContext(
                  u.GetThreadDpiAwarenessContext()),
              "| remote session", bool(u.GetSystemMetrics(0x1000)))

    theme = build_theme()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("theme", theme)
    engine.loadData(QML, QUrl.fromLocalFile(str(Path("ui/probe.qml").resolve())))
    window = engine.rootObjects()[0]
    print("graphics api", window.rendererInterface().graphicsApi().name)
    lock = None if args.no_lock else install_window_scaling(window)

    def close_first():
        measure("1 normal", window)
        if args.hidden:
            window.close()

    def full_screen():
        show_module_windows(True)

    def while_full_screen():
        measure("2 full screen", window)
        if not args.no_grab:
            save_window_snapshot(
                window, os.path.join(tempfile.gettempdir(), "fs-probe.png"))
            measure("3 after snapshot", window)
        shot = Path(tempfile.gettempdir()) / "fs-probe-screen.png"
        app.primaryScreen().grabWindow(0).save(str(shot))
        print("screen capture", shot)

    def back():
        window.showNormal()

    def done():
        measure("4 normal again", window)
        sys.stdout.flush()
        os._exit(0)  # skip Qt teardown; the probe has nothing to save

    QTimer.singleShot(1500, close_first)
    QTimer.singleShot(3000, full_screen)
    QTimer.singleShot(5000, while_full_screen)
    QTimer.singleShot(6500, back)
    QTimer.singleShot(8000, done)
    app.exec()
    del lock


if __name__ == "__main__":
    main()
