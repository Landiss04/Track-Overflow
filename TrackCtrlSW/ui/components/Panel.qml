// Bordered work surface with a title strip, style guide 5 and 6.7.
// The Program and View tabs are both grids of these, so the strip
// carries an optional right-hand status count.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string title: ""
    property string status: ""
    default property alias content: body.data

    color: theme.bg_surface
    border.color: theme.border
    border.width: 1
    radius: theme.radius_md

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 1
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: theme.control_h_sm + theme.space_1
            color: theme.bg_sunken
            radius: theme.radius_md

            // Square off the bottom corners so the strip meets the body.
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: parent.radius
                color: parent.color
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                implicitHeight: 1
                color: theme.border
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: theme.space_3
                anchors.rightMargin: theme.space_3
                spacing: theme.space_2

                Text {
                    text: root.title.toUpperCase()
                    color: theme.text_secondary
                    font.family: theme.ui_family
                    font.pixelSize: theme.size_label
                    font.weight: theme.weight_bold
                    font.letterSpacing: theme.label_letter_spacing
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                MonoText {
                    text: root.status
                    color: theme.text_muted
                    font.pixelSize: theme.size_label
                    visible: root.status !== ""
                }
            }
        }

        Item {
            id: body
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
    }
}
