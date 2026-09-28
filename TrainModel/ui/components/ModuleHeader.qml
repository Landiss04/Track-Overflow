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
    property var navigationEntries: []
    property int currentNavigationIndex: -1
    signal navigationActivated(int index)

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

        RowLayout {
            Layout.alignment: Qt.AlignVCenter
            spacing: theme.space_1
            visible: root.navigationEntries.length > 0

            Repeater {
                model: root.navigationEntries

                delegate: Rectangle {
                    required property int index
                    required property string modelData

                    readonly property bool selected: index === root.currentNavigationIndex

                    implicitWidth: navigationLabel.implicitWidth + 2 * theme.space_3
                    implicitHeight: theme.control_h_md
                    radius: theme.radius_md
                    color: selected ? theme.accent_subtle : "transparent"
                    border.width: selected ? 1 : 0
                    border.color: theme.accent

                    Text {
                        id: navigationLabel
                        anchors.centerIn: parent
                        text: modelData
                        color: parent.selected ? theme.accent : theme.text_secondary
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_small
                        font.weight: parent.selected
                            ? theme.weight_bold : theme.weight_regular
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.navigationActivated(index)
                    }
                }
            }
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
