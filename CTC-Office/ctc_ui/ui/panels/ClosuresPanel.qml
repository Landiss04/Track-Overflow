// Blocks currently closed by the dispatcher, and blocks the Track
// Controller reports failed. A closed block can be reopened here; a
// failure clears only when the Track Controller stops reporting it.
import QtQuick
import QtQuick.Layouts
import "../../../../ui"

Panel {
    id: root

    // The CtcHost from __main__.py.
    property var host: null
    readonly property var closures: host ? host.closures : []
    property int selected: -1
    readonly property var selectedRow: selected >= 0
        && selected < closures.length ? closures[selected] : null
    property string message: ""

    onClosuresChanged: selected = -1

    title: qsTr("Active closures")

    DataTable {
        Layout.fillWidth: true
        columns: [
            { label: qsTr("Block"), key: "block", width: 110, mono: true },
            { label: qsTr("State"), key: "state" }
        ]
        rows: root.closures
        currentIndex: root.selected
        onRowActivated: function (index) { root.selected = index; }
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
                : qsTr("Select a closed block to reopen it.")
        }

        AppButton {
            variant: "secondary"
            text: qsTr("Reopen block")
            enabled: root.selectedRow !== null && root.selectedRow.reopenable
            onClicked: root.message = root.host.reopenBlock(
                root.selectedRow.line, root.selectedRow.blockId)
        }
    }

    Item { Layout.fillHeight: true }
}
