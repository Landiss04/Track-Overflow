// Throughput metrics: headline readouts (trains per hour, then tickets
// per hour on each line, from Track Model ticket sales), tickets sold in
// each of the last 12 simulated hours per line, and an optional per-line
// breakdown.
import QtQuick
import QtQuick.Layouts
import "../../../../ui"

Panel {
    id: root

    property bool showLineTable: true
    // The CtcHost from __main__.py.
    property var host: null
    readonly property var lineRows: host ? host.throughputRows : []

    function ticketsPerHour(line) {
        return root.host && root.host.throughput[line] !== undefined
            ? root.host.throughput[line] : "—";
    }

    title: qsTr("Throughput metrics")

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_2

        TelemetryReadout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            label: qsTr("Trains")
            unit: "/hr"
        }
        TelemetryReadout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            // Tickets per hour; the per-line table below says so.
            label: qsTr("Red line")
            value: root.ticketsPerHour("Red")
            unit: "/hr"
        }
        TelemetryReadout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            label: qsTr("Green line")
            value: root.ticketsPerHour("Green")
            unit: "/hr"
        }
    }

    FieldLabel { text: qsTr("THROUGHPUT, LAST 12 HOURS") }

    ThroughputHistory {
        Layout.fillWidth: true
        history: root.host ? root.host.throughputHistory : null
    }

    DataTable {
        Layout.fillWidth: true
        visible: root.showLineTable
        columns: [
            { label: qsTr("Line"), key: "line" },
            { label: qsTr("Tickets/hr"), key: "tickets", width: 88,
              numeric: true },
            { label: qsTr("Trains/hr"), key: "trains", width: 80,
              numeric: true },
            { label: qsTr("Dwell (s)"), key: "dwell", width: 80,
              numeric: true }
        ]
        rows: root.lineRows
    }

    HelperText {
        Layout.fillWidth: true
        Layout.topMargin: theme.space_2
        visible: root.showLineTable && root.lineRows.length === 0
        horizontalAlignment: Text.AlignHCenter
        text: qsTr("No line data")
    }

    Item { Layout.fillHeight: true }
}
