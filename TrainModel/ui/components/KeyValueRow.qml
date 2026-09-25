// Label and value pair, style guide 6.6. Values are mono and right-aligned.
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

        FieldLabel {
            Layout.fillWidth: true
            text: root.label.toUpperCase()
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
