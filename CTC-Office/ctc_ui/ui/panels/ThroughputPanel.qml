// Throughput metrics: tickets per hour on each line since the
// simulation started, from Track Model ticket sales, as whole numbers.
// Two readouts fit a value of six digits at the telemetry size; a third
// would cut one short.
import QtQuick
import QtQuick.Layouts
import "../../../../ui"

Panel {
    id: root

    // The CtcHost from __main__.py.
    property var host: null

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

    HelperText {
        Layout.fillWidth: true
        Layout.topMargin: theme.space_2
        text: qsTr("Tickets sold per hour since the simulation started.")
    }
}
