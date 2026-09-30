import QtQuick
import QtQuick.Layouts

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

    implicitHeight: Theme.controlHMd + 2 * Theme.space4
    color: Theme.bgRaised

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.space5
        anchors.rightMargin: Theme.space5
        spacing: Theme.space4

        Text {
            text: root.instance === "" ? root.moduleName : root.moduleName + " \u2014 " + root.instance
            color: Theme.textPrimary
            font.family: Theme.uiFamily
            font.pixelSize: Theme.sizeH3
            font.bold: true
        }

        StatusBadge {
            kind: root.modeKind
            text: root.mode
            visible: root.mode !== ""
        }

        StatusBadge {
            kind: "fault"
            text: root.faultText
            visible: root.faultText !== ""
        }

        Item {
            Layout.fillWidth: true
        }

        RowLayout {
            id: controlRow
            spacing: Theme.space4
        }

        Text {
            text: root.clock
            color: Theme.textMuted
            font.family: Theme.monoFamily
            font.pixelSize: Theme.sizeSmall
            font.bold: true
        }
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        color: Theme.border
    }
}
