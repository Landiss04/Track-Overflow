// Blocks closed by the dispatcher, which can be reopened here. (Failures
// are not listed: the CTC sees one only as an occupied block.)
import QtQuick
import QtQuick.Layouts
import "../../../../ui"

Panel {
    id: root

    // The CtcHost from __main__.py.
    property var host: null
    readonly property var closures: host ? host.closures : []
    // The selected row, kept by block (not by position) so it survives
    // the list being rebuilt on every update.
    property string selectedKey: ""
    readonly property int selected: {
        for (let i = 0; i < closures.length; ++i) {
            if (root.keyOf(closures[i]) === root.selectedKey)
                return i;
        }
        return -1;
    }
    readonly property var selectedRow: selected >= 0
        ? closures[selected] : null
    property string message: ""

    function keyOf(row) {
        return row.line + "|" + row.blockId;
    }

    title: qsTr("Active closures")

    DataTable {
        Layout.fillWidth: true
        columns: [
            { label: qsTr("Block"), key: "block", width: 110, mono: true },
            { label: qsTr("State"), key: "state" }
        ]
        rows: root.closures
        currentIndex: root.selected
        onRowActivated: function (index, row) {
            root.selectedKey = root.keyOf(row);
            root.message = "";
        }
    }

    HelperText {
        Layout.fillWidth: true
        Layout.topMargin: theme.space_2
        visible: root.closures.length === 0
        horizontalAlignment: Text.AlignHCenter
        text: qsTr("No active closures")
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.topMargin: theme.space_2
        visible: root.closures.length > 0
        spacing: theme.space_3

        HelperText {
            Layout.fillWidth: true
            color: root.message !== "" ? theme.danger : theme.text_muted
            text: root.message !== "" ? root.message
                : qsTr("Select a closed block to reopen it.")
        }

        AppButton {
            variant: "secondary"
            text: qsTr("Reopen block")
            enabled: root.selectedRow !== null
            onClicked: root.message = root.host.reopenBlock(
                root.selectedRow.line, root.selectedRow.blockId)
        }
    }

    Item { Layout.fillHeight: true }
}
