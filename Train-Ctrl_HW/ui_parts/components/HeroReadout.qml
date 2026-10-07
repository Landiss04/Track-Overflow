// Telemetry readout at driving-position size. Same container, label and
// unit as the shared TelemetryReadout (guide 6.5); only the value size
// differs, and it is the one token this console adds (see README).
import QtQuick
import QtQuick.Layouts
import "../../../ui"

Rectangle {
    id: root

    property string label: ""
    property string value: "\u2014"
    property string unit: ""
    // Normally the text colour; an identifier may carry its own.
    property color valueColor: theme.text_primary

    color: theme.bg_sunken
    border.color: theme.border
    border.width: 1
    radius: theme.radius_md
    implicitHeight: column.implicitHeight + 2 * theme.space_3

    ColumnLayout {
        id: column
        anchors.fill: parent
        anchors.topMargin: theme.space_3
        anchors.bottomMargin: theme.space_3
        anchors.leftMargin: theme.space_4
        anchors.rightMargin: theme.space_4
        spacing: theme.space_1

        FieldLabel {
            Layout.fillWidth: true
            text: root.label.toUpperCase()
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
        }

        Text {
            Layout.fillWidth: true
            text: root.value
            color: root.valueColor
            font.family: theme.mono_family
            font.pixelSize: theme.size_display
            font.weight: theme.weight_bold
            horizontalAlignment: Text.AlignHCenter
        }

        MonoText {
            Layout.fillWidth: true
            text: root.unit
            color: theme.text_muted
            horizontalAlignment: Text.AlignHCenter
        }
    }
}
