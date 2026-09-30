// Close a block for maintenance. Force-closing a block is a
// safety-critical control (style guide 7): it is confirmed, oversized, and
// separated from the routine selectors by at least --space-5.
import QtQuick
import QtQuick.Layouts
import "../../../../ui"

Panel {
    id: root

    property var lineOptions: []
    property var blockOptions: []

    signal closeBlockRequested(string line, string block)

    title: qsTr("Close block for maintenance")

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_3

        SelectField {
            id: lineSelect
            Layout.preferredWidth: 120
            label: qsTr("Line")
            model: root.lineOptions
            currentIndex: -1
        }

        SelectField {
            id: blockSelect
            Layout.fillWidth: true
            label: qsTr("Block")
            model: root.blockOptions
            currentIndex: -1
        }
    }

    HelperText {
        Layout.fillWidth: true
        Layout.topMargin: theme.space_5 - theme.space_3
        text: closeButton.armed
            ? qsTr("Close %1 %2? No train will be given authority over "
                + "it, and queued runs that use it will be re-routed.")
                .arg(lineSelect.currentValue).arg(blockSelect.currentValue)
            : qsTr("Select a line and block to close.")
    }

    SafetyButton {
        id: closeButton
        Layout.fillWidth: true
        label: qsTr("Close block")
        confirmLabel: qsTr("Yes, close block")
        enabled: lineSelect.currentIndex >= 0 && blockSelect.currentIndex >= 0
        onConfirmed: root.closeBlockRequested(lineSelect.currentValue,
            blockSelect.currentValue)
    }

    Item { Layout.fillHeight: true }
}
