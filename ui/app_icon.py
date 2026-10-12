"""Give every module window the Track Overflow logo as its icon.

Shared by every module, so all windows carry the same icon. Call
:func:`install_app_icon` once, right after creating the
``QGuiApplication`` and setting its name, before any window is shown.

The logo is ``utils/Track_Overlow_Logo.png`` at the repository root.
The packaged binary must bundle it at the same relative path, for
example with PyInstaller's ``--add-data`` option:
``"utils/Track_Overlow_Logo.png:utils"``.
"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from PySide6.QtGui import QGuiApplication, QIcon

LOGO_PATH = (
    Path(__file__).resolve().parents[1] / "utils" / "Track_Overlow_Logo.png"
)

# Prefix of the Windows taskbar identity. The application name is
# appended so each module groups as its own taskbar button.
_APP_ID_PREFIX = "TrackOverflow"


def install_app_icon(app: QGuiApplication) -> bool:
    """Set the logo as the icon of every window ``app`` opens.

    Applies to the main window and to every dialog and secondary window
    the application creates. On Windows it also gives the process its
    own taskbar identity; without one, Windows groups the window under
    ``python.exe`` and shows Python's icon in the taskbar. Returns
    ``False`` if the logo file is missing, leaving the default icon.
    """
    if not LOGO_PATH.is_file():
        print(f"App icon not found: {LOGO_PATH}", file=sys.stderr)
        return False

    if sys.platform == "win32":
        name = "".join(app.applicationName().split()) or "App"
        shell32 = ctypes.windll.shell32  # type: ignore[attr-defined]
        shell32.SetCurrentProcessExplicitAppUserModelID(
            f"{_APP_ID_PREFIX}.{name}"
        )

    app.setWindowIcon(QIcon(str(LOGO_PATH)))
    return True
