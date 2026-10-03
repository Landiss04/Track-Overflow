// Track-ahead strip: the occupied block at the bottom and the blocks ahead
// stacked above it, with the direction of travel shown by an arrow up the
// left side. Each row is a shared TrackBlock (style guide 6.4) with the
// block's section, any station, the distance to it, and an End of
// authority badge on the authority block. There is no shared equivalent,
// so this composition stays local to the Train Controller.
import QtQuick
import QtQuick.Layouts
import "../../../ui"

Item {
    id: root

    property var blocks: []
    property int slots: 6

    readonly property real gap: theme.space_2
    readonly property real rowHeight: (height - gap * (slots - 1)) / slots
    readonly property real railX: theme.space_3

    function formatFeet(value) {
        return Number(value).toLocaleString(Qt.locale("en_US"), "f", 0) + " ft";
    }

    function sideText(side) {
        return side === "BOTH" ? "both sides"
            : side === "LEFT" ? "left" : side === "RIGHT" ? "right" : "";
    }

    // Direction-of-travel arrow, from the train marker up to the next block.
    Rectangle {
        id: rail

        x: root.railX
        width: 2
        visible: root.blocks.length > 1
        anchors.top: arrowHead.verticalCenter
        anchors.bottom: parent.bottom
        color: theme.text_secondary
    }

    Text {
        id: arrowHead

        anchors.horizontalCenter: rail.horizontalCenter
        visible: rail.visible
        y: Math.max(0, root.height - stack.height + root.rowHeight
            + root.gap - height / 2)
        text: "▲"
        color: theme.text_secondary
        font.pixelSize: theme.size_small
    }

    Rectangle {
        anchors.horizontalCenter: rail.horizontalCenter
        anchors.bottom: parent.bottom
        width: theme.space_3
        height: root.rowHeight * 0.5
        radius: theme.radius_sm
        color: theme.info
    }

    Column {
        id: stack

        anchors.left: parent.left
        anchors.leftMargin: root.railX + theme.space_6
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        spacing: root.gap

        Repeater {
            model: root.blocks

            delegate: RowLayout {
                required property var modelData

                width: stack.width
                height: root.rowHeight
                spacing: theme.space_4

                TrackBlock {
                    Layout.preferredWidth: 150
                    Layout.fillHeight: true
                    blockId: modelData.block_id
                    occupancy: modelData.occupancy
                }

                // Zero preferred width so every row's info column gets the
                // same share and the distance column lines up.
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    spacing: 2

                    HelperText {
                        Layout.fillWidth: true
                        text: "Section " + modelData.section
                    }

                    MonoText {
                        Layout.fillWidth: true
                        visible: modelData.station !== ""
                        text: modelData.station + " · platform "
                            + root.sideText(modelData.platform_side)
                        font.weight: theme.weight_bold
                        elide: Text.ElideRight
                    }

                    StatusBadge {
                        visible: modelData.is_authority
                        variant: "warning"
                        label: "End of authority"
                    }
                }

                MonoText {
                    Layout.preferredWidth: 80
                    horizontalAlignment: Text.AlignRight
                    text: modelData.distance_ft >= 0
                        ? root.formatFeet(modelData.distance_ft) : "Here"
                    color: theme.text_secondary
                }
            }
        }
    }
}
