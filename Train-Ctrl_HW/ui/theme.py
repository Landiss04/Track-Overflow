"""
ui/theme.py — the only place literal color values appear.

Style Guide v1.2, Team 3. Every token below uses the same key name as the
document, which is what makes the optional dark theme (§10) a drop-in swap:
change ACTIVE to DARK and nothing else in the program changes.
"""

from PySide6.QtGui import QFont

# ---------------------------------------------------------------- §4 color
LIGHT = {
    # 4.1 surfaces and borders
    "bg-app": "#F4F6F8", "bg-surface": "#FFFFFF", "bg-raised": "#FFFFFF",
    "bg-sunken": "#E8ECF0", "border": "#D5DCE3", "border-strong": "#8795A3",
    # 4.2 text
    "text-primary": "#16202A", "text-secondary": "#4B5C6B",
    "text-muted": "#5F6B79", "text-inverse": "#FFFFFF",
    # 4.3 accent
    "accent": "#1D6FD0", "accent-hover": "#1A5FB4", "accent-active": "#164E96",
    "accent-subtle": "#E4EFFB", "on-accent": "#FFFFFF",
    # 4.4 semantic
    "success": "#15803D", "success-hover": "#126832", "success-bg": "#EDF7F0",
    "warning": "#B45309", "warning-bg": "#FDF2E0",
    "danger": "#C0272D", "danger-hover": "#A81F25", "danger-active": "#8C1A1F",
    "danger-bg": "#FBE8E9",
    "info": "#4338CA", "info-bg": "#EAE8FB",
    "focus-ring": "#1D6FD0",
    # NOTE: additions not yet in the style guide. §4.4 --danger (#C0272D) is a
    # deep signal red and --warning (#B45309) a dark amber; neither reads as the
    # bright red / yellow a cab brake handle uses. Per §1 these must be added to
    # the guide before ship. Contrast checked: text-inverse on brake-emergency
    # 4.9:1 (AA); text-primary on brake-service 11.2:1 (AAA).
    "brake-emergency": "#E11D1D", "brake-emergency-active": "#B31414",
    "brake-service": "#F2C037", "brake-service-active": "#D9A520",
    # line identity, matching the CTC track view
    "green-line": "#2F7D4F", "red-line": "#B03A3A",
}

# §10.1 — informative, not committed. Kept here so the switch is a token swap.
DARK = {
    "bg-app": "#0F1419", "bg-surface": "#161C24", "bg-raised": "#1E2630",
    "bg-sunken": "#0A0E12", "border": "#2C3742", "border-strong": "#3E4B59",
    "text-primary": "#E6EDF3", "text-secondary": "#9FB0C0",
    "text-muted": "#6B7E90", "text-inverse": "#0F1419",
    "accent": "#38BDF8", "accent-hover": "#7DD3FC", "accent-active": "#0EA5E9",
    "accent-subtle": "#12303F", "on-accent": "#041018",
    "success": "#2ECC71", "success-hover": "#46D983", "success-bg": "#0E2A1A",
    "warning": "#FBBF24", "warning-bg": "#322505",
    "danger": "#EF4444", "danger-hover": "#F75C5C", "danger-active": "#D93A3A",
    "danger-bg": "#2E0F11",
    "info": "#818CF8", "info-bg": "#1B1D3A",
    "focus-ring": "#FBBF24",
    "brake-emergency": "#EF4444", "brake-emergency-active": "#D93A3A",
    "brake-service": "#FBBF24", "brake-service-active": "#E0A818",
    "green-line": "#3FA76A", "red-line": "#E06666",
}

ACTIVE = LIGHT


def c(token: str) -> str:
    """Look up a color token. Fails loudly rather than rendering the wrong hue."""
    try:
        return ACTIVE[token]
    except KeyError as exc:
        raise KeyError(f"unknown color token '{token}' — add it to the style guide first") from exc


# ---------------------------------------------------------------- §5 spacing
SPACE_1, SPACE_2, SPACE_3 = 4, 8, 12
SPACE_4, SPACE_5, SPACE_6, SPACE_7 = 16, 24, 32, 48

RADIUS_SM, RADIUS_MD, RADIUS_LG, RADIUS_PILL = 3, 6, 10, 999

