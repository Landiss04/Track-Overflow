// Panel, style guide 5. A --bg-raised header bar carries the H3 title and
// an optional trailing slot (badges, small buttons); the body fills the
// rest. QML has no box-shadow, so --shadow-1 is carried by --border.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string title: ""
    property int bodyPadding: theme.space_4
    // Children declared inside a Panel land in the body column.
    default property alias content: body.data
    // Trailing header content, e.g. `headerItems: [StatusBadge { ... }]`.
    property alias headerItems: headerSlot.data

    readonly property int headerHeight: theme.control_h_lg + theme.space_1

    color: theme.bg_surface
    border.color: theme.border
    border.width: 1
    radius: theme.radius_lg
    clip: true
    implicitHeight: headerHeight + body.implicitHeight + 2 * bodyPadding + 2

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 1
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: root.headerHeight
            color: theme.bg_raised
            radius: theme.radius_lg

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: theme.space_4
                anchors.rightMargin: theme.space_4
                spacing: theme.space_3

                Text {
                    text: root.title
                    textFormat: Text.PlainText
                    color: theme.text_primary
                    font.family: theme.ui_family
                    font.pixelSize: theme.size_h3
                    font.weight: theme.weight_bold
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                RowLayout {
                    id: headerSlot
                    spacing: theme.space_2
                }
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                implicitHeight: 1
                color: theme.border
            }
        }

        ColumnLayout {
            id: body
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: root.bodyPadding
            spacing: theme.space_3
        }
    }
}
