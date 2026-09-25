"""Design tokens for the ECE1140 UI Style Guide, light theme.

Single source of truth for colour, typography, spacing, radius and control
sizing, per style guide section 9. No literal token value appears anywhere
else in the module: QML reads these through the ``theme`` context property.

Token names match the style guide so the optional dark theme of section 10
is a drop-in replacement.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QFontDatabase

# Surfaces and borders (style guide 4.1).
BG_APP = "#F4F6F8"
BG_SURFACE = "#FFFFFF"
BG_RAISED = "#FFFFFF"
BG_SUNKEN = "#E8ECF0"
BORDER = "#D5DCE3"
BORDER_STRONG = "#8795A3"

# Text (4.2).
TEXT_PRIMARY = "#16202A"
TEXT_SECONDARY = "#4B5C6B"
TEXT_MUTED = "#5F6B79"
TEXT_INVERSE = "#FFFFFF"

# Accent (4.3).
ACCENT = "#1D6FD0"
ACCENT_HOVER = "#1A5FB4"
ACCENT_ACTIVE = "#164E96"
ACCENT_SUBTLE = "#E4EFFB"
ON_ACCENT = "#FFFFFF"

# Semantic (4.4).
SUCCESS = "#15803D"
SUCCESS_HOVER = "#126832"
SUCCESS_BG = "#EDF7F0"
WARNING = "#B45309"
WARNING_BG = "#FDF2E0"
DANGER = "#C0272D"
DANGER_HOVER = "#A81F25"
DANGER_ACTIVE = "#8C1A1F"
DANGER_BG = "#FBE8E9"
INFO = "#4338CA"
INFO_BG = "#EAE8FB"
FOCUS_RING = "#1D6FD0"

# Typography (3). Helvetica and Monaco are not bundled; the fallback stacks
# resolve to Arial and Consolas on Windows and to Helvetica Neue and Menlo
# on macOS.
UI_FAMILIES = [
    "Helvetica Neue",
    "Helvetica",
    "Arial",
    "Nimbus Sans",
    "DejaVu Sans",
]
MONO_FAMILIES = [
    "Monaco",
    "Menlo",
    "Consolas",
    "Andale Mono",
    "DejaVu Sans Mono",
]

SIZE_DISPLAY = 36
SIZE_H1 = 28
SIZE_H2 = 22
SIZE_H3 = 18
SIZE_BODY = 15
SIZE_SMALL = 13
SIZE_LABEL = 12
SIZE_TELEMETRY = 28

WEIGHT_REGULAR = 400
WEIGHT_BOLD = 700

# Letter spacing is specified in em; QML expects pixels.
LABEL_LETTER_SPACING = round(SIZE_LABEL * 0.07, 2)
SAFETY_LETTER_SPACING = round(SIZE_BODY * 0.05, 2)

# Spacing, radius, elevation (5).
SPACE_1 = 4
SPACE_2 = 8
SPACE_3 = 12
SPACE_4 = 16
SPACE_5 = 24
SPACE_6 = 32
SPACE_7 = 48

RADIUS_SM = 3
RADIUS_MD = 6
RADIUS_LG = 10
RADIUS_PILL = 999

CONTROL_H_SM = 28
CONTROL_H_MD = 36
CONTROL_H_LG = 44

# Shadow-1 and shadow-2 are expressed as an offset, a blur-substitute
# spread and an alpha, because QML has no CSS box-shadow.
SHADOW_1_COLOR = "#14161C"
SHADOW_1_ALPHA = 0.08
SHADOW_2_ALPHA = 0.12

# Safety-critical control minimums (7).
SAFETY_MIN_HEIGHT = CONTROL_H_LG
SAFETY_MIN_WIDTH = 200


def resolve_family(candidates: list[str]) -> str:
    """Return the first installed family from a fallback stack.

    QML's ``font.family`` takes a single name, so the stacks in style guide
    section 3 are resolved once at startup against what the machine actually
    has. Requires a QGuiApplication to exist.
    """
    available = set(QFontDatabase.families())
    for name in candidates:
        if name in available:
            return name
    return candidates[-1]


def build_theme() -> dict[str, Any]:
    """Return the token table consumed by QML as the ``theme`` property."""
    return {
        "bg_app": BG_APP,
        "bg_surface": BG_SURFACE,
        "bg_raised": BG_RAISED,
        "bg_sunken": BG_SUNKEN,
        "border": BORDER,
        "border_strong": BORDER_STRONG,
        "text_primary": TEXT_PRIMARY,
        "text_secondary": TEXT_SECONDARY,
        "text_muted": TEXT_MUTED,
        "text_inverse": TEXT_INVERSE,
        "accent": ACCENT,
        "accent_hover": ACCENT_HOVER,
        "accent_active": ACCENT_ACTIVE,
        "accent_subtle": ACCENT_SUBTLE,
        "on_accent": ON_ACCENT,
        "success": SUCCESS,
        "success_hover": SUCCESS_HOVER,
        "success_bg": SUCCESS_BG,
        "warning": WARNING,
        "warning_bg": WARNING_BG,
        "danger": DANGER,
        "danger_hover": DANGER_HOVER,
        "danger_active": DANGER_ACTIVE,
        "danger_bg": DANGER_BG,
        "info": INFO,
        "info_bg": INFO_BG,
        "focus_ring": FOCUS_RING,
        "ui_families": UI_FAMILIES,
        "mono_families": MONO_FAMILIES,
        "ui_family": resolve_family(UI_FAMILIES),
        "mono_family": resolve_family(MONO_FAMILIES),
        "size_display": SIZE_DISPLAY,
        "size_h1": SIZE_H1,
        "size_h2": SIZE_H2,
        "size_h3": SIZE_H3,
        "size_body": SIZE_BODY,
        "size_small": SIZE_SMALL,
        "size_label": SIZE_LABEL,
        "size_telemetry": SIZE_TELEMETRY,
        "weight_regular": WEIGHT_REGULAR,
        "weight_bold": WEIGHT_BOLD,
        "label_letter_spacing": LABEL_LETTER_SPACING,
        "safety_letter_spacing": SAFETY_LETTER_SPACING,
        "space_1": SPACE_1,
        "space_2": SPACE_2,
        "space_3": SPACE_3,
        "space_4": SPACE_4,
        "space_5": SPACE_5,
        "space_6": SPACE_6,
        "space_7": SPACE_7,
        "radius_sm": RADIUS_SM,
        "radius_md": RADIUS_MD,
        "radius_lg": RADIUS_LG,
        "radius_pill": RADIUS_PILL,
        "control_h_sm": CONTROL_H_SM,
        "control_h_md": CONTROL_H_MD,
        "control_h_lg": CONTROL_H_LG,
        "shadow_1_color": SHADOW_1_COLOR,
        "shadow_1_alpha": SHADOW_1_ALPHA,
        "shadow_2_alpha": SHADOW_2_ALPHA,
        "safety_min_height": SAFETY_MIN_HEIGHT,
        "safety_min_width": SAFETY_MIN_WIDTH,
    }
