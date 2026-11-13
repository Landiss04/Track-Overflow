// One block on the track-ahead strip, style guide 6.4. The train's block is
// Occupied (--info), a closed block is --warning, and free blocks are
// --bg-raised with a --border-strong outline. The block where the train
// must stop carries a heavy top rule.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string blockId: ""
    property string note: ""
    // current | clear | station | stop | closed
    property string kind: "clear"

    readonly property bool filled: kind === "current" || kind === "closed"

    radius: theme.radius_sm
    color: kind === "current" ? theme.info
        : kind === "closed" ? theme.warning : theme.bg_raised
    border.width: filled ? 0 : 1
    border.color: theme.border_strong

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: theme.space_1
        visible: root.kind === "stop"
        color: theme.text_primary
    }

    ColumnLayout {
        anchors.left: parent.left
        anchors.leftMargin: theme.space_4
        anchors.verticalCenter: parent.verticalCenter
        spacing: theme.space_2

        MonoText {
            text: root.blockId
            color: root.filled ? theme.text_inverse : theme.text_primary
            font.pixelSize: theme.size_body
            font.weight: theme.weight_bold
        }

        Text {
            text: root.note
            color: root.filled ? theme.text_inverse : theme.text_secondary
            font.family: theme.ui_family
            font.pixelSize: theme.size_label
            font.weight: theme.weight_bold
            font.letterSpacing: theme.label_letter_spacing
        }
    }
}
