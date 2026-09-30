// Horizontal rule with a centred Label-token caption.
import QtQuick
import QtQuick.Layouts
import "../../../../ui"

RowLayout {
    id: root

    property string text: ""

    spacing: theme.space_3

    Rectangle {
        Layout.fillWidth: true
        implicitHeight: 1
        color: theme.border
    }

    FieldLabel { text: root.text.toUpperCase() }

    Rectangle {
        Layout.fillWidth: true
        implicitHeight: 1
        color: theme.border
    }
}
