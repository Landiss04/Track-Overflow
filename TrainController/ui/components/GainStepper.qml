// Kp or Ki editor for the engineer pop-up: minus, the pending value, plus,
// with the value currently in use shown beside the label. The value field
// also accepts a typed number. Built from shared AppButton and ValueField;
// the stepper arrangement itself has no shared equivalent.
import QtQuick
import QtQuick.Layouts
import "../../../ui"

ColumnLayout {
    id: root

    property string label: ""
    property real value: 0
    property real inUse: 0
    signal stepped(int direction)
    signal typed(real value)

    spacing: theme.space_1

    // Keep the field in step with host state; typing breaks a binding.
    onValueChanged: field.text = value.toFixed(3)
    Component.onCompleted: field.text = value.toFixed(3)

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
            Layout.preferredWidth: theme.control_h_lg
            Layout.alignment: Qt.AlignTop
            text: "−"
            Accessible.name: "Decrease " + root.label
            onClicked: root.stepped(-1)
        }

        ValueField {
            id: field

            Layout.fillWidth: true
            kind: "float"
            onCommitted: function (value) { root.typed(value); }
        }

        AppButton {
            Layout.preferredWidth: theme.control_h_lg
            Layout.alignment: Qt.AlignTop
            text: "+"
            Accessible.name: "Increase " + root.label
            onClicked: root.stepped(1)
        }
    }
}
