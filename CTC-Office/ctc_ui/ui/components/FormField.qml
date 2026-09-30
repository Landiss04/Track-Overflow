// Labelled form field, style guide 6.2. Every input has a visible
// Label-token label above it; placeholder text is not a label.
import QtQuick
import QtQuick.Layouts
import "../../../../ui"

ColumnLayout {
    id: root

    property string label: ""
    // The control declared inside a FormField; give it Layout.fillWidth.
    default property alias content: slot.data

    spacing: theme.space_1

    FieldLabel {
        Layout.fillWidth: true
        text: root.label.toUpperCase()
    }

    ColumnLayout {
        id: slot
        Layout.fillWidth: true
        spacing: 0
    }
}
