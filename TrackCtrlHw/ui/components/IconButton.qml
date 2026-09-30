import QtQuick
import QtQuick.Controls.Basic

// Square icon-only control. Minimum interactive target is 28 px (§8), so the
// small size sits exactly on the floor. A tooltip carries the text label
// required by §2 principle 2.
Button {
    id: control

    property string glyph: ""
    property string size: "md"
    property string tip: ""

    readonly property int controlHeight: size === "sm" ? Theme.controlHSm : Theme.controlHMd

    implicitWidth: controlHeight
    implicitHeight: controlHeight
    padding: 0
    hoverEnabled: true
    opacity: enabled ? 1.0 : Theme.disabledOpacity
    Accessible.name: tip

    ToolTip.text: tip
    ToolTip.visible: tip !== "" && hovered
    ToolTip.delay: 400

    background: Rectangle {
        radius: Theme.radiusMd
        color: control.hovered ? Theme.accentSubtle : Theme.bgRaised
        border.width: 1
        border.color: Theme.borderStrong

        Rectangle {
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
        text: control.glyph
        color: Theme.textSecondary
        font.family: Theme.uiFamily
        font.pixelSize: Theme.sizeBody
        font.bold: true
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
}
