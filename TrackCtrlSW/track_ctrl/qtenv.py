"""Qt runtime setup that must happen before any QML engine is built.

Shared by the Track Controller UI and the test UI, which are separate
processes with separate entry points but the same Qt install.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def add_qt_dll_directory() -> None:
    """Make Qt's own DLLs findable by its QML plugins on Windows.

    Qt loads QML plugins with LoadLibrary at runtime. Python 3.8+
    restricts the DLL search path, so the plugins cannot find the Qt
    libraries that sit next to them unless that directory is added back
    explicitly. Without this the QML engine fails with "Cannot load
    library qtquick2plugin.dll" and no window is created.
    """
    if sys.platform != "win32":
        return
    import PySide6

    os.add_dll_directory(str(Path(PySide6.__file__).resolve().parent))
