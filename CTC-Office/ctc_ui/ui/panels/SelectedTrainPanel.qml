// Selected train. Shows an empty state until a train is picked in the
// Train Occupancy window, then the train's live readouts. In Manual
// mode (canReroute) the dispatcher can also change where it is going.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../../../ui"
import "../components"

Panel {
    id: root

    property string trainId: ""
    // The CtcHost from __main__.py.
    property var host: null
    property bool canReroute: false
    readonly property bool hasSelection: trainId !== ""
    // The train's current row; re-read whenever the module changes.
    readonly property var train: {
        if (!root.host || root.trainId === "")
            return ({});
        root.host.revision;
        return root.host.trainDetail(root.trainId);
    }
    // The train's route for the chips below: CtcHost.routeDetail.
    readonly property var route: {
        if (!root.host || root.trainId === "")
            return ({ chips: [], summary: "" });
        root.host.revision;
        return root.host.routeDetail(root.trainId);
    }
    // When it should get there, from where it is now
    // (CtcHost.arrivalEstimate): re-read as the clock runs too, so a
    // train that waits is never shown arriving in the past.
    readonly property var arrival: {
        if (!root.host || root.trainId === "")
            return ({});
        root.host.revision;
        root.host.clockSecond;
        return root.host.arrivalEstimate(root.trainId);
    }
    property string message: ""
    property bool messageIsError: false
    // The New destination entry for the yard; no block ID is "yard".
    readonly property string yardValue: "yard"

    function show(field) {
        return root.train[field] || "—";
    }

    function report(error, done) {
        root.messageIsError = error !== "";
        root.message = error !== "" ? error : done;
    }

    onTrainIdChanged: message = ""

    signal clearRequested()

    title: !hasSelection ? qsTr("Selected train")
        : train.line ? qsTr("Train %1 · %2 line")
            .arg(trainId).arg(train.line)
        : qsTr("Selected train — %1").arg(trainId)

    headerItems: [
        AppButton {
            variant: "ghost"
            size: "small"
            text: qsTr("Clear")
            visible: root.hasSelection
            onClicked: root.clearRequested()
        }
    ]

    Item {
        Layout.fillWidth: true
        Layout.fillHeight: true
        visible: !root.hasSelection

        EmptyState {
            anchors.centerIn: parent
            heading: qsTr("No train selected")
            body: qsTr("Open the Train Occupancy window and pick a train. "
                + "Its route highlights on the track view and its metrics "
                + "load here.")
        }
    }

    // Scrolls when the panel is short (Manual mode) so the reroute
    // controls stay reachable.
    ScrollView {
        id: detailScroll
        Layout.fillWidth: true
        Layout.fillHeight: true
        visible: root.hasSelection
        contentWidth: availableWidth
        clip: true

        ColumnLayout {
            width: detailScroll.availableWidth
            spacing: theme.space_3

            GridLayout {
                Layout.fillWidth: true
                columns: root.width >= 560 ? 3 : 2
                columnSpacing: theme.space_2
                rowSpacing: theme.space_2

                TelemetryReadout {
                    Layout.fillWidth: true
                    label: qsTr("Current block")
                    value: root.show("block")
                }
                TelemetryReadout {
                    Layout.fillWidth: true
                    // The speed the CTC suggests; its actual speed is
                    // never known. "Suggested speed" is cut off when
                    // the readouts run two to a row.
                    label: qsTr("Suggested")
                    value: root.show("suggestedSpeed")
                    unit: "mph"
                }
                TelemetryReadout {
                    Layout.fillWidth: true
                    label: qsTr("Authority")
                    value: root.show("authorityBlocks")
                    unit: "blocks"
                }
                TelemetryReadout {
                    Layout.fillWidth: true
                    // The estimate; the requested time until the
                    // train is on the track.
                    label: root.arrival.time ? qsTr("Est. arrival")
                        : qsTr("Arrival")
                    value: root.arrival.time || root.show("eta")
                }
                TelemetryReadout {
                    Layout.fillWidth: true
                    // Minutes after (+) or before (-) the requested
                    // arrival.
                    label: qsTr("Deviation")
                    value: root.arrival.deviation || "—"
                    unit: "min"
                }
            }

            FieldLabel { text: qsTr("ROUTE — HIGHLIGHTED ON TRACK VIEW") }

            // Route blocks (style guide 6.4): the train's own block, the
            // blocks within its authority, and the block it stops before.
            Flow {
                Layout.fillWidth: true
                spacing: theme.space_1
                visible: root.route.chips.length > 0

                Repeater {
                    model: root.route.chips

                    // A block, or "+n more" for authority blocks left out.
                    delegate: Item {
                        id: chip
                        required property var modelData
                        readonly property bool isMore:
                            modelData.more !== undefined
                        width: isMore ? more.implicitWidth
                            : block.implicitWidth
                        height: block.implicitHeight

                        TrackBlock {
                            id: block
                            visible: !chip.isMore
                            blockId: chip.modelData.block || ""
                            occupancy: chip.modelData.occupancy || "free"
                        }

                        HelperText {
                            id: more
                            visible: chip.isMore
                            anchors.verticalCenter: parent.verticalCenter
                            text: qsTr("+%1 more").arg(chip.modelData.more)
                        }
                    }
                }
            }

            HelperText {
                Layout.fillWidth: true
                visible: root.route.summary !== ""
                text: root.route.summary
            }

            KeyValueRow {
                Layout.fillWidth: true
                label: qsTr("Destination")
                value: root.show("destination")
            }
            KeyValueRow {
                Layout.fillWidth: true
                label: qsTr("Authority to")
                value: root.show("authorityEnd")
            }
            KeyValueRow {
                Layout.fillWidth: true
                label: qsTr("Limited by")
                value: root.show("authorityLimit")
            }
            KeyValueRow {
                Layout.fillWidth: true
                label: qsTr("Status")
                value: root.show("status")
            }
            KeyValueRow {
                Layout.fillWidth: true
                label: qsTr("Due")
                value: root.show("eta")
            }
            KeyValueRow { Layout.fillWidth: true; label: qsTr("Next station") }
            KeyValueRow {
                Layout.fillWidth: true
                label: qsTr("Dwell at next stop")
            }

            // Reroute (Manual mode): a new destination replaces the order.
            ColumnLayout {
                Layout.fillWidth: true
                visible: root.canReroute
                spacing: theme.space_2

                LabeledDivider {
                    Layout.fillWidth: true
                    text: qsTr("change route")
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: theme.space_3

                    PickField {
                        id: rerouteSelect
                        Layout.fillWidth: true
                        label: qsTr("New destination")
                        textRole: "text"
                        valueRole: "value"
                        // The yard first (R66, D022), then the stations.
                        // Picking it sends the train back to the yard,
                        // as the Return to yard button does.
                        model: root.host && root.train.line
                            ? [{ value: root.yardValue,
                                 text: qsTr("Yard · return and retire") }]
                                .concat(root.host.stationOptions(
                                    root.train.line))
                            : []
                        currentIndex: -1
                    }

                    ValueField {
                        id: rerouteArrival
                        Layout.preferredWidth: 110
                        label: qsTr("Arrival (HH:MM)")
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: theme.space_2

                    AppButton {
                        Layout.fillWidth: true
                        variant: "primary"
                        text: qsTr("Reroute")
                        enabled: rerouteSelect.value !== ""
                            && (rerouteSelect.value !== root.yardValue
                                || root.train.tracked === true)
                        onClicked: rerouteSelect.value === root.yardValue
                            ? root.report(
                                root.host.returnToYard(root.trainId),
                                qsTr("%1 sent back to the yard.")
                                    .arg(root.trainId))
                            : root.report(
                                root.host.dispatchTrain(root.trainId,
                                    root.train.line, rerouteSelect.value,
                                    rerouteArrival.text),
                                qsTr("%1 rerouted.").arg(root.trainId))
                    }

                    // Return to yard (R66, D022): an order to the yard
                    // entry block, where the train is retired. Only a
                    // train on the track can be sent back.
                    AppButton {
                        variant: "secondary"
                        text: qsTr("Return to yard")
                        enabled: root.train.tracked === true
                        onClicked: root.report(
                            root.host.returnToYard(root.trainId),
                            qsTr("%1 sent back to the yard.")
                                .arg(root.trainId))
                    }
                }

                HelperText {
                    Layout.fillWidth: true
                    visible: root.message !== ""
                    color: root.messageIsError ? theme.danger
                        : theme.text_secondary
                    text: root.message
                }
            }
        }
    }
}
