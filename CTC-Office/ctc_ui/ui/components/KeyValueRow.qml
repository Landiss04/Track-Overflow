// Data-list row, style guide 6.6. Sentence-case label on the left, mono
// value on the right; an empty value renders as an em dash.
import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root

    property string label: ""
    property string value: ""

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
            elide: Text.ElideRight
        }

        MonoText {
            text: root.value === "" ? "—" : root.value
            horizontalAlignment: Text.AlignRight
        }
    }

    Rectangle {
        Layout.fillWidth: true
        implicitHeight: 1
        color: theme.border
    }
}
