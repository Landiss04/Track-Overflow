// Buttons, style guide 6.1. Hover, pressed, disabled and focus states are
// mandatory; the focus indicator is never removed.
import QtQuick
import QtQuick.Controls.Basic

Button {
    id: control

    // primary | secondary | ghost | danger | success
    property string variant: "secondary"
    // small | medium | large
    property string size: "medium"
    property string tooltip: ""          // optional hover text (native ToolTip)

    readonly property int hPadding: size === "small" ? theme.space_3
        : size === "large" ? theme.space_5 : theme.space_4
    readonly property int labelSize: size === "small" ? theme.size_small
        : size === "large" ? theme.size_h3 : theme.size_body
    readonly property bool filled: variant === "primary" || variant === "danger"
        || variant === "success"

    readonly property color restFill: variant === "primary" ? theme.accent
        : variant === "danger" ? theme.danger
        : variant === "success" ? theme.success
        : variant === "ghost" ? "transparent" : theme.bg_raised
    readonly property color hoverFill: variant === "primary" ? theme.accent_hover
        : variant === "danger" ? theme.danger_hover
        : variant === "success" ? theme.success_hover
        : variant === "ghost" ? theme.accent_subtle : theme.accent_subtle
    readonly property color pressFill: variant === "primary" ? theme.accent_active
        : variant === "danger" ? theme.danger_active
        : variant === "success" ? theme.success_hover
        : variant === "ghost" ? theme.accent_subtle : theme.accent_subtle
    readonly property color labelColor: variant === "primary" ? theme.on_accent
        : filled ? theme.text_inverse
        : variant === "ghost" ? theme.text_secondary : theme.text_primary

    implicitHeight: size === "small" ? theme.control_h_sm
        : size === "large" ? theme.control_h_lg : theme.control_h_md
    implicitWidth: label.implicitWidth + 2 * hPadding
    leftPadding: hPadding
    rightPadding: hPadding
    hoverEnabled: true
    opacity: enabled ? 1.0 : 0.42

    background: Rectangle {
        radius: theme.radius_md
        color: !control.enabled ? control.restFill
            : control.pressed ? control.pressFill
            : control.hovered ? control.hoverFill : control.restFill
        border.width: control.variant === "secondary" ? 1 : 0
        border.color: theme.border_strong

        Rectangle {
            anchors.fill: parent
            anchors.margins: -2
            visible: control.visualFocus
            color: "transparent"
            radius: theme.radius_md + 2
            border.width: 2
            border.color: theme.focus_ring
        }
    }

    contentItem: Text {
        id: label
        text: control.text
        color: control.labelColor
        font.family: theme.ui_family
        font.pixelSize: control.labelSize
        font.weight: theme.weight_bold
        font.letterSpacing: control.font.letterSpacing
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    // Tooltip rides the button's own hover state, so it never blocks clicks.
    onHoveredChanged: {
        if (control.tooltip === "") return
        if (control.hovered)
            ToolTip.show(control.tooltip, 0, 0, control)
        else
            ToolTip.hide()
    }
}
