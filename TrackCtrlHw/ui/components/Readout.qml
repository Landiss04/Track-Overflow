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

    readonly property int valueSize: compact ? Theme.sizeBody : Theme.sizeReadout

    implicitWidth: column.implicitWidth + 2 * Theme.space4
    implicitHeight: column.implicitHeight + 2 * Theme.space3
    radius: Theme.radiusMd
    color: Theme.bgSunken
    border.width: 1
    border.color: Theme.border
    clip: true

    Column {
        id: column
        anchors.fill: parent
        anchors.leftMargin: Theme.space4
        anchors.rightMargin: Theme.space4
        anchors.topMargin: Theme.space3
        anchors.bottomMargin: Theme.space3
        spacing: Theme.space1

        Text {
            text: root.label.toUpperCase()
            color: Theme.textMuted
            font.family: Theme.uiFamily
            font.pixelSize: Theme.sizeLabel
            font.bold: true
            font.letterSpacing: Theme.sizeLabel * Theme.labelTracking
        }

        Row {
            spacing: Theme.space2
            width: parent.width

            Text {
                text: root.value
                color: Theme.textPrimary
                font.family: Theme.monoFamily
                font.pixelSize: root.valueSize
                font.bold: true
                width: Math.min(implicitWidth, column.width)
                elide: Text.ElideRight
            }

            Text {
                text: root.unit
                visible: root.unit !== ""
                color: Theme.textMuted
                font.family: Theme.monoFamily
                font.pixelSize: Theme.sizeSmall
                anchors.bottom: parent.bottom
                anchors.bottomMargin: root.compact ? 1 : 4
            }
        }
    }
}
