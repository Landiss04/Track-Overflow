// Close a block for maintenance. Force-closing a block is a
// safety-critical control (style guide 7): it is confirmed, oversized, and
// separated from the routine selectors by at least --space-5.
import QtQuick
import QtQuick.Layouts
import "../components"

Panel {
    id: root

    property var lineOptions: []
    property var blockOptions: []

    signal closeBlockRequested(string line, string block)

    title: qsTr("Close block for maintenance")

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_3

        FormField {
            Layout.preferredWidth: 120
            label: qsTr("Line")

            SelectField {
                id: lineSelect
                Layout.fillWidth: true
                model: root.lineOptions
                currentIndex: -1
            }
        }

        FormField {
            Layout.fillWidth: true
            label: qsTr("Block")

            SelectField {
                id: blockSelect
                Layout.fillWidth: true
                mono: true
                model: root.blockOptions
                currentIndex: -1
            }
        }
    }

    HelperText {
        Layout.fillWidth: true
        Layout.topMargin: theme.space_5 - theme.space_3
        text: closeButton.armed
            ? qsTr("Close %1 %2? No train will be given authority over "
                + "it, and queued runs that use it will be re-routed.")
                .arg(lineSelect.currentText).arg(blockSelect.currentText)
            : qsTr("Select a line and block to close.")
    }

    SafetyButton {
        id: closeButton
        Layout.fillWidth: true
        label: qsTr("Close block")
        confirmLabel: qsTr("Yes, close block")
        enabled: lineSelect.currentIndex >= 0 && blockSelect.currentIndex >= 0
        onConfirmed: root.closeBlockRequested(lineSelect.currentText,
            blockSelect.currentText)
    }

    Item { Layout.fillHeight: true }
}
