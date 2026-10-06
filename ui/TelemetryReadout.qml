// Telemetry readout, style guide 6.5. Label above, value in mono at 28 px
// bold, unit immediately after. The container does not resize as digits
// change, so give every readout in a group the same width. Without one it
// reserves room for six digits; a longer value elides.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string label: ""
    property string value: "\u2014"
    property string unit: ""

    color: theme.bg_sunken
    border.color: theme.border
    border.width: 1
    radius: theme.radius_md
    implicitWidth: Math.max(labelText.implicitWidth, Math.ceil(digitReserve.advanceWidth)
        + theme.space_2 + unitText.implicitWidth) + 2 * theme.space_4
    implicitHeight: column.implicitHeight + 2 * theme.space_3

    TextMetrics {
        id: digitReserve
        font: valueText.font
        text: "000000"
    }

    ColumnLayout {
        id: column
        anchors.fill: parent
        anchors.topMargin: theme.space_3
        anchors.bottomMargin: theme.space_3
        anchors.leftMargin: theme.space_4
        anchors.rightMargin: theme.space_4
        spacing: theme.space_1

        FieldLabel {
            id: labelText
            Layout.fillWidth: true
            text: root.label.toUpperCase()
            elide: Text.ElideRight
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.space_2

            Text {
                id: valueText
                Layout.fillWidth: true
                // Whole pixels: the layout rounds a fractional width down,
                // which would elide a value that fits.
                Layout.preferredWidth: Math.ceil(implicitWidth)
                Layout.maximumWidth: Math.ceil(implicitWidth)
                text: root.value
                textFormat: Text.PlainText
                elide: Text.ElideRight
                color: theme.text_primary
                font.family: theme.mono_family
                font.pixelSize: theme.size_telemetry
                font.weight: theme.weight_bold
            }

            MonoText {
                id: unitText
                Layout.alignment: Qt.AlignBottom
                Layout.bottomMargin: theme.space_1
                text: root.unit
                color: theme.text_muted
                visible: root.unit !== ""
            }

            Item { Layout.fillWidth: true }
        }
    }
}
