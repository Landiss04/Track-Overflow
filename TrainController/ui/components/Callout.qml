// Informational callout on --accent-subtle, style guide 4.3.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string heading: ""
    property string body: ""

    color: theme.accent_subtle
    radius: theme.radius_md
    border.color: theme.border
    border.width: 1
    implicitHeight: column.implicitHeight + 2 * theme.space_4

    ColumnLayout {
        id: column
        anchors.fill: parent
        anchors.margins: theme.space_4
        spacing: theme.space_2

        Text {
            Layout.fillWidth: true
            text: root.heading
            color: theme.accent
            font.family: theme.ui_family
            font.pixelSize: theme.size_small
            font.weight: theme.weight_bold
        }

        HelperText {
            Layout.fillWidth: true
            text: root.body
            visible: root.body !== ""
        }
    }
}
