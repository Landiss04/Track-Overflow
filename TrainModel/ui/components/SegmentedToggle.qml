// Toggle group, style guide 5 (--radius-pill) and 6.1. The selected segment
// carries the accent fill; the label is always present.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property var options: []
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

            delegate: AppButton {
                required property int index
                required property string modelData
                readonly property bool selected: index === root.currentIndex
                Layout.fillWidth: true
                size: "small"
                implicitHeight: theme.control_h_sm
                text: modelData
                variant: selected ? "primary" : "ghost"
                Accessible.name: modelData
                onClicked: root.activated(index)
            }
        }
    }
}
