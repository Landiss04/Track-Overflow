import QtQuick

// Read-only value well: sunken field with a mono value (Style Guide §6.2
// input styling, minus interaction). Used where the mockup shows a
// standalone bordered readout (e.g. direction of travel). No focus, no
// cursor, no click target.
Item {
    id: root

    property string value: ""

    implicitWidth: 0
    implicitHeight: theme.field_height

    Rectangle {
        anchors.fill: parent
        color: theme.bg_sunken
        border.width: 1
        border.color: theme.border_strong
        radius: theme.radius_md
    }

    Text {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: theme.space_3
        anchors.verticalCenter: parent.verticalCenter
        text: root.value
        elide: Text.ElideRight
        font.family: theme.mono_family
        font.pixelSize: theme.font_body
        color: theme.text_primary
    }
}
