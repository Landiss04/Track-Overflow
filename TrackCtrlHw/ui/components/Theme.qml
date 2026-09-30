pragma Singleton

import QtQuick

// Single source of truth for every visual token, per UI_Style_Guide.md §9.
// No other QML file in this module may contain a literal colour, font size,
// spacing value, radius or control height.
QtObject {
    id: theme

    // ---- 4.1 Surfaces and borders -----------------------------------------
    readonly property color bgApp: "#F4F6F8"
    readonly property color bgSurface: "#FFFFFF"
    readonly property color bgRaised: "#FFFFFF"
    readonly property color bgSunken: "#E8ECF0"
    readonly property color border: "#D5DCE3"
    readonly property color borderStrong: "#8795A3"

    // ---- 4.2 Text ---------------------------------------------------------
    readonly property color textPrimary: "#16202A"
    readonly property color textSecondary: "#4B5C6B"
    readonly property color textMuted: "#5F6B79"
    readonly property color textInverse: "#FFFFFF"

    // ---- 4.3 Accent -------------------------------------------------------
    readonly property color accent: "#1D6FD0"
    readonly property color accentHover: "#1A5FB4"
    readonly property color accentActive: "#164E96"
    readonly property color accentSubtle: "#E4EFFB"
    // Named inkOnAccent, not onAccent: QML parses an `onX` identifier as a
    // signal handler. The token is --on-accent.
    readonly property color inkOnAccent: "#FFFFFF"

    // ---- 4.4 Semantic -----------------------------------------------------
    readonly property color success: "#15803D"
    readonly property color successHover: "#126832"
    readonly property color successBg: "#EDF7F0"
    readonly property color warning: "#B45309"
    readonly property color warningBg: "#FDF2E0"
    readonly property color danger: "#C0272D"
    readonly property color dangerHover: "#A81F25"
    readonly property color dangerActive: "#8C1A1F"
    readonly property color dangerBg: "#FBE8E9"
    readonly property color info: "#4338CA"
    readonly property color infoBg: "#EAE8FB"
    readonly property color focusRing: "#1D6FD0"

    // ---- 5 Spacing --------------------------------------------------------
    readonly property int space1: 4
    readonly property int space2: 8
    readonly property int space3: 12
    readonly property int space4: 16
    readonly property int space5: 24
    readonly property int space6: 32
    readonly property int space7: 48

    // ---- 5 Radius ---------------------------------------------------------
    readonly property int radiusSm: 3
    readonly property int radiusMd: 6
    readonly property int radiusLg: 10
    readonly property int radiusPill: 999

    // ---- 5 Elevation ------------------------------------------------------
    // --shadow-1 / --shadow-2 are rgba(22,32,42,.08) and (.12). Qt Quick has no
    // box-shadow, so panels approximate shadow-1 with a tinted underlay.
    readonly property color shadowInk: "#16202A"
    readonly property real shadow1Opacity: 0.08
    readonly property real shadow2Opacity: 0.12

    // ---- 5 Control heights ------------------------------------------------
    readonly property int controlHSm: 28
    readonly property int controlHMd: 36
    readonly property int controlHLg: 44

    // ---- 3 Typography -----------------------------------------------------
    readonly property var uiFamilies: ["Helvetica Neue", "Helvetica", "Arial", "sans-serif"]
    readonly property var monoFamilies: ["Monaco", "Menlo", "Consolas", "Andale Mono", "monospace"]

    // Canvas' Context2D takes a single family name, not a CSS fallback stack.
    readonly property string uiFamily: theme.firstAvailable(theme.uiFamilies)
    readonly property string monoFamily: theme.firstAvailable(theme.monoFamilies)

    readonly property int sizeDisplay: 36
    readonly property int sizeH1: 28
    readonly property int sizeH2: 22
    readonly property int sizeH3: 18
    readonly property int sizeBody: 15
    readonly property int sizeSmall: 13
    readonly property int sizeLabel: 12
    readonly property int sizeReadout: 28

    readonly property real labelTracking: 0.07   // em, applied to the Label token
    readonly property real safetyTracking: 0.05  // em, §7 safety-critical labels

    readonly property real disabledOpacity: 0.42

    function firstAvailable(candidates) {
        var installed = Qt.fontFamilies();
        for (var i = 0; i < candidates.length; ++i) {
            if (installed.indexOf(candidates[i]) >= 0)
                return candidates[i];
        }
        return candidates[candidates.length - 1];
    }

    // Semantic token lookups, so components switch on a name rather than a hex.
    function semanticInk(kind) {
        switch (kind) {
        case "ok":
            return theme.success;
        case "warning":
            return theme.warning;
        case "fault":
            return theme.danger;
        case "info":
            return theme.info;
        case "accent":
            return theme.accent;
        default:
            return theme.textMuted;
        }
    }

    function semanticBg(kind) {
        switch (kind) {
        case "ok":
            return theme.successBg;
        case "warning":
            return theme.warningBg;
        case "fault":
            return theme.dangerBg;
        case "info":
            return theme.infoBg;
        case "accent":
            return theme.accentSubtle;
        default:
            return theme.bgSunken;
        }
    }
}
