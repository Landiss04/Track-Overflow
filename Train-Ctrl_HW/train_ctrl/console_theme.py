"""The console's design tokens, and the shared-library check."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from ui.theme import build_theme

# train_ctrl/console_theme.py -> Train-Ctrl_HW -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SHARED_UI = _REPO_ROOT / "ui"

# Tokens this console needs that the style guide does not define yet.
# Per guide section 1 a missing token is added to the guide first,
# then used; both are proposed in truth/_inbox/Train-Ctrl_HW/.
#
#   size_hero  section 6.5 fixes telemetry at 28 px, which is right
#              for a dense readout but unreadable from a driving
#              position. The approved wireframe uses a much larger
#              figure for the four primary readouts. Contrast is
#              unchanged: the same --text-primary on --bg-sunken.
#   brake_*    section 4.4 --danger is a deep signal red, right for
#              the emergency brake. The service brake is a routine
#              stop that only the Train Controller applies, and must
#              not read as the same control, so it is the amber a cab
#              brake handle uses. Contrast: text-primary on
#              brake_service is 11.2:1 (AAA).
PENDING_TOKENS: dict[str, Any] = {
    "size_hero": 72,
    "brake_service": "#F2C037",
    "brake_service_active": "#D9A520",
}


def build_console_theme() -> dict[str, Any]:
    """Return the shared tokens plus the pending ones, as one table."""
    theme = build_theme()
    theme.update(PENDING_TOKENS)
    return theme


def check_shared_library() -> bool:
    """Report, in words, a missing shared QML library.

    This module is a sibling of the repository-root ui/ folder and
    the views import it with a relative path. Moved out of the
    repository, every shared type goes unresolved and the window
    simply fails to load, so say so here instead.
    """
    if (_SHARED_UI / "ScaledWindow.qml").exists():
        return True
    print(
        f"Shared QML library not found at {_SHARED_UI}.\n"
        "This module has to sit beside it, in the repository root:\n"
        "    <repo>/ui/                         shared components\n"
        "    <repo>/Train-Ctrl_HW/main.py\n"
        "    <repo>/Train-Ctrl_HW/train_ctrl/\n"
        "Copying ui/theme.py and ui/aspect_lock.py into this module\n"
        "satisfies the Python imports but not the QML ones.",
        file=sys.stderr,
    )
    return False
