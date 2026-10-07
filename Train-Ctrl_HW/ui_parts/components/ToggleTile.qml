// Door, light and headlight tile. The label states the action in words
// and the dot repeats the state in colour, so neither carries it alone.
// A shared AppButton underneath, so hover, press, disabled and focus
// behave exactly like every other button in the system.
import QtQuick
import QtQuick.Layouts
import "../../../ui"

AppButton {
    id: tile

    property bool on: false
    // Theme key the dot uses while the tile is on.
    property string tone: "success"

    variant: "secondary"
    implicitHeight: theme.control_h_lg
    Accessible.name: text

    background: Rectangle {
        radius: theme.radius_md
        color: !tile.enabled ? theme.bg_app
            : tile.pressed || tile.hovered ? theme.accent_subtle
            : tile.on ? theme.accent_subtle : theme.bg_raised
        border.width: tile.on ? 2 : 1
        border.color: tile.on ? theme.accent : theme.border_strong

        Rectangle {
            anchors.fill: parent
            anchors.margins: -4
            visible: tile.visualFocus
            color: "transparent"
            radius: theme.radius_md + 4
            border.width: 2
            border.color: theme.focus_ring
        }
    }

    contentItem: RowLayout {
        spacing: theme.space_2

        Item { Layout.fillWidth: true }

        Rectangle {
            implicitWidth: 9
            implicitHeight: 9
            radius: 4.5
            color: tile.on ? theme[tile.tone] : theme.text_muted
        }

        Text {
            text: tile.text
            color: theme.text_primary
            font.family: theme.ui_family
            font.pixelSize: theme.size_body
            font.weight: theme.weight_bold
            elide: Text.ElideRight
        }

        Item { Layout.fillWidth: true }
    }
}
