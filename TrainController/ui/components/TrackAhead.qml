// Track-ahead strip: blocks stacked with the train's block at the bottom and
// the direction of travel shown by an arrow up the left side.
import QtQuick
import QtQuick.Layouts

Item {
    id: root

    property var blocks: []
    property int slots: 6

    readonly property real gap: theme.space_2
    readonly property real tileHeight: (height - gap * (slots - 1)) / slots
    readonly property real railX: theme.space_3

    function formatFeet(value) {
        return Number(value).toLocaleString(Qt.locale("en_US"), "f", 0) + " ft";
    }

    // Direction-of-travel arrow, from the train marker up to the next block.
    Rectangle {
        id: rail

        x: root.railX
        width: 2
        anchors.top: arrowHead.verticalCenter
        anchors.bottom: parent.bottom
        color: theme.text_secondary
    }

    Text {
        id: arrowHead

        anchors.horizontalCenter: rail.horizontalCenter
        y: Math.max(0, root.height - stack.height + root.tileHeight
            + root.gap - height / 2)
        text: "▲"
        color: theme.text_secondary
        font.pixelSize: theme.size_small
    }

    Rectangle {
        anchors.horizontalCenter: rail.horizontalCenter
        anchors.bottom: parent.bottom
        width: theme.space_3
        height: root.tileHeight * 0.4
        radius: theme.radius_sm
        color: theme.info
    }

    Column {
        id: stack

        anchors.left: parent.left
        anchors.leftMargin: root.railX + theme.space_7 - theme.space_3
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        spacing: root.gap

        Repeater {
            model: root.blocks

            delegate: RowLayout {
                required property var modelData

                width: stack.width
                height: root.tileHeight
                spacing: theme.space_4

                TrackBlockTile {
                    Layout.preferredWidth: stack.width * 0.72
                    Layout.fillHeight: true
                    blockId: modelData.block_id
                    note: modelData.note
                    kind: modelData.state
                }

                MonoText {
                    Layout.fillWidth: true
                    text: modelData.distance_ft >= 0
                        ? root.formatFeet(modelData.distance_ft) : ""
                    color: theme.text_secondary
                    font.pixelSize: theme.size_body
                }
            }
        }
    }
}
