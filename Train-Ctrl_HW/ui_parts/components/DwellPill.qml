// The station dwell as a header pill (REQUIREMENTS.md M6): filled in
// the info colour when the dwell starts, emptying to white as it runs.
// The same shape as a StatusBadge, at a fixed width, so nothing beside
// it moves as it drains. The label is drawn twice, white over the
// filled part and in the info colour over the empty part, so it reads
// the whole way.
import QtQuick

Rectangle {
    id: root

    //: Share of the dwell still to run, 1 to 0.
    property real share: 0
    property string label: qsTr("Station dwell")

    implicitWidth: 150
    implicitHeight: theme.control_h_sm
    radius: height / 2
    color: theme.bg_surface
    border.color: theme.info
    border.width: 1
    clip: true

    Rectangle {
        id: fill
        width: root.width * Math.max(0, Math.min(1, root.share))
        height: root.height
        radius: root.radius
        color: theme.info
    }

    Text {
        anchors.centerIn: parent
        text: root.label.toUpperCase()
        color: theme.info
        font.family: theme.ui_family
        font.pixelSize: theme.size_label
        font.weight: theme.weight_bold
        font.letterSpacing: theme.label_letter_spacing
    }

    Item {
        width: fill.width
        height: root.height
        clip: true

        Text {
            x: (root.width - width) / 2
            anchors.verticalCenter: parent.verticalCenter
            text: root.label.toUpperCase()
            color: theme.bg_surface
            font.family: theme.ui_family
            font.pixelSize: theme.size_label
            font.weight: theme.weight_bold
            font.letterSpacing: theme.label_letter_spacing
        }
    }
}
