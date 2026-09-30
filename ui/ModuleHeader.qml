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
            text: root.moduleName
            color: theme.text_primary
            font.family: theme.ui_family
            font.pixelSize: theme.size_h3
            font.weight: theme.weight_bold
        }

        MonoText {
            text: root.instance
            visible: root.instance !== ""
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

                delegate: AppButton {
                    required property int index
                    required property string modelData
                    readonly property bool selected: index === root.currentNavigationIndex
                    size: "small"
                    implicitHeight: theme.control_h_md
                    text: modelData
                    variant: "ghost"
                    background: Rectangle {
                        radius: theme.radius_md
                        color: parent.selected || parent.hovered
                            ? theme.accent_subtle : "transparent"
                        border.width: parent.visualFocus ? 2 : parent.selected ? 1 : 0
                        border.color: parent.visualFocus ? theme.focus_ring : theme.accent
                    }
                    Accessible.name: modelData
                    onClicked: root.navigationActivated(index)
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
