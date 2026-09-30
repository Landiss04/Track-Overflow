// Automatic mode: trains dispatch themselves from the loaded schedule.
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
        heading: qsTr("Automatic mode")
        body: qsTr("Trains dispatch themselves from the loaded schedule. "
            + "CTC issues speed and authority automatically. To dispatch a "
            + "train yourself, switch to Manual. To close a block or move a "
            + "switch, switch to Maintenance.")
    }

    SelectedTrainPanel {
        Layout.fillWidth: true
        Layout.preferredHeight: hasSelection ? implicitHeight : 212
        trainId: root.selectedTrainId
        onClearRequested: root.clearSelectionRequested()
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        spacing: theme.space_3

        AutoDispatchPanel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: 343
        }

        ThroughputPanel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: 405
        }
    }
}
