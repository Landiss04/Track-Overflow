// Panel, style guide 5 and 6.7. QML has no box-shadow, so the --shadow-1
// elevation of a resting panel is carried by --border instead.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string title: ""
    // Optional status belongs in a card header only when it describes the
    // section itself, such as an active failure count.
    property string statusLabel: ""
    property string statusVariant: "idle"
    // A framed card is reserved for bounded content such as a dense readout
    // group or a safety control. Most sections use the flat treatment so the
    // workspace does not turn into a grid of identical cards.
    property bool framed: true
    default property alias content: body.data

    color: framed ? theme.bg_surface : "transparent"
    border.color: theme.border
    border.width: framed ? 1 : 0
    radius: framed ? theme.radius_lg : 0
    implicitHeight: layout.implicitHeight + 2 * (framed ? theme.space_5 : 0)

    ColumnLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: root.framed ? theme.space_5 : 0
        spacing: theme.space_4

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.space_3

            Text {
                text: root.title
                color: theme.text_primary
                font.family: theme.ui_family
                font.pixelSize: root.framed ? theme.size_h3 : theme.size_h2
                font.weight: theme.weight_bold
            }

            Item { Layout.fillWidth: true }

            StatusBadge {
                label: root.statusLabel
                variant: root.statusVariant
                visible: root.statusLabel !== ""
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 1
            color: theme.border
            visible: root.framed
        }

        ColumnLayout {
            id: body
            Layout.fillWidth: true
            spacing: theme.space_3
        }
    }
}
