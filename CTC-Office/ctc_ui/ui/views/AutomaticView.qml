// Automatic mode: trains dispatch themselves from the loaded schedule.
//
// The column scrolls: a selected train's details are tall, and the
// schedule and throughput panels below keep a usable minimum height
// rather than being squeezed out of view.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../../../ui"
import "../panels"

ScrollView {
    id: root

    property string selectedTrainId: ""
    property string scheduleFile: ""
    property string scheduleError: ""
    property var departures: []
    // The CtcHost from __main__.py.
    property var host: null
    signal clearSelectionRequested()
    signal scheduleFileSelected(url fileUrl)

    // Smallest height that still shows the departures table and the
    // throughput readouts.
    readonly property int bottomRowMinimum: 440

    contentWidth: availableWidth
    clip: true

    ColumnLayout {
        id: column

        width: root.availableWidth
        // Fill the view when everything fits; grow (and scroll) when not.
        height: Math.max(root.availableHeight, implicitHeight)
        spacing: theme.space_3

        Callout {
            Layout.fillWidth: true
            variant: "info"
            heading: qsTr("Automatic mode")
            body: qsTr("Trains dispatch themselves from the loaded schedule. "
                + "CTC issues speed and authority automatically. To "
                + "dispatch a train yourself, switch to Manual. To close a "
                + "block or move a switch, switch to Maintenance.")
        }

        SelectedTrainPanel {
            Layout.fillWidth: true
            Layout.preferredHeight: hasSelection ? implicitHeight : 212
            trainId: root.selectedTrainId
            host: root.host
            onClearRequested: root.clearSelectionRequested()
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            // Sized from this, not from the panels' content, so a long
            // departures list scrolls inside its own panel.
            Layout.preferredHeight: root.bottomRowMinimum
            Layout.minimumHeight: root.bottomRowMinimum
            spacing: theme.space_3

            AutoDispatchPanel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 343
                scheduleFile: root.scheduleFile
                scheduleError: root.scheduleError
                departures: root.departures
                onScheduleFileSelected: function (fileUrl) {
                    root.scheduleFileSelected(fileUrl);
                }
            }

            ThroughputPanel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 405
                host: root.host
            }
        }
    }
}
