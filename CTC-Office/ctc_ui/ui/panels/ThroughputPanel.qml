// Throughput metrics: headline readouts, a 12-hour history chart
// placeholder, and an optional per-line breakdown.
import QtQuick
import QtQuick.Layouts
import "../components"

Panel {
    id: root

    property bool showLineTable: true
    property var lineRows: []

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
            label: qsTr("Tickets")
            unit: "/hr"
        }
        TelemetryReadout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            label: qsTr("On time")
            unit: "%"
        }
    }

    FieldLabel { text: qsTr("THROUGHPUT, LAST 12 HOURS") }

    // Hourly bar chart renders here.
    Rectangle {
        Layout.fillWidth: true
        implicitHeight: theme.space_7 + theme.space_5
        color: theme.bg_sunken
        radius: theme.radius_md

        HelperText {
            anchors.centerIn: parent
            text: qsTr("No throughput data yet")
            color: theme.text_muted
        }
    }

    DataTable {
        Layout.fillWidth: true
        visible: root.showLineTable
        columns: [
            { title: qsTr("Line"), key: "line" },
            { title: qsTr("Tickets/hr"), key: "tickets", width: 88,
              numeric: true },
            { title: qsTr("Trains/hr"), key: "trains", width: 80,
              numeric: true },
            { title: qsTr("Dwell (s)"), key: "dwell", width: 80,
              numeric: true }
        ]
        rows: root.lineRows
        emptyText: qsTr("No line data")
    }

    Item { Layout.fillHeight: true }
}