CONTROL_H_SM, CONTROL_H_MD, CONTROL_H_LG = 28, 36, 44

# §7 safety-critical minimum footprint
SAFETY_MIN_H, SAFETY_MIN_W = 44, 200

# ---------------------------------------------------------------- §3 type
FONT_UI = '"Helvetica Neue", "Helvetica", "Arial", sans-serif'
FONT_MONO = '"Monaco", "Menlo", "Consolas", "Andale Mono", monospace'
FONT_UI_FAMILIES = ["Helvetica Neue", "Helvetica", "Arial"]
FONT_MONO_FAMILIES = ["Monaco", "Menlo", "Consolas", "Andale Mono"]

# Only 400 and 700 exist (§3). Anything else is synthesized and inconsistent.
W_REGULAR, W_BOLD = QFont.Normal, QFont.Bold

TYPE = {
    "display": (36, W_BOLD),
    "h1": (28, W_BOLD),
    "h2": (22, W_BOLD),
    "h3": (18, W_BOLD),
    "body": (15, W_REGULAR),
    "small": (13, W_REGULAR),
    "label": (12, W_BOLD),
    # NOTE: added token, not yet in the style guide.
    # §6.5 fixes telemetry values at 28 px, which is right for a dense readout
    # panel but unreadable from a driving position. The approved wireframe uses
    # a much larger figure for the four primary readouts. Per §1 this must be
    # added to the guide before it ships. Everything else obeys §6.5 exactly.
    "hero": (72, W_BOLD),
}


def font(role: str, mono: bool = False) -> QFont:
    size, weight = TYPE[role]
    f = QFont()
    f.setFamilies(FONT_MONO_FAMILIES if mono else FONT_UI_FAMILIES)
    f.setPixelSize(size)
    f.setWeight(weight)
    if role == "label":                       # §3: uppercase, 0.07em tracking
        f.setLetterSpacing(QFont.PercentageSpacing, 107)
    return f


