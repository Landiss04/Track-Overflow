// Blocks currently closed or restricted.
import QtQuick
import QtQuick.Layouts
import "../components"

Panel {
    id: root

    property var closures: []

    title: qsTr("Active closures")

    DataTable {
        Layout.fillWidth: true
        columns: [
            { title: qsTr("Block"), key: "block", width: 110, mono: true },
            { title: qsTr("State"), key: "state" }
        ]
        rows: root.closures
        emptyText: qsTr("No active closures")
    }

    Item { Layout.fillHeight: true }
}
