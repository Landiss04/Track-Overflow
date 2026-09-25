// Panel, style guide 5 and 6.7. QML has no box-shadow, so the --shadow-1
// elevation of a resting panel is carried by --border instead.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string title: ""
    property string badgeLabel: ""
    property string badgeVariant: "idle"
    default property alias content: body.data

    color: theme.bg_surface
    border.color: theme.border
    border.width: 1
    radius: theme.radius_lg
    implicitHeight: layout.implicitHeight + 2 * theme.space_5

    ColumnLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: theme.space_5
        spacing: theme.space_4

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.space_3

            Text {
                text: root.title
                color: theme.text_primary
                font.family: theme.ui_family
                font.pixelSize: theme.size_h3
                font.weight: theme.weight_bold
            }

            Item { Layout.fillWidth: true }

            StatusBadge {
                label: root.badgeLabel
                variant: root.badgeVariant
                visible: root.badgeLabel !== ""
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 1
            color: theme.border
        }

        ColumnLayout {
            id: body
            Layout.fillWidth: true
            spacing: theme.space_3
        }
    }
}
