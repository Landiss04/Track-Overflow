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

        FieldLabel {
            Layout.fillWidth: true
            text: root.heading.toUpperCase()
            color: theme.accent
        }

        HelperText {
            Layout.fillWidth: true
            text: root.body
            visible: root.body !== ""
        }
    }
}
