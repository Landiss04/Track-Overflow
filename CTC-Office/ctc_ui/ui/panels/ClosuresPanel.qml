// Blocks currently closed or restricted.
import QtQuick
import QtQuick.Layouts
import "../components"
import "../../../../ui"

Panel {
    id: root

    property var closures: []

    title: qsTr("Active closures")

    DataTable {
        Layout.fillWidth: true
        columns: [
            { label: qsTr("Block"), key: "block", width: 110, mono: true },
            { label: qsTr("State"), key: "state" }
        ]
        rows: root.closures
    }

    HelperText {
        Layout.fillWidth: true
        Layout.topMargin: theme.space_2
        visible: root.closures.length === 0
        horizontalAlignment: Text.AlignHCenter
        text: qsTr("No active closures")
    }

    Item { Layout.fillHeight: true }
}
