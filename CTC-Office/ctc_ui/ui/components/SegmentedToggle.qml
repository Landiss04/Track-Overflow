// Toggle group, style guide 5 (--radius-pill) and 6.1. The selected
// segment carries the accent fill; the label is always present. Each
// segment is keyboard reachable (Tab, then Space or Enter) with a visible
// --focus-ring, per style guide 8.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property var options: []
    // -1 means no segment is selected yet.
    property int currentIndex: 0
    signal activated(int index)

    implicitHeight: theme.control_h_md
    implicitWidth: row.implicitWidth + 2 * theme.space_1
    radius: theme.radius_pill
    color: theme.bg_sunken
    border.color: theme.border_strong
    border.width: 1
    opacity: enabled ? 1.0 : 0.42

    RowLayout {
        id: row
        anchors.fill: parent
        anchors.margins: theme.space_1
        spacing: 0

        Repeater {
            model: root.options

            delegate: Rectangle {
                id: segment

                required property int index
                required property string modelData

                readonly property bool selected: index === root.currentIndex

                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: segmentLabel.implicitWidth
                    + 2 * theme.space_4
                radius: theme.radius_pill
                color: selected ? theme.accent : "transparent"
                activeFocusOnTab: root.enabled

                Accessible.role: Accessible.Button
                Accessible.name: segment.modelData
                Accessible.checkable: true
                Accessible.checked: segment.selected

                Keys.onSpacePressed: root.activated(segment.index)
                Keys.onReturnPressed: root.activated(segment.index)
                Keys.onEnterPressed: root.activated(segment.index)

                Text {
                    id: segmentLabel
                    anchors.centerIn: parent
                    // Toggle segments are buttons, so they follow the
                    // sentence-case button rule rather than the Label
                    // token.
                    text: segment.modelData
                    color: segment.selected
                        ? theme.on_accent : theme.text_secondary
                    font.family: theme.ui_family
                    font.pixelSize: theme.size_small
                    font.weight: theme.weight_bold
                }

                Rectangle {
                    anchors.fill: parent
                    anchors.margins: -2
                    visible: segment.activeFocus
                    color: "transparent"
                    radius: theme.radius_pill
                    border.width: 2
                    border.color: theme.focus_ring
                }

                MouseArea {
                    anchors.fill: parent
                    enabled: root.enabled
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.activated(segment.index)
                }
            }
        }
    }
}
