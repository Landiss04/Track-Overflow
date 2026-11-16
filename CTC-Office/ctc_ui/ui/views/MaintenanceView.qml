// Maintenance mode: block closures and switch positions set by hand.
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

    // The CtcHost from __main__.py.
    property var host: null

    contentWidth: availableWidth
    clip: true

    ColumnLayout {
        width: root.availableWidth
        // Fill the view when everything fits; grow (and scroll) when not.
        height: Math.max(root.availableHeight, implicitHeight)
        spacing: theme.space_3

        Callout {
            Layout.fillWidth: true
            variant: "warning"
            heading: qsTr("Maintenance mode")
            body: qsTr("You close and reopen blocks and set switch "
                + "positions by hand, only in this mode. A block closes "
                + "at once, even with a train in it. Closures and switch "
                + "commands stay when you leave Maintenance, until you "
                + "reopen or release them here.")
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.space_3

            // Wide enough for the armed confirmation, "YES, CLOSE
            // BLOCK" beside Cancel, to show in full.
            CloseBlockPanel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 396
                host: root.host
            }

            SwitchPanel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 352
                host: root.host
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            // The throughput and signals panels, stacked, in full.
            Layout.minimumHeight: throughput.implicitHeight
                + theme.space_3 + signalLights.implicitHeight
            spacing: theme.space_3

            ClosuresPanel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 343
                host: root.host
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
