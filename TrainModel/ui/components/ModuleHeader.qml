// Module window header, style guide 6.7. Module name and instance at H3, the
// current mode badge, and the simulation clock in mono at 13 px muted.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string moduleName: ""
    property string instance: ""
    property string mode: ""
    property string line: ""
    property string clock: ""
    property bool faulted: false

    implicitHeight: theme.control_h_lg + 2 * theme.space_3
    color: theme.bg_raised

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        implicitHeight: 1
        color: theme.border
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: theme.space_5
        anchors.rightMargin: theme.space_5
        spacing: theme.space_4

        Text {
            text: root.instance === ""
                ? root.moduleName : root.moduleName + " \u2014 " + root.instance
            color: theme.text_primary
            font.family: theme.ui_family
            font.pixelSize: theme.size_h3
            font.weight: theme.weight_bold
        }

        StatusBadge {
            label: root.mode
            variant: "info"
            visible: root.mode !== ""
        }

        StatusBadge {
            label: "E-brake"
            variant: "fault"
            visible: root.faulted
        }

        Item { Layout.fillWidth: true }

        MonoText {
            text: root.line
            color: theme.text_muted
            visible: root.line !== ""
        }

        MonoText {
            text: root.clock
            color: theme.text_muted
        }
    }
}