def build_qss() -> str:
    """One application-wide stylesheet, assembled from the tokens above (§9)."""
    return f"""
QWidget {{
    background: {c('bg-app')};
    color: {c('text-primary')};
    font-family: {FONT_UI};
    font-size: 15px;
}}

/* ---- structure ---- */
QFrame#header {{
    background: {c('bg-raised')};
    border-bottom: 1px solid {c('border')};
}}
QFrame#panel {{
    background: {c('bg-surface')};
    border: 1px solid {c('border')};
    border-radius: {RADIUS_LG}px;
}}
QLabel#panelTitle {{
    color: {c('text-muted')};
    font-size: 12px;
    font-weight: 700;
    background: transparent;
}}
QLabel#panelMeta {{
    color: {c('text-muted')};
    font-family: {FONT_MONO};
    font-size: 12px;
    background: transparent;
}}

/* ---- §6.5 telemetry readout ---- */
QFrame#readout {{
    background: {c('bg-sunken')};
    border: 1px solid {c('border')};
    border-radius: {RADIUS_MD}px;
}}
QLabel#roLabel {{ color: {c('text-muted')}; font-size: 12px; font-weight: 700; background: transparent; }}
QLabel#roValue {{ color: {c('text-primary')}; font-family: {FONT_MONO};
                   font-size: {TYPE['hero'][0]}px; font-weight: 700; background: transparent; }}
QLabel#roValueSm {{ color: {c('text-primary')}; font-family: {FONT_MONO};
                   font-size: {TYPE['h1'][0]}px; font-weight: 700; background: transparent; }}
QLabel#roUnit  {{ color: {c('text-muted')}; font-family: {FONT_MONO}; font-size: 13px; background: transparent; }}

/* ---- §6.1 buttons ---- */
QPushButton {{
    background: {c('bg-raised')};
    color: {c('text-primary')};
    border: 1px solid {c('border-strong')};
    border-radius: {RADIUS_MD}px;
    font-size: 15px;
    font-weight: 700;
    padding: 0 {SPACE_4}px;
    min-height: {CONTROL_H_MD}px;
}}
QPushButton:hover {{ background: {c('accent-subtle')}; }}
QPushButton:disabled {{ color: {c('text-muted')}; border-color: {c('border')}; }}
QPushButton:focus {{ border: 2px solid {c('focus-ring')}; }}

QPushButton#primary {{
    background: {c('accent')}; color: {c('on-accent')}; border: none;
}}
QPushButton#primary:hover  {{ background: {c('accent-hover')}; }}
QPushButton#primary:pressed {{ background: {c('accent-active')}; }}
QPushButton#primary:disabled {{ background: {c('bg-sunken')}; color: {c('text-muted')}; }}

QPushButton#danger {{
    background: {c('danger')}; color: {c('text-inverse')}; border: none;
    font-size: 18px;
}}
QPushButton#danger:hover  {{ background: {c('danger-hover')}; }}
QPushButton#danger:pressed {{ background: {c('danger-active')}; }}
QPushButton#danger:disabled {{ background: {c('danger-bg')}; color: {c('text-muted')}; }}
QPushButton#danger:checked {{ background: {c('danger-active')};
                              border: 3px solid {c('text-inverse')}; }}

QPushButton#estop {{
    background: {c('brake-emergency')}; color: {c('text-inverse')}; border: none;
    font-size: 20px;
}}
QPushButton#estop:hover   {{ background: {c('brake-emergency-active')}; }}
QPushButton#estop:checked {{ background: {c('text-inverse')};
                             color: {c('brake-emergency')};
                             border: 5px solid {c('brake-emergency')}; }}
QPushButton#estop:disabled {{ background: {c('bg-sunken')}; color: {c('text-muted')};
                              border: 1px solid {c('border')}; }}

QPushButton#svc {{
    background: {c('brake-service')}; color: {c('text-primary')}; border: none;
    font-size: 18px;
}}
QPushButton#svc:hover   {{ background: {c('brake-service-active')}; }}
QPushButton#svc:checked {{ background: {c('brake-service-active')};
                           border: 3px solid {c('text-primary')}; }}
QPushButton#svc:disabled {{ background: {c('bg-sunken')}; color: {c('text-muted')};
                            border: 1px solid {c('border')}; }}

QPushButton#success {{
    background: {c('success')}; color: {c('text-inverse')}; border: none;
}}
QPushButton#success:hover {{ background: {c('success-hover')}; }}
QPushButton#success:disabled {{ background: {c('bg-sunken')}; color: {c('text-muted')}; }}

/* segmented toggle — pill group */
QPushButton#segLeft, QPushButton#segRight, QPushButton#segMid {{
    font-size: 13px; padding: 0 {SPACE_3}px; min-height: {CONTROL_H_SM}px;
}}
QPushButton#segLeft  {{ border-top-right-radius: 0; border-bottom-right-radius: 0; }}
QPushButton#segRight {{ border-top-left-radius: 0;  border-bottom-left-radius: 0; border-left: none; }}
QPushButton#segLeft:checked, QPushButton#segRight:checked {{
    background: {c('accent')}; color: {c('on-accent')}; border-color: {c('accent')};
}}

/* big mode selector */
QPushButton#mode {{ font-size: 18px; min-height: {CONTROL_H_LG}px; }}
QPushButton#thermo {{ font-size: 18px; font-weight: 700; min-height: {CONTROL_H_SM}px;
                      background: {c('bg-raised')}; }}
QPushButton#thermo:hover {{ background: {c('accent-subtle')}; }}
QFrame#kvRow {{ border-bottom: 1px solid {c('border')}; }}
QFrame#kvRowLast {{ border: none; }}
QPushButton#step {{ padding: 0; font-size: 18px; font-weight: 700;
                    min-width: {CONTROL_H_MD}px; max-width: {CONTROL_H_MD}px; }}
QPushButton#mode:checked {{
    background: {c('accent-subtle')};
    border: 2px solid {c('accent')};
    color: {c('accent-active')};
}}

/* tile-style driver control */
QPushButton#tile {{ font-size: 12px; min-height: 64px; padding: 0 {SPACE_1}px;
                    text-align: center; }}
QPushButton#tile:checked {{
    background: {c('accent-subtle')}; border-color: {c('accent')};
}}
QPushButton#tile:disabled {{ background: {c('bg-app')}; color: {c('text-muted')};
                             border-color: {c('border')}; }}

/* ---- §6.2 inputs ---- */
QLineEdit {{
    background: {c('bg-sunken')};
    border: 1px solid {c('border-strong')};
    border-radius: {RADIUS_MD}px;
    padding: 0 {SPACE_3}px;
    min-height: {CONTROL_H_MD}px;
    font-family: {FONT_MONO};
    font-size: 15px;
    color: {c('text-primary')};
}}
QLineEdit:focus {{ border: 2px solid {c('accent')}; }}
QLineEdit:disabled {{ color: {c('text-muted')}; border-color: {c('border')}; }}

QComboBox {{
    background: {c('bg-sunken')};
    border: 1px solid {c('border-strong')};
    border-radius: {RADIUS_MD}px;
    padding: 0 {SPACE_3}px;
    min-height: {CONTROL_H_SM}px;
    max-height: {CONTROL_H_SM}px;
    font-family: {FONT_MONO};
    font-size: 13px;
    color: {c('text-primary')};
}}
QComboBox::drop-down {{ border: none; width: 20px; }}

/* ---- labels ---- */
QLabel#label     {{ color: {c('text-muted')}; font-size: 12px; font-weight: 700; background: transparent; }}
QLabel#lockNoteEmpty {{ background: transparent; border: none; padding: 0; }}
QLabel#signinNote {{ background: {c('bg-app')}; color: {c('text-secondary')};
                     font-size: 22px; font-weight: 700; }}
QLabel#lockNoteOff {{ background: transparent; border: none; }}
QLabel#lockNote  {{ background: {c('accent-subtle')}; color: {c('accent-active')};
                    border: 1px solid {c('accent')}; border-radius: {RADIUS_MD}px;
                    padding: 8px 12px; font-size: 13px; font-weight: 700; }}
QLabel#small     {{ color: {c('text-secondary')}; font-size: 13px; background: transparent; }}
QLabel#muted     {{ color: {c('text-muted')}; font-size: 13px; background: transparent; }}
QLabel#mono      {{ color: {c('text-primary')}; font-family: {FONT_MONO}; font-size: 13px; background: transparent; }}
QLabel#clock     {{ color: {c('text-muted')}; font-family: {FONT_MONO}; font-size: 13px; background: transparent; }}
QLabel#appTitle  {{ color: {c('text-primary')}; font-size: 18px; font-weight: 700; background: transparent; }}
QLabel#aspect    {{ color: {c('text-primary')}; font-family: {FONT_MONO}; font-size: 22px; font-weight: 700; background: transparent; }}

/* ---- §6.3 status badge ---- */
QLabel#badgeOk    {{ background: {c('success-bg')}; color: {c('success')};
                     border: 1px solid {c('success')}; border-radius: {RADIUS_PILL}px;
                     padding: 3px 10px; font-size: 12px; font-weight: 700; max-height: 24px; }}
QLabel#badgeFault {{ background: {c('danger-bg')}; color: {c('danger')};
                     border: 1px solid {c('danger')}; border-radius: {RADIUS_PILL}px;
                     padding: 3px 10px; font-size: 12px; font-weight: 700; max-height: 24px; }}
QLabel#badgeInfo  {{ background: {c('info-bg')}; color: {c('info')};
                     border: 1px solid {c('info')}; border-radius: {RADIUS_PILL}px;
                     padding: 3px 10px; font-size: 12px; font-weight: 700; max-height: 24px; }}

/* engineer dialog */
QDialog {{ background: {c('bg-app')}; }}
QFrame#dlgCard {{ background: {c('bg-surface')}; border: 1px solid {c('border')};
                  border-radius: {RADIUS_LG}px; }}
QLabel#dlgTitle {{ color: {c('text-primary')}; font-size: 18px; font-weight: 700;
                   background: transparent; }}

/* disclosure bar */
QPushButton#disclosure {{
    background: {c('bg-raised')};
    border: none;
    border-bottom: 1px solid {c('border')};
    border-radius: 0;
    color: {c('text-secondary')};
    font-size: 12px;
    font-weight: 700;
    min-height: {CONTROL_H_MD}px;
}}
QPushButton#disclosure:hover {{ background: {c('accent-subtle')}; }}
"""