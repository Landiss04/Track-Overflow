// Read-only value well, style guide 6.2 input styling with the mono face.
import QtQuick

Rectangle {
    id: root

    property string text: ""
    property int pixelSize: theme.size_body

    implicitHeight: theme.control_h_md
    color: theme.bg_sunken
    border.color: theme.border_strong
    border.width: 1
    radius: theme.radius_md

    MonoText {
        anchors.left: parent.left
        anchors.leftMargin: theme.space_3
        anchors.verticalCenter: parent.verticalCenter
        text: root.text
        font.pixelSize: root.pixelSize
    }
}
