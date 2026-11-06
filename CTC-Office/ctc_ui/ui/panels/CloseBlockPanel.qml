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
    // The picked block's closure: "closed", "closing" or "". A block
    // that is already either cannot be closed again; the panel says so
    // as soon as it is picked.
    readonly property string closure: {
        if (!root.host || lineSelect.value === "" || blockSelect.value === "")
            return "";
        root.host.revision;
        return root.host.closureState(lineSelect.value, blockSelect.value);
    }

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
            // A new pick replaces the last action's result.
            onValueChanged: root.message = ""
        }

        PickField {
            id: blockSelect
            Layout.fillWidth: true
            label: qsTr("Block")
            model: root.host && lineSelect.value !== ""
                ? root.host.blockOptions(lineSelect.value) : []
            currentIndex: -1
            onValueChanged: root.message = ""
        }
    }

    HelperText {
        Layout.fillWidth: true
        Layout.topMargin: theme.space_5 - theme.space_3
        color: closeButton.armed ? theme.text_secondary
            : root.message !== ""
                ? (root.messageIsError ? theme.danger : theme.text_secondary)
            : root.closure !== "" ? theme.warning
            : theme.text_secondary
        text: closeButton.armed
            ? qsTr("Close %1 %2? No train will be given authority over "
                + "it, and queued runs that use it will be re-routed.")
                .arg(lineSelect.value).arg(blockSelect.value)
            : root.message !== "" ? root.message
            : root.closure === "closed"
                ? qsTr("%1 %2 is already closed. Reopen it under Active "
                    + "closures.").arg(lineSelect.value)
                    .arg(blockSelect.value)
            : root.closure === "closing"
                ? qsTr("%1 %2 is already closing: it closes once the train "
                    + "has left. Cancel it under Active closures.")
                    .arg(lineSelect.value).arg(blockSelect.value)
            : qsTr("Select a line and block to close.")
    }

    SafetyButton {
        id: closeButton
        Layout.fillWidth: true
        label: qsTr("Close block")
        confirmLabel: qsTr("Yes, close block")
        enabled: lineSelect.value !== "" && blockSelect.value !== ""
            && root.closure === ""
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
