// Table header, style guide 6.6. Label token, muted, 1 px --border-strong
// bottom rule.
import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root

    property string nameColumn: "Signal"
    property string kindColumn: "Type"
    property string valueColumn: "Value"
    property int kindWidth: 64
    property int valueWidth: 180
    property int unitWidth: 52

    spacing: theme.space_2

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_3

        FieldLabel { Layout.fillWidth: true; text: root.nameColumn.toUpperCase() }
        FieldLabel {
            Layout.preferredWidth: root.kindWidth
            text: root.kindColumn.toUpperCase()
        }
        FieldLabel {
            Layout.preferredWidth: root.valueWidth
            text: root.valueColumn.toUpperCase()
        }
        Item { Layout.preferredWidth: root.unitWidth }
    }

    Rectangle {
        Layout.fillWidth: true
        implicitHeight: 1
        color: theme.border_strong
    }
}
