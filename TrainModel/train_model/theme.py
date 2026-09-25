"""Design tokens for the Train Model UI.

Every colour, font, spacing, radius, and element dimension used by the QML
views resolves through this module. No literal visual value may appear in a
view; this is the single source of truth (UI Style Guide §9).

Colour, type, spacing, radius, and component tokens come from
``documents/UI_Style_Guide.md`` (light theme, normative). Element dimensions
the style guide does not cover — top-bar height, nav-rail width, card header
strip, metric tile, table row, field, and toggle-group sizes — come from the
Figma CSS exports in ``refrence-docs/``.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtGui import QFontDatabase


def _resolve_family(stack: list[str]) -> str:
    """Return the first font family in *stack* present on this system.

    Falls back to the last entry so the stack always yields a name.
    """
    available = set(QFontDatabase.families())
    for family in stack:
        if family in available:
            return family
    return stack[-1]


def build_theme() -> dict[str, Any]:
    """Return the full token dictionary for the committed light theme."""
    ui_stack = ["Helvetica Neue", "Helvetica", "Arial"]
    mono_stack = [
        "Monaco",
        "Menlo",
        "Consolas",
        "Andale Mono",
        "DejaVu Sans Mono",
        "Liberation Mono",
    ]

    tokens: dict[str, Any] = {
        # -- Typography -------------------------------------------------
        "ui_family": _resolve_family(ui_stack),
        "mono_family": _resolve_family(mono_stack),
        "weight_regular": 400,
        "weight_bold": 700,
        "font_display": 36,
        "font_h1": 28,
        "font_h2": 22,
        "font_h3": 18,
        "font_body": 15,
        "font_small": 13,
        "font_label": 12,
        # Label tracking is an em factor (Style Guide §3); views multiply by
        # the pixel size so the value stays a token, not a literal.
        "label_tracking_em": 0.07,
        "value_size": 28,  # telemetry readout value (§6.5)
        "unit_size": 13,  # unit suffix after a readout value (§6.5)

        # -- Surfaces and borders (§4.1) -------------------------------
        "bg_app": "#F4F6F8",
        "bg_surface": "#FFFFFF",
        "bg_raised": "#FFFFFF",
        "bg_sunken": "#E8ECF0",
        "border": "#D5DCE3",
        "border_strong": "#8795A3",

        # -- Text (§4.2) ------------------------------------------------
        "text_primary": "#16202A",
        "text_secondary": "#4B5C6B",
        "text_muted": "#5F6B79",
        "text_inverse": "#FFFFFF",

        # -- Accent (§4.3) ---------------------------------------------
        "accent": "#1D6FD0",
        "accent_hover": "#1A5FB4",
        "accent_active": "#164E96",
        "accent_subtle": "#E4EFFB",
        "on_accent": "#FFFFFF",

        # -- Semantic (§4.4) -------------------------------------------
        "success": "#15803D",
        "success_hover": "#126832",
        "success_bg": "#EDF7F0",
        "warning": "#B45309",
        "warning_bg": "#FDF2E0",
        "danger": "#C0272D",
        "danger_hover": "#A81F25",
        "danger_active": "#8C1A1F",
        "danger_bg": "#FBE8E9",
        "info": "#4338CA",
        "info_bg": "#EAE8FB",
        "focus_ring": "#1D6FD0",

        # -- Spacing, radius, elevation (§5) ----------------------------
        "space_1": 4,
        "space_2": 8,
        "space_3": 12,
        "space_4": 16,
        "space_5": 24,
        "space_6": 32,
        "space_7": 48,
        "radius_sm": 3,
        "radius_md": 6,
        "radius_lg": 10,
        "radius_pill": 999,
        "shadow_1": "0 1px 2px rgba(22,32,42,.08)",
        "shadow_2": "0 4px 14px rgba(22,32,42,.12)",

        # -- Control heights (§5) ---------------------------------------
        "control_h_sm": 28,
        "control_h_md": 36,
        "control_h_lg": 44,

        # -- Focus (§4.4 / §6.1) ----------------------------------------
        "focus_ring_width": 2,
        "focus_ring_offset": 2,

        # -- Status badges (§6.3) ---------------------------------------
        "badge_dot_size": 7,
        "badge_text_size": 12,

        # -- Element dimensions (Figma exports, not in the style guide) --
        "top_bar_height": 56,
        "nav_rail_width": 56,
        "nav_item_height": 44,
        "card_header_height": 30,
        "metric_tile_height": 60,
        "table_row_height": 24,
        "input_row_height": 34,
        "field_height": 28,
        "field_narrow_width": 96,
        "field_wide_width": 170,
        "toggle_group_width": 108,
        "progress_bar_height": 12,
        "icon_size": 18,
        "stroke_width": 2,
        "sublabeled_button_height": 60,
        "selector_chip_height": 30,

        # -- State styling (§6.1: disabled = 40–45% opacity) ------------
        "disabled_opacity": 0.45,

        # -- Canvas (design width 1440 held as the window minimum) ------
        "design_width": 1440,
        "design_height": 900,
    }

    return tokens
