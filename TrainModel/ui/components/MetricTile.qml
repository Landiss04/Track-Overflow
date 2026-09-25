import QtQuick
import QtQuick.Layouts

// Telemetry readout (Style Guide §6.5): sunken well, Label-token heading,
// mono 28 px bold value with a smaller muted unit inline. The container is
// a fixed height so digits updating in place never resize the layout.
Item {
    id: root

    property string label: ""
    property string value: ""
    property string unit: ""

    implicitWidth: 0
    implicitHeight: theme.metric_tile_height

    Rectangle {
        anchors.fill: parent
        color: theme.bg_sunken
        border.width: 1
        border.color: theme.border
        radius: theme.radius_md
    }

    Column {
        id: col
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        spacing: theme.space_1

        Text {
            width: parent.width
            text: root.label
            elide: Text.ElideRight
            font.family: theme.ui_family
            font.pixelSize: theme.font_label
            font.weight: Font.Bold
            font.letterSpacing: theme.label_tracking_em * theme.font_label
            color: theme.text_muted
        }

        RowLayout {
            spacing: theme.space_1

            Text {
                text: root.value
                font.family: theme.mono_family
                font.pixelSize: theme.value_size
                font.weight: Font.Bold
                color: theme.text_primary
            }

            Text {
                visible: root.unit.length > 0
                text: root.unit
                font.family: theme.mono_family
                font.pixelSize: theme.unit_size
                color: theme.text_muted
            }
        }
    }
}
