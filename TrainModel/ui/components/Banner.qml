import QtQuick

// Mode / context banner: sunken surface strip (mockup's neutral grey,
// resolved to --bg-sunken + --border) with a bold heading and a helper
// sentence beneath.
Item {
    id: root

    property string heading: ""
    property string helper: ""

    implicitWidth: 0
    implicitHeight: col.implicitHeight + 2 * theme.space_3

    Rectangle {
        anchors.fill: parent
        color: theme.bg_sunken
        border.width: 1
        border.color: theme.border
        radius: theme.radius_lg
    }

    Column {
        id: col
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.margins: theme.space_3
        spacing: theme.space_1

        Text {
            width: parent.width
            text: root.heading
            font.family: theme.ui_family
            font.pixelSize: theme.font_body
            font.weight: Font.Bold
            color: theme.text_primary
        }

        Text {
            width: parent.width
            visible: root.helper.length > 0
            text: root.helper
            wrapMode: Text.WordWrap
            font.family: theme.ui_family
            font.pixelSize: theme.font_small
            color: theme.text_secondary
        }
    }
}
