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

    readonly property int controlHeight: size === "sm" ? theme.control_h_sm : theme.control_h_md

    implicitWidth: controlHeight
    implicitHeight: controlHeight
    padding: 0
    hoverEnabled: true
    opacity: enabled ? 1.0 : 0.42
    Accessible.name: tip

    ToolTip.text: tip
    ToolTip.visible: tip !== "" && hovered
    ToolTip.delay: 400

    background: Rectangle {
        radius: theme.radius_md
        color: control.hovered ? theme.accent_subtle : theme.bg_raised
        border.width: 1
        border.color: theme.border_strong

        Rectangle {
            anchors.fill: parent
            anchors.margins: -3
            visible: control.visualFocus
            radius: parent.radius + 3
            color: "transparent"
            border.width: 2
            border.color: theme.focus_ring
        }
    }

    contentItem: Text {
        text: control.glyph
        color: theme.text_secondary
        font.family: theme.ui_family
        font.pixelSize: theme.size_body
        font.bold: true
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
}
