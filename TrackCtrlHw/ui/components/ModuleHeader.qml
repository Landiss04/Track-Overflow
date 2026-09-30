import QtQuick
import QtQuick.Layouts

import "../../../ui" as Shared

// Style Guide §6.7. Every module window carries module name and instance at H3,
// the current mode badge, and the simulation clock in mono 13 px --text-muted.
Rectangle {
    id: root

    property string moduleName: ""
    property string instance: ""
    property string mode: ""
    property string modeKind: "info"
    property string faultText: ""
    property string clock: "--:--:--"
    property alias controls: controlRow.data

    implicitHeight: theme.control_h_md + 2 * theme.space_4
    color: theme.bg_raised

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: theme.space_5
        anchors.rightMargin: theme.space_5
        spacing: theme.space_4

        Text {
            text: root.instance === "" ? root.moduleName : root.moduleName + " \u2014 " + root.instance
            color: theme.text_primary
            font.family: theme.ui_family
            font.pixelSize: theme.size_h3
            font.bold: true
        }

        Shared.StatusBadge {
            variant: root.modeKind
            label: root.mode
            visible: root.mode !== ""
        }

        Shared.StatusBadge {
            variant: "fault"
            label: root.faultText
            visible: root.faultText !== ""
        }

        Item {
            Layout.fillWidth: true
        }

        RowLayout {
            id: controlRow
            spacing: theme.space_4
        }

        Text {
            text: root.clock
            color: theme.text_muted
            font.family: theme.mono_family
            font.pixelSize: theme.size_small
            font.bold: true
        }
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        color: theme.border
    }
}
