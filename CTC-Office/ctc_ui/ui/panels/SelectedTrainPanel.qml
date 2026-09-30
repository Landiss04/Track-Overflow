// Selected train. Shows an empty state until a train is picked in the
// Train Occupancy window; the detail layout below is the skeleton that a
// selection fills in.
import QtQuick
import QtQuick.Layouts
import "../../../../ui"

Panel {
    id: root

    property string trainId: ""
    readonly property bool hasSelection: trainId !== ""

    signal clearRequested()

    title: hasSelection
        ? qsTr("Selected train — %1").arg(trainId)
        : qsTr("Selected train")

    headerItems: [
        AppButton {
            variant: "ghost"
            size: "small"
            text: qsTr("Clear")
            visible: root.hasSelection
            onClicked: root.clearRequested()
        }
    ]

    Item {
        Layout.fillWidth: true
        Layout.fillHeight: true
        visible: !root.hasSelection

        EmptyState {
            anchors.centerIn: parent
            heading: qsTr("No train selected")
            body: qsTr("Open the Train Occupancy window and pick a train. "
                + "Its route highlights on the track view and its metrics "
                + "load here.")
        }
    }

    ColumnLayout {
        Layout.fillWidth: true
        visible: root.hasSelection
        spacing: theme.space_3

        GridLayout {
            Layout.fillWidth: true
            columns: 3
            columnSpacing: theme.space_2
            rowSpacing: theme.space_2

            TelemetryReadout {
                Layout.fillWidth: true
                label: qsTr("Current block")
            }
            TelemetryReadout {
                Layout.fillWidth: true
                label: qsTr("Speed")
                unit: "m/s"
            }
            TelemetryReadout {
                Layout.fillWidth: true
                label: qsTr("Speed limit")
                unit: "m/s"
            }
            TelemetryReadout {
                Layout.fillWidth: true
                label: qsTr("Authority → block")
            }
            TelemetryReadout {
                Layout.fillWidth: true
                label: qsTr("ETA")
            }
            TelemetryReadout {
                Layout.fillWidth: true
                label: qsTr("Schedule deviation")
                unit: "s"
            }
        }

        FieldLabel { text: qsTr("ROUTE — HIGHLIGHTED ON TRACK VIEW") }

        // Route block chips (style guide 6.4) are populated here.
        Flow {
            Layout.fillWidth: true
            spacing: theme.space_1
        }

        KeyValueRow { Layout.fillWidth: true; label: qsTr("Destination") }
        KeyValueRow { Layout.fillWidth: true; label: qsTr("Next station") }
        KeyValueRow {
            Layout.fillWidth: true
            label: qsTr("Dwell at next stop")
        }
    }
}
