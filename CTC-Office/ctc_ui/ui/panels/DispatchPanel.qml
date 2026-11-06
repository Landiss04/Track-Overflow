// Manual dispatch: pick a line, a train and a destination station (or a
// block directly); CTC computes the suggested speed and authority sent
// to the wayside, shown as soon as all three are picked. Picking a train
// that already has an order reroutes it.
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
    // What the readouts show: the train's live values once it runs to
    // the picked destination, else what dispatching it there would send
    // (``error`` says why nothing would).
    readonly property var computed: {
        if (!root.host || root.trainId === "" || destinationSelect.value === "")
            return root.train;
        if (root.train.tracked
                && root.train.destinationBlock === destinationSelect.value)
            return root.train;
        root.host.revision;
        return root.host.dispatchPreview(root.trainId, root.line,
                                         destinationSelect.value);
    }
    // Result of the last action: an error, or a confirmation. Cleared
    // by any new pick or edit, so it never outlives what it was about.
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
            onValueChanged: root.message = ""
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
            onValueChanged: root.message = ""
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
            onValueChanged: root.message = ""
        }

        ValueField {
            id: arrivalField
            Layout.preferredWidth: 120
            label: qsTr("Arrival (HH:MM)")
            onTextChanged: root.message = ""
        }
    }

    FieldLabel { text: qsTr("CTC COMPUTED — SENT TO TRACK CONTROLLER") }

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_2

        TelemetryReadout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            label: qsTr("Suggested speed")
            value: root.computed.suggestedSpeed || "—"
            unit: "mph"
        }
        TelemetryReadout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            label: qsTr("Authority")
            value: root.computed.authorityBlocks || "—"
            unit: "blocks"
        }
    }

    HelperText {
        Layout.fillWidth: true
        color: root.message !== ""
            ? (root.messageIsError ? theme.danger : theme.text_secondary)
            : root.computed.error ? theme.warning : theme.text_secondary
        text: root.message !== "" ? root.message
            : root.computed.error ? root.computed.error
            : root.computed.authorityBlocks
                && root.computed.authorityBlocks !== "—"
                && root.computed !== root.train
                ? qsTr("What the CTC sends once %1 is dispatched; "
                    + "recomputed every step after that.")
                    .arg(root.trainId)
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

        BlockField {
            id: blockSelect
            Layout.fillWidth: true
            label: qsTr("Block on the selected line")
            enabled: root.line !== ""
            model: root.host && root.line !== ""
                ? root.host.blockOptions(root.line) : []
            onValueChanged: root.message = ""
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
