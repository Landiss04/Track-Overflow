import QtQuick
import QtQuick.Controls

// Mode / context banner: sunken surface strip (mockup's neutral grey,
// resolved to --bg-sunken + --border) with a bold heading. Explanatory
// copy goes in `tooltip` and appears on hover instead of as a second line.
Item {
    id: root

    property string heading: ""
    property string tooltip: ""

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
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        enabled: root.tooltip.length > 0
        onEntered: ToolTip.show(root.tooltip, mouseX, mouseY, root)
        onPositionChanged: ToolTip.show(root.tooltip, mouseX, mouseY, root)
        onExited: ToolTip.hide()
    }
}
