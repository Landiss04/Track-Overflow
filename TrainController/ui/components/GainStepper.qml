// Kp or Ki editor for the engineer pop-up: minus, pending value, plus, with
// the value currently in use shown beside the label.
import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root

    property string label: ""
    property real value: 0
    property real inUse: 0
    signal stepped(int direction)

    spacing: theme.space_2

    RowLayout {
        Layout.fillWidth: true

        FieldLabel { text: root.label.toUpperCase() }

        Item { Layout.fillWidth: true }

        FieldLabel { text: "IN USE" }

        MonoText { text: root.inUse.toFixed(3) }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_2

        AppButton {
            Layout.preferredWidth: theme.control_h_lg + theme.space_3
            size: "large"
            text: "−"
            onClicked: root.stepped(-1)
        }

        ValueBox {
            Layout.fillWidth: true
            Layout.preferredHeight: theme.control_h_lg
            text: root.value.toFixed(3)
            pixelSize: theme.size_h3
        }

        AppButton {
            Layout.preferredWidth: theme.control_h_lg + theme.space_3
            size: "large"
            text: "+"
            onClicked: root.stepped(1)
        }
    }
}
