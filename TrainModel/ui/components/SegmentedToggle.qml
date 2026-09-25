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

            delegate: Rectangle {
                required property int index
                required property string modelData

                readonly property bool selected: index === root.currentIndex

                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: segmentLabel.implicitWidth + 2 * theme.space_4
                radius: theme.radius_pill
                color: selected ? theme.accent : "transparent"

                Text {
                    id: segmentLabel
                    anchors.centerIn: parent
                    text: modelData.toUpperCase()
                    color: parent.selected ? theme.on_accent : theme.text_secondary
                    font.family: theme.ui_family
                    font.pixelSize: theme.size_label
                    font.weight: theme.weight_bold
                    font.letterSpacing: theme.label_letter_spacing
                }

                MouseArea {
                    anchors.fill: parent
                    enabled: root.enabled
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.activated(index)
                }
            }
        }
    }
}
