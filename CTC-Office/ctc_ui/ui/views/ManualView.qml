// Manual mode: the dispatcher issues destination, authority and speed.
//
// The column scrolls: the bottom row keeps at least the full height of
// the throughput and signals panels, so nothing is clipped on a short
// window.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../../../ui"
import "../panels"

ScrollView {
    id: root

    property string selectedTrainId: ""
    // The CtcHost from __main__.py.
    property var host: null
    signal clearSelectionRequested()

    contentWidth: availableWidth
    clip: true

    ColumnLayout {
        width: root.availableWidth
        // Fill the view when everything fits; grow (and scroll) when not.
        height: Math.max(root.availableHeight, implicitHeight)
        spacing: theme.space_3

        Callout {
            Layout.fillWidth: true
            variant: "info"
            heading: qsTr("Manual mode")
            body: qsTr("You issue destination, authority and speed. "
                + "Schedule auto-dispatch is paused and queued runs are "
                + "held. To close a block or move a switch, switch to "
                + "Maintenance.")
        }

        DispatchPanel {
            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
            host: root.host
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            // The throughput and signals panels, stacked, in full.
            Layout.minimumHeight: throughput.implicitHeight
                + theme.space_3 + signalLights.implicitHeight
            spacing: theme.space_3

            SelectedTrainPanel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 343
                trainId: root.selectedTrainId
                host: root.host
                canReroute: true
                onClearRequested: root.clearSelectionRequested()
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 405
                spacing: theme.space_3

                ThroughputPanel {
                    id: throughput
                    Layout.fillWidth: true
                    host: root.host
                }

                SignalsPanel {
                    id: signalLights
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    lights: trackMap ? trackMap.signals : []
                    states: root.host ? root.host.signalStates : ({})
                }
            }
        }
    }
}
