// Cab panel: a titled strip over a padded body, style guide 5 (--radius-lg,
// --border). Children go into a ColumnLayout, so Layout.fillHeight works
// when the panel itself is stretched.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string title: ""
    property string trailing: ""
    property bool trailingMono: false
    default property alias content: body.data

    color: theme.bg_surface
    border.color: theme.border
    border.width: 1
    radius: theme.radius_lg
    implicitHeight: header.height + body.implicitHeight + 2 * theme.space_3

    Item {
        id: header

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: theme.control_h_md

        FieldLabel {
            anchors.left: parent.left
            anchors.leftMargin: theme.space_4
            anchors.verticalCenter: parent.verticalCenter
            text: root.title.toUpperCase()
            color: theme.text_primary
        }

        MonoText {
            anchors.right: parent.right
            anchors.rightMargin: theme.space_4
            anchors.verticalCenter: parent.verticalCenter
            visible: root.trailingMono
            text: root.trailing
        }

        FieldLabel {
            anchors.right: parent.right
            anchors.rightMargin: theme.space_4
            anchors.verticalCenter: parent.verticalCenter
            visible: !root.trailingMono
            text: root.trailing.toUpperCase()
        }

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 1
            color: theme.border
        }
    }

    ColumnLayout {
        id: body

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: header.bottom
        anchors.bottom: parent.bottom
        anchors.margins: theme.space_3
        spacing: theme.space_2
    }
}
