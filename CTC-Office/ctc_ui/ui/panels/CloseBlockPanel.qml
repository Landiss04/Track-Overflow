// Close a block for maintenance. Force-closing a block is a
// safety-critical control (style guide 7): it is confirmed, oversized, and
// separated from the routine selectors by at least --space-5.
import QtQuick
import QtQuick.Layouts
import "../../../../ui"
import "../components"

Panel {
    id: root

    // The CtcHost from __main__.py.
    property var host: null
    property string message: ""
    property bool messageIsError: false

    title: qsTr("Close block for maintenance")

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_3

        PickField {
            id: lineSelect
            Layout.preferredWidth: 120
            label: qsTr("Line")
            model: root.host ? root.host.lineNames : []
            currentIndex: -1
        }

        PickField {
            id: blockSelect
            Layout.fillWidth: true
            label: qsTr("Block")
            model: root.host && lineSelect.value !== ""
                ? root.host.blockOptions(lineSelect.value) : []
            currentIndex: -1
        }
    }

    HelperText {
        Layout.fillWidth: true
        Layout.topMargin: theme.space_5 - theme.space_3
        color: !closeButton.armed && root.messageIsError
            ? theme.danger : theme.text_secondary
        text: closeButton.armed
            ? qsTr("Close %1 %2? No train will be given authority over "
                + "it, and queued runs that use it will be re-routed.")
                .arg(lineSelect.value).arg(blockSelect.value)
            : root.message !== "" ? root.message
            : qsTr("Select a line and block to close.")
    }

    SafetyButton {
        id: closeButton
        Layout.fillWidth: true
        label: qsTr("Close block")
        confirmLabel: qsTr("Yes, close block")
        enabled: lineSelect.value !== "" && blockSelect.value !== ""
        onConfirmed: {
            const error = root.host.closeBlock(lineSelect.value,
                blockSelect.value);
            root.messageIsError = error !== "";
            root.message = error !== "" ? error
                : qsTr("%1 %2 closed.").arg(lineSelect.value)
                    .arg(blockSelect.value);
        }
    }

    Item { Layout.fillHeight: true }
}
