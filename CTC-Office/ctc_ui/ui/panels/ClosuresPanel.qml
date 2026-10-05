// Blocks closed by the dispatcher, blocks waiting to close until the
// train in them leaves, and blocks the Track Controller reports failed.
// A closed block can be reopened and a pending closure cancelled here; a
// failure clears only when the Track Controller stops reporting it.
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
        return row.line + "|" + row.blockId + "|" + row.reopenable;
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
                : root.selectedRow && !root.selectedRow.reopenable
                ? qsTr("Failures clear when the Track Controller stops "
                    + "reporting them.")
                : root.selectedRow && root.selectedRow.pending
                ? qsTr("Closes by itself once the train has left the "
                    + "block.")
                : qsTr("Select a closed block to reopen it.")
        }

        AppButton {
            variant: "secondary"
            text: root.selectedRow && root.selectedRow.pending
                ? qsTr("Cancel closing") : qsTr("Reopen block")
            enabled: root.selectedRow !== null && root.selectedRow.reopenable
            onClicked: root.message = root.host.reopenBlock(
                root.selectedRow.line, root.selectedRow.blockId)
        }
    }

    Item { Layout.fillHeight: true }
}
