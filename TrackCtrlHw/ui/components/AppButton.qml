import QtQuick
import QtQuick.Controls.Basic

// Style Guide §6.1. Variants: primary, secondary, ghost, danger, success.
// Sizes: sm (28), md (36, default), lg (44).
Button {
    id: control

    property string variant: "secondary"
    property string size: "md"

    readonly property int controlHeight: size === "sm" ? Theme.controlHSm : size === "lg" ? Theme.controlHLg : Theme.controlHMd
    readonly property int sidePadding: size === "sm" ? Theme.space3 : size === "lg" ? Theme.space5 : Theme.space4
    readonly property int labelSize: size === "sm" ? Theme.sizeSmall : size === "lg" ? Theme.sizeH3 : Theme.sizeBody

    readonly property color fillColour: {
        if (variant === "primary")
            return control.pressed ? Theme.accentActive : control.hovered ? Theme.accentHover : Theme.accent;
        if (variant === "danger")
            return control.pressed ? Theme.dangerActive : control.hovered ? Theme.dangerHover : Theme.danger;
        if (variant === "success")
            return control.hovered ? Theme.successHover : Theme.success;
        if (variant === "ghost")
            return control.hovered ? Theme.accentSubtle : "transparent";
        return control.hovered ? Theme.accentSubtle : Theme.bgRaised;
    }

    readonly property color inkColour: {
        if (variant === "primary")
            return Theme.inkOnAccent;
        if (variant === "danger" || variant === "success")
            return Theme.textInverse;
        if (variant === "ghost")
            return Theme.textSecondary;
        return Theme.textPrimary;
    }

    implicitHeight: controlHeight
    leftPadding: sidePadding
    rightPadding: sidePadding
    topPadding: 0
    bottomPadding: 0
    hoverEnabled: true
    opacity: enabled ? 1.0 : Theme.disabledOpacity
    Accessible.name: text

    background: Rectangle {
        radius: Theme.radiusMd
        color: control.fillColour
        border.width: control.variant === "secondary" ? 1 : 0
        border.color: Theme.borderStrong

        Rectangle {
            // Focus: 2 px --focus-ring with 2 px offset (§6.1). Never removed.
            anchors.fill: parent
            anchors.margins: -3
            visible: control.visualFocus
            radius: parent.radius + 3
            color: "transparent"
            border.width: 2
            border.color: Theme.focusRing
        }
    }

    contentItem: Text {
        text: control.text
        color: control.inkColour
        font.family: Theme.uiFamily
        font.pixelSize: control.labelSize
        font.bold: true
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
}
