// Data-list row, style guide 6.6. Field-label styling is only for labels
// above inputs; list labels remain readable sentence case.
import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root

    property string label: ""
    property string value: "\u2014"
    property bool rule: true

    spacing: theme.space_2

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_3

        Text {
            Layout.fillWidth: true
            text: root.label
            color: theme.text_secondary
            font.family: theme.ui_family
            font.pixelSize: theme.size_small
            font.weight: theme.weight_regular
            elide: Text.ElideRight
        }

        MonoText {
            text: root.value === "" ? "\u2014" : root.value
            horizontalAlignment: Text.AlignRight
        }
    }

    Rectangle {
        Layout.fillWidth: true
        implicitHeight: 1
        color: theme.border
        visible: root.rule
    }
}
