import QtQuick

// Style Guide §6.5. Container --bg-sunken, Label-token label above, value in
// mono. `compact` drops the value to Body size for identifiers and filenames,
// which do not benefit from the 28 px telemetry size.
Rectangle {
    id: root

    property string label: ""
    property string value: "\u2014"
    property string unit: ""
    property bool compact: false

    readonly property int valueSize: compact ? theme.size_body : theme.size_telemetry

    implicitWidth: column.implicitWidth + 2 * theme.space_4
    implicitHeight: column.implicitHeight + 2 * theme.space_3
    radius: theme.radius_md
    color: theme.bg_sunken
    border.width: 1
    border.color: theme.border
    clip: true

    Column {
        id: column
        anchors.fill: parent
        anchors.leftMargin: theme.space_4
        anchors.rightMargin: theme.space_4
        anchors.topMargin: theme.space_3
        anchors.bottomMargin: theme.space_3
        spacing: theme.space_1

        Text {
            text: root.label.toUpperCase()
            color: theme.text_muted
            font.family: theme.ui_family
            font.pixelSize: theme.size_label
            font.bold: true
            font.letterSpacing: theme.label_letter_spacing
        }

        Row {
            spacing: theme.space_2
            width: parent.width

            Text {
                text: root.value
                color: theme.text_primary
                font.family: theme.mono_family
                font.pixelSize: root.valueSize
                font.bold: true
                width: Math.min(implicitWidth, column.width)
                elide: Text.ElideRight
            }

            Text {
                text: root.unit
                visible: root.unit !== ""
                color: theme.text_muted
                font.family: theme.mono_family
                font.pixelSize: theme.size_small
                anchors.bottom: parent.bottom
                anchors.bottomMargin: root.compact ? 1 : 4
            }
        }
    }
}
