// Maintenance mode: block closures and switch positions set by hand.
//
// The column scrolls: the bottom row keeps at least the throughput
// panel's full height (chart, hour labels, line table), so nothing is
// clipped on a short window.
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
                + "positions by hand, only in this mode. A block with a "
                + "train in it closes once the train has left. Switch "
                + "commands are released when you leave Maintenance; "
                + "closures stay.")
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.space_3

            CloseBlockPanel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 1
                host: root.host
            }

            SwitchPanel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 1
                host: root.host
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: throughput.implicitHeight
            spacing: theme.space_3

            ClosuresPanel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 343
                host: root.host
            }

            ThroughputPanel {
                id: throughput
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 405
                host: root.host
            }
        }
    }
}
