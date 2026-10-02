// Manual mode: the dispatcher issues destination, authority and speed.
import QtQuick
import QtQuick.Layouts
import "../../../../ui"
import "../panels"

ColumnLayout {
    id: root

    property string selectedTrainId: ""
    signal clearSelectionRequested()

    spacing: theme.space_3

    Callout {
        Layout.fillWidth: true
        variant: "info"
        heading: qsTr("Manual mode")
        body: qsTr("You issue destination, authority and speed. Schedule "
            + "auto-dispatch is paused and queued runs are held. To close "
            + "a block or move a switch, switch to Maintenance.")
    }

    DispatchPanel {
        Layout.fillWidth: true
        Layout.preferredHeight: implicitHeight
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        spacing: theme.space_3

        SelectedTrainPanel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: 343
            trainId: root.selectedTrainId
            onClearRequested: root.clearSelectionRequested()
        }

        ThroughputPanel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: 405
            showLineTable: false
        }
    }
}
