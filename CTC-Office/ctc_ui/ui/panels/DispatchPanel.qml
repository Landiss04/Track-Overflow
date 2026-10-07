// Manual dispatch: pick a line, a train and a destination station (or a
// block directly); CTC computes the suggested speed and authority sent
// to the wayside. Picking a train that already has an order reroutes
// it.
import QtQuick
import QtQuick.Layouts
import "../../../../ui"
import "../components"

Panel {
    id: root

    // The CtcHost from __main__.py.
    property var host: null

    // What the dispatcher picked; '' until they pick (PickField).
    readonly property string line: lineSelect.value
    readonly property string trainId: trainSelect.value
    // The selected train's current row; re-read whenever the module
    // changes.
    readonly property var train: {
        if (!root.host || root.trainId === "")
            return ({});
        root.host.revision;
        return root.host.trainDetail(root.trainId);
    }
    // Result of the last action: an error, or a confirmation.
    property string message: ""
    property bool messageIsError: false

    function report(error, done) {
        root.messageIsError = error !== "";
        root.message = error !== "" ? error : done;
    }

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

        PickField {
            id: lineSelect
            Layout.preferredWidth: 110
            label: qsTr("Line")
            model: root.host ? root.host.lineNames : []
            currentIndex: -1
        }

        PickField {
            id: trainSelect
            Layout.preferredWidth: 170
            label: qsTr("Train")
            textRole: "text"
            valueRole: "value"
            model: {
                if (!root.host || root.line === "")
                    return [];
                root.host.revision;
                return root.host.trainOptions(root.line);
            }
        }

        PickField {
            id: destinationSelect
            Layout.fillWidth: true
            label: qsTr("Destination station")
            textRole: "text"
            valueRole: "value"
            model: root.host && root.line !== ""
                ? root.host.stationOptions(root.line) : []
            currentIndex: -1
        }

        ValueField {
            id: arrivalField
            Layout.preferredWidth: 120
            label: qsTr("Arrival (HH:MM)")
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
            value: root.train.speedLimit || "—"
            unit: "mph"
        }
        TelemetryReadout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            label: qsTr("Authority")
            value: root.train.authorityBlocks || "—"
            unit: "blocks"
        }
    }

    HelperText {
        Layout.fillWidth: true
        color: root.messageIsError ? theme.danger : theme.text_secondary
        text: root.message !== "" ? root.message
            : qsTr("Select a line, train and destination to compute "
                + "speed and authority.")
    }

    LabeledDivider {
        Layout.fillWidth: true
        text: qsTr("or dispatch directly to a block")
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_3

        PickField {
            id: blockSelect
            Layout.fillWidth: true
            label: qsTr("Block on the selected line")
            model: root.host && root.line !== ""
                ? root.host.blockOptions(root.line) : []
            currentIndex: -1
        }

        AppButton {
            Layout.alignment: Qt.AlignBottom
            variant: "secondary"
            text: qsTr("Set authority")
            enabled: root.trainId !== "" && blockSelect.value !== ""
            onClicked: root.report(
                root.host.setAuthority(root.trainId, root.line,
                    blockSelect.value),
                qsTr("%1 given authority toward %2 block %3.")
                    .arg(root.trainId).arg(root.line)
                    .arg(blockSelect.value))
        }
    }

    AppButton {
        Layout.fillWidth: true
        variant: "primary"
        size: "large"
        text: root.train.destinationBlock
            ? qsTr("Reroute train") : qsTr("Dispatch train")
        enabled: root.trainId !== "" && destinationSelect.value !== ""
        onClicked: root.report(
            root.host.dispatchTrain(root.trainId, root.line,
                destinationSelect.value, arrivalField.text),
            qsTr("%1 dispatched to %2.").arg(root.trainId)
                .arg(destinationSelect.model[
                    destinationSelect.currentIndex].text))
    }
}
