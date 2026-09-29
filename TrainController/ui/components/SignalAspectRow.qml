// Wayside signal aspect, read-only. The active aspect is filled with its
// semantic colour and every aspect keeps its text label (style guide 2).
import QtQuick
import QtQuick.Layouts

RowLayout {
    id: root

    property string aspect: ""

    spacing: theme.space_2

    Repeater {
        model: ["RED", "YELLOW", "GREEN", "SUPER GREEN"]

        delegate: Rectangle {
            id: tile

            required property string modelData

            readonly property bool active: modelData === root.aspect
            readonly property color tone: modelData === "RED" ? theme.danger
                : modelData === "YELLOW" ? theme.warning : theme.success

            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.preferredHeight: theme.control_h_lg + theme.space_3
            radius: theme.radius_md
            color: active ? tone : theme.bg_raised
            border.width: active ? 0 : 1
            border.color: theme.border

            Text {
                anchors.centerIn: parent
                text: tile.modelData
                color: tile.active ? theme.text_inverse : theme.text_muted
                font.family: theme.ui_family
                font.pixelSize: theme.size_small
                font.weight: theme.weight_bold
                font.letterSpacing: theme.label_letter_spacing
            }
        }
    }
}
