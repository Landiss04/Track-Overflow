// View switcher. Entries carry text labels: style guide 2 and 8 require that
// colour or an icon is never the only signal, and every interactive target is
// at least 28 px.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property var entries: []
    property int currentIndex: 0
    signal activated(int index)

    implicitWidth: 196
    color: theme.bg_raised

    Rectangle {
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        implicitWidth: 1
        color: theme.border
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: theme.space_3
        spacing: theme.space_1

        Repeater {
            model: root.entries

            delegate: Rectangle {
                required property int index
                required property string modelData

                readonly property bool selected: index === root.currentIndex

                Layout.fillWidth: true
                implicitHeight: theme.control_h_md
                radius: theme.radius_md
                color: selected ? theme.accent_subtle : "transparent"
                border.width: selected ? 1 : 0
                border.color: theme.accent

                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: theme.space_3
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData
                    color: parent.selected ? theme.accent : theme.text_secondary
                    font.family: theme.ui_family
                    font.pixelSize: theme.size_small
                    font.weight: parent.selected
                        ? theme.weight_bold : theme.weight_regular
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.activated(index)
                }
            }
        }

        Item { Layout.fillHeight: true }
    }
}
