// Two-state switch for a boolean input. The state is written as a word
// inside the track as well as shown by the knob, so it never relies on
// position or colour alone (style guide 4.5).
import QtQuick
import QtQuick.Controls.Basic

Item {
    id: root

    property bool checked: false
    property string onText: qsTr("ON")
    property string offText: qsTr("OFF")
    signal toggled(bool value)

    implicitWidth: 104
    implicitHeight: theme.control_h_md
    opacity: enabled ? 1.0 : 0.42
    activeFocusOnTab: true

    Keys.onSpacePressed: root.toggled(!root.checked)
    Keys.onReturnPressed: root.toggled(!root.checked)

    Rectangle {
        anchors.fill: parent
        radius: theme.radius_pill
        color: root.checked ? theme.accent : theme.bg_sunken
        border.color: root.checked ? theme.accent : theme.border_strong
        border.width: 1

        Rectangle {
            anchors.fill: parent
            anchors.margins: -2
            visible: root.activeFocus
            color: "transparent"
            radius: theme.radius_pill
            border.width: 2
            border.color: theme.focus_ring
        }

        Rectangle {
            id: knob
            width: parent.height - 8
            height: width
            radius: width / 2
            y: 4
            x: root.checked ? parent.width - width - 4 : 4
            color: theme.bg_surface
            border.color: theme.border_strong
            border.width: 1
        }

        Text {
            anchors.verticalCenter: parent.verticalCenter
            x: root.checked ? 12 : parent.width - width - 12
            text: root.checked ? root.onText : root.offText
            color: root.checked ? theme.on_accent : theme.text_secondary
            font.family: theme.ui_family
            font.pixelSize: theme.size_label
            font.weight: theme.weight_bold
        }
    }

    MouseArea {
        anchors.fill: parent
        enabled: root.enabled
        cursorShape: Qt.PointingHandCursor
        onClicked: {
            root.forceActiveFocus();
            root.toggled(!root.checked);
        }
    }
}
