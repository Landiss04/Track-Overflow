import QtQuick
import QtQuick.Layouts

// Surface card. Header rule and --border carry the separation; --shadow-1 is
// approximated by a tinted underlay because Qt Quick has no box-shadow.
Item {
    id: root

    property string title: ""
    property int bodyPadding: Theme.space4
    property alias headerContent: headerTools.data
    default property alias content: body.data

    Rectangle {
        anchors.fill: surface
        anchors.topMargin: 1
        anchors.bottomMargin: -2
        radius: Theme.radiusLg
        color: Theme.shadowInk
        opacity: Theme.shadow1Opacity
    }

    Rectangle {
        id: surface
        anchors.fill: parent
        radius: Theme.radiusLg
        color: Theme.bgSurface
        border.width: 1
        border.color: Theme.border
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
                    anchors.leftMargin: Theme.space4
                    anchors.rightMargin: Theme.space4
                    spacing: Theme.space3

                    Text {
                        text: root.title
                        color: Theme.textPrimary
                        font.family: Theme.uiFamily
                        font.pixelSize: Theme.sizeH3
                        font.bold: true
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    RowLayout {
                        id: headerTools
                        spacing: Theme.space2
                    }
                }

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 1
                    color: Theme.border
                }
            }

            ColumnLayout {
                id: body
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.margins: root.bodyPadding
                spacing: Theme.space3
            }
        }
    }
}
