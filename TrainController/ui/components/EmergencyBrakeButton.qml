// Train Controller emergency brake, style guide 7. Oversized --danger fill,
// uppercase with 0.05em tracking. It is the one destructive control that
// acts immediately, with no confirmation step. Once engaged it stays on:
// only the office can release it, so pressing again does nothing.
import QtQuick
import QtQuick.Controls.Basic

Button {
    id: control

    property bool engaged: false

    implicitHeight: theme.safety_emphasis_height
    implicitWidth: theme.safety_min_width
    hoverEnabled: true

    background: Rectangle {
        radius: theme.radius_md
        color: control.engaged ? theme.danger_active
            : control.pressed ? theme.danger_active
            : control.hovered ? theme.danger_hover : theme.danger

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

    contentItem: Item {
        Column {
            anchors.centerIn: parent
            spacing: theme.space_3

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: control.engaged ? "EMERGENCY BRAKE ON" : "EMERGENCY BRAKE"
                color: theme.text_inverse
                font.family: theme.ui_family
                font.pixelSize: theme.size_h2
                font.weight: theme.weight_bold
                font.letterSpacing: theme.safety_letter_spacing * 2
            }

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: control.engaged
                    ? "FULL STOP · WAITING FOR THE OFFICE TO RELEASE IT"
                    : "FULL STOP · THE OFFICE MUST RELEASE IT"
                color: theme.text_inverse
                font.family: theme.ui_family
                font.pixelSize: theme.size_label
                font.weight: theme.weight_bold
                font.letterSpacing: theme.label_letter_spacing
            }
        }
    }
}
