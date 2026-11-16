// Manual dispatch: pick a line, a train and a stop (a station, or any
// block of the line), with an optional arrival time. A train with no
// order is dispatched to it ("Dispatch train"); a train with one gets
// it queued after its last stop ("Queue stop"). The train's stops are
// listed below: it heads for the first, dwells there (D007), then
// heads for the next, and stays at the last. The dispatcher removes a
// stop with its ×, and reorders them by dragging a card or with its
// arrows. CTC computes the suggested speed and authority sent to the
// wayside, shown as soon as a stop is picked.
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
    // The Destination station entry for the yard (R66, D022); no block
    // ID is "yard".
    readonly property string yardValue: "yard"
    // 0: a station; 1: any block of the line (REQ-FUNC-009).
    property int stopKind: 0
    readonly property string destination: root.stopKind === 0
        ? stationSelect.value : blockSelect.value
    readonly property bool yardPicked: root.stopKind === 0
        && stationSelect.value === yardValue
    // The selected train's current row; re-read whenever the module
    // changes.
    readonly property var train: {
        if (!root.host || root.trainId === "")
            return ({});
        root.host.revision;
        return root.host.trainDetail(root.trainId);
    }
    // "Dispatch train" for a train with no order, else "Queue stop".
    readonly property string action: {
        if (!root.host || root.trainId === "")
            return qsTr("Dispatch train");
        root.host.revision;
        return root.host.stopAction(root.trainId);
    }
    readonly property bool queueing: root.action === "Queue stop"
    // The selected train's stops, the one it is heading for first.
    readonly property var stops: root.host && root.trainId !== ""
        ? (root.host.stopQueues[root.trainId] || []) : []

    // The stops' blocks as the list shows them: an action on a stop is
    // refused if the train has moved on since (``CtcHost.removeStop``).
    function shownBlocks() {
        return root.stops.map(stop => stop.block);
    }

    // What the readouts show: the train's live values once it has an
    // order, else what dispatching it to the picked stop would send
    // (``error`` says why nothing would).
    readonly property var computed: {
        if (!root.host || root.trainId === "" || root.queueing
                || root.destination === "")
            return root.train;
        // The yard is not a block, so there is nothing to preview.
        if (root.yardPicked)
            return root.train.tracked ? root.train
                : ({ error: qsTr("Only a train on the track can be sent "
                    + "back to the yard.") });
        root.host.revision;
        return root.host.dispatchPreview(root.trainId, root.line,
                                         root.destination);
    }
    // Result of the last action: an error, or a confirmation. Cleared
    // by any new pick or edit, so it never outlives what it was about.
    property string message: ""
    property bool messageIsError: false

    function report(error, done) {
        root.messageIsError = error !== "";
        root.message = error !== "" ? error : done;
    }

    function stopName() {
        if (root.stopKind === 1)
            return qsTr("block %1").arg(blockSelect.value);
        return stationSelect.model[stationSelect.currentIndex].text;
    }

    function submit() {
        if (root.yardPicked) {
            // Queued after its other stops, like any station; the yard
            // stays its last stop (``CtcOffice.return_to_yard``).
            const queued = root.queueing;
            const error = root.host.returnToYard(root.trainId);
            if (error === "")
                stationSelect.clear();
            root.report(error, queued
                ? qsTr("Yard queued for %1, after its other stops.")
                    .arg(root.trainId)
                : qsTr("%1 sent back to the yard.").arg(root.trainId));
            return;
        }
        const queued = root.queueing;
        const name = root.stopName();
        const error = root.host.addStop(root.trainId, root.line,
                                        root.destination, arrivalField.text);
        if (error === "") {
            // Ready for the next stop (which clears the message too).
            stationSelect.clear();
            blockSelect.clear();
            arrivalField.text = "";
        }
        root.report(error, queued
            ? qsTr("%1 queued for %2.").arg(name).arg(root.trainId)
            : qsTr("%1 dispatched to %2.").arg(root.trainId).arg(name));
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
            objectName: "dispatch-line"
            Layout.preferredWidth: 110
            label: qsTr("Line")
            model: root.host ? root.host.lineNames : []
            currentIndex: -1
            onValueChanged: root.message = ""
        }

        PickField {
            id: trainSelect
            objectName: "dispatch-train"
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

        ColumnLayout {
            Layout.fillWidth: true
            spacing: theme.space_1

            FieldLabel { text: qsTr("STOP AT") }

            SegmentedToggle {
                objectName: "stop-kind"
                options: [qsTr("Station"), qsTr("Block")]
                currentIndex: root.stopKind
                onActivated: function (index) {
                    root.stopKind = index;
                    root.message = "";
                }
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_3

        PickField {
            id: stationSelect
            objectName: "stop-station"
            Layout.fillWidth: true
            visible: root.stopKind === 0
            label: qsTr("Station")
            textRole: "text"
            valueRole: "value"
            // The yard first, then the stations. Picking it queues the
            // yard as a train's last stop, after the ones it has, where
            // it is retired; a train with no stops goes there at once.
            model: root.host && root.line !== ""
                ? [{ value: root.yardValue,
                     text: qsTr("Yard · return and retire") }]
                    .concat(root.host.stationOptions(root.line))
                : []
            currentIndex: -1
            onValueChanged: root.message = ""
        }

        BlockField {
            id: blockSelect
            objectName: "stop-block"
            Layout.fillWidth: true
            visible: root.stopKind === 1
            label: qsTr("Block on the selected line")
            enabled: root.line !== ""
            model: root.host && root.line !== ""
                ? root.host.blockOptions(root.line) : []
            onValueChanged: root.message = ""
        }

        ValueField {
            id: arrivalField
            objectName: "stop-arrival"
            Layout.fillWidth: false
            Layout.preferredWidth: 120
            label: qsTr("Arrival (HH:MM)")
            enabled: !root.yardPicked
            onTextChanged: root.message = ""
        }

        AppButton {
            id: submitButton
            objectName: "stop-submit"
            Layout.alignment: Qt.AlignBottom
            Layout.preferredWidth: 150
            variant: "primary"
            text: root.yardPicked && !root.queueing
                ? qsTr("Return to yard") : root.action
            enabled: root.trainId !== "" && root.destination !== ""
                && (!root.yardPicked || root.train.tracked === true)
            onClicked: root.submit()
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
        objectName: "dispatch-message"
        Layout.fillWidth: true
        color: root.message !== ""
            ? (root.messageIsError ? theme.danger : theme.text_secondary)
            : root.computed.error ? theme.warning : theme.text_secondary
        text: root.message !== "" ? root.message
            : root.computed.error ? root.computed.error
            : root.queueing
                ? qsTr("%1's live values. A queued stop is added after "
                    + "its last; it dwells at each stop, then goes on to "
                    + "the next.").arg(root.trainId)
            : root.computed.authorityBlocks
                && root.computed.authorityBlocks !== "—"
                && root.computed !== root.train
                ? qsTr("What the CTC sends once %1 is dispatched; "
                    + "recomputed every step after that.")
                    .arg(root.trainId)
            : qsTr("Select a line, train and stop to compute speed and "
                + "authority.")
    }

    StopList {
        Layout.fillWidth: true
        trainId: root.trainId
        stops: root.stops
        onRemoveRequested: function (index) {
            root.report(root.host.removeStop(root.trainId, index,
                                             root.shownBlocks()),
                qsTr("Stop removed from %1.").arg(root.trainId));
        }
        onMoveRequested: function (from, to) {
            root.report(root.host.moveStop(root.trainId, from, to,
                                           root.shownBlocks()),
                qsTr("%1's stops reordered.").arg(root.trainId));
        }
    }
}
