// Empty state shown where a panel has nothing to display yet. QML has no
// dashed border, so the frame uses a solid --border-strong rule.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string heading: ""
    property string body: ""

    color: "transparent"
    border.color: theme.border_strong
    border.width: 1
    radius: theme.radius_md
    implicitWidth: 360
    implicitHeight: column.implicitHeight + 2 * theme.space_5
    // Shrink to fit narrow panels rather than overflowing them.
    width: parent ? Math.min(implicitWidth, parent.width) : implicitWidth
    height: implicitHeight

    ColumnLayout {
        id: column
        anchors.fill: parent
        anchors.margins: theme.space_5
        spacing: theme.space_2

        Text {
            Layout.fillWidth: true
            text: root.heading
            color: theme.text_secondary
            font.family: theme.ui_family
            font.pixelSize: theme.size_body
            font.weight: theme.weight_bold
            horizontalAlignment: Text.AlignHCenter
        }

        HelperText {
            Layout.fillWidth: true
            text: root.body
            visible: root.body !== ""
            horizontalAlignment: Text.AlignHCenter
        }
    }
}
