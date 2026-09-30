import QtQuick
import QtQuick.Layouts

// Surface card. Header rule and --border carry the separation; --shadow-1 is
// approximated by a tinted underlay because Qt Quick has no box-shadow.
Item {
    id: root

    property string title: ""
    property int bodyPadding: theme.space_4
    property alias headerContent: headerTools.data
    default property alias content: body.data

    Rectangle {
        anchors.fill: surface
        anchors.topMargin: 1
        anchors.bottomMargin: -2
        radius: theme.radius_lg
        color: theme.shadow_1_color
        opacity: theme.shadow_1_alpha
    }

    Rectangle {
        id: surface
        anchors.fill: parent
        radius: theme.radius_lg
        color: theme.bg_surface
        border.width: 1
        border.color: theme.border
        clip: true

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 44
                visible: root.title !== "" || headerTools.children.length > 0

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: theme.space_4
                    anchors.rightMargin: theme.space_4
                    spacing: theme.space_3

                    Text {
                        text: root.title
                        color: theme.text_primary
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_h3
                        font.bold: true
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    RowLayout {
                        id: headerTools
                        spacing: theme.space_2
                    }
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
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.margins: root.bodyPadding
                spacing: theme.space_3
            }
        }
    }
}
