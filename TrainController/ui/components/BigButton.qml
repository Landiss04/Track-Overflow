// Oversized secondary button for the cab, style guide 6.1 (secondary variant)
// sized up for a low-proficiency driver. Optional second line explains why
// the button is, or is not, available.
import QtQuick
import QtQuick.Controls.Basic

Button {
    id: control

    property string subtitle: ""

    implicitHeight: theme.control_h_lg
    implicitWidth: labels.implicitWidth + 2 * theme.space_4
    hoverEnabled: true
    opacity: enabled ? 1.0 : 0.42

    background: Rectangle {
        radius: theme.radius_md
        color: !control.enabled ? theme.bg_raised
            : control.pressed || control.hovered ? theme.accent_subtle
            : theme.bg_raised
        border.width: 1
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

    contentItem: Item {
        implicitWidth: labels.implicitWidth
        implicitHeight: labels.implicitHeight

        Column {
            id: labels

            anchors.centerIn: parent
            spacing: theme.space_1

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: control.text
                color: theme.text_primary
                font.family: theme.ui_family
                font.pixelSize: theme.size_h3
                font.weight: theme.weight_bold
                font.letterSpacing: theme.safety_letter_spacing
            }

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                visible: control.subtitle !== ""
                text: control.subtitle.toUpperCase()
                color: theme.text_muted
                font.family: theme.ui_family
                font.pixelSize: theme.size_label
                font.weight: theme.weight_bold
                font.letterSpacing: theme.label_letter_spacing
            }
        }
    }
}
