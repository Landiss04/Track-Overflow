// Manual dispatch: pick a train and destination (or a block directly);
// CTC computes the suggested speed and authority sent to the wayside.
import QtQuick
import QtQuick.Layouts
import "../components"
import "../../../../ui"

Panel {
    id: root

    property var trainOptions: []
    property var destinationOptions: []
    property var lineOptions: []
    property var blockOptions: []

    signal dispatchRequested(string trainId, string destination,
                             string arrivalTime)
    signal setAuthorityRequested(string line, string block)

    title: qsTr("Dispatch train")

    headerItems: [
        HelperText {
            text: qsTr("Manual mode only")
            color: theme.text_muted
        }
    ]

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_3

        SelectField {
            id: trainSelect
            Layout.preferredWidth: 160
            label: qsTr("Train")
            model: root.trainOptions
            currentIndex: -1
        }

        SelectField {
            id: destinationSelect
            Layout.fillWidth: true
            label: qsTr("Destination station")
            model: root.destinationOptions
            currentIndex: -1
        }

        ValueField {
            id: arrivalField
            Layout.preferredWidth: 120
            label: qsTr("Arrival time")
        }
    }

    FieldLabel { text: qsTr("CTC COMPUTED — SENT TO TRACK CONTROLLER") }

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_2

        TelemetryReadout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            label: qsTr("Suggested speed limit")
            unit: "m/s"
        }
        TelemetryReadout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            label: qsTr("Authority → block")
        }
    }

    HelperText {
        Layout.fillWidth: true
        text: qsTr("Select a train and destination to compute speed and "
            + "authority.")
    }

    LabeledDivider {
        Layout.fillWidth: true
        text: qsTr("or dispatch directly to a block")
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_3

        SelectField {
            id: lineSelect
            Layout.preferredWidth: 160
            label: qsTr("Line")
            model: root.lineOptions
            currentIndex: -1
        }

        SelectField {
            id: blockSelect
            Layout.fillWidth: true
            label: qsTr("Block")
            model: root.blockOptions
            currentIndex: -1
        }

        AppButton {
            Layout.alignment: Qt.AlignBottom
            variant: "secondary"
            text: qsTr("Set authority")
            enabled: lineSelect.currentIndex >= 0
                && blockSelect.currentIndex >= 0
            onClicked: root.setAuthorityRequested(
                lineSelect.currentValue, blockSelect.currentValue)
        }
    }

    AppButton {
        Layout.fillWidth: true
        variant: "primary"
        size: "large"
        text: qsTr("Dispatch train")
        enabled: trainSelect.currentIndex >= 0
            && destinationSelect.currentIndex >= 0
        onClicked: root.dispatchRequested(trainSelect.currentValue,
            destinationSelect.currentValue, arrivalField.text)
    }
}
