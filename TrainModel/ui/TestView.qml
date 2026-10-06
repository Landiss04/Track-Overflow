// Test harness page. Every input the Train Model would receive from the
// Track Model or the Train Controller is supplied here instead, so the
// module can be run and graded on its own.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../ui"

Item {
    id: root

    // Sizes one input row slot: the tallest row, an editor with its label.
    SignalRow {
        id: rowProbe
        visible: false
        name: "probe"
        kind: "float"
        // A valid value, so no validation message adds to the height.
        value: 0
        unit: "mph"
        editable: true
    }

    RowLayout {
        anchors.fill: parent
        spacing: theme.space_5

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: 1
            Layout.margins: theme.space_5
            Layout.rightMargin: 0
            spacing: theme.space_5

            Callout {
                Layout.fillWidth: true
                heading: qsTr("Test harness \u2014 module driven from this page")
                body: qsTr("Sending the inputs hands them to the Train Model "
                    + "and advances one tick. Each later tick reuses the last "
                    + "sent inputs; passengers board once per send, only at "
                    + "a station with a door open. Doors open only at 0 mph. "
                    + "Select emergency_brake_command and send to override "
                    + "a passenger brake latch. Failures are set in the Train "
                    + "Model window. Controls show live model state; pending "
                    + "edits are marked until sent. Boarding counts are "
                    + "consumed once.")
            }

            Card {
                Layout.fillWidth: true
                Layout.fillHeight: true
                fillBody: true
                title: qsTr("Inputs")

                TableHeader { Layout.fillWidth: true }

                // Scrolls in place and wraps around: after the last input
                // comes the first again. Only the rows that fit are shown.
                PathView {
                    id: inputList

                    readonly property real slot: rowProbe.implicitHeight
                        + theme.space_3
                    // Wheel travel not yet turned into a whole row.
                    property real wheelRemainder: 0

                    objectName: "inputList"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: harness.inputDefinitions
                    pathItemCount: Math.max(
                        1, Math.min(count, Math.floor(height / slot)))
                    // Every row stays alive off the path, so scrolling
                    // never drops an edit in progress.
                    cacheItemCount: Math.max(0, count - pathItemCount)
                    // The current row is the top row.
                    preferredHighlightBegin: 0
                    preferredHighlightEnd: 0
                    highlightRangeMode: PathView.StrictlyEnforceRange
                    highlightMoveDuration: 120
                    snapMode: PathView.SnapOneItem

                    path: Path {
                        startX: inputList.width / 2
                        startY: inputList.slot / 2

                        PathLine {
                            x: inputList.width / 2
                            y: inputList.slot / 2
                                + inputList.pathItemCount * inputList.slot
                        }
                    }

                    delegate: Item {
                        id: slotItem

                        required property var modelData

                        width: inputList.width
                        height: inputList.slot

                        SignalRow {
                            property bool pending:
                                !!harness.pendingInputs[slotItem.modelData.name]

                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            objectName: "input-" + slotItem.modelData.name
                            kind: slotItem.modelData.kind
                            value: harness.displayInputValues[
                                slotItem.modelData.name]
                            unit: slotItem.modelData.unit
                            editable: true
                            name: slotItem.modelData.name
                                + (pending ? " (pending)" : "")
                            onEdited: function (newValue) {
                                harness.setDisplayInput(
                                    slotItem.modelData.name, newValue);
                            }
                        }
                    }

                    WheelHandler {
                        onWheel: function (event) {
                            // One row per wheel notch; trackpads send
                            // smaller steps, so they add up first.
                            inputList.wheelRemainder += event.angleDelta.y;
                            while (inputList.wheelRemainder <= -120) {
                                inputList.wheelRemainder += 120;
                                inputList.incrementCurrentIndex();
                            }
                            while (inputList.wheelRemainder >= 120) {
                                inputList.wheelRemainder -= 120;
                                inputList.decrementCurrentIndex();
                            }
                        }
                    }
                }
            }
        }

        // The output and run-control cards can be taller than the window,
        // so this column scrolls on its own.
        ScrollView {
            id: rightColumn

            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: 1
            Layout.topMargin: theme.space_5
            Layout.bottomMargin: theme.space_5
            Layout.rightMargin: theme.space_5
            clip: true
            contentWidth: availableWidth

            ColumnLayout {
                width: rightColumn.availableWidth
                spacing: theme.space_5

                Card {
                    Layout.fillWidth: true
                    title: qsTr("Outputs")

                    TableHeader { Layout.fillWidth: true }

                    // Stable rows bound to a value map: rebuilding every row on
                    // each tick cannot keep up with 10x.
                    Repeater {
                        model: harness.outputDefinitions

                        delegate: SignalRow {
                            required property var modelData

                            Layout.fillWidth: true
                            objectName: "output-" + modelData.name
                            name: modelData.name
                            kind: modelData.kind
                            value: harness.outputValues[modelData.name]
                            unit: modelData.unit
                        }
                    }

                    HelperText {
                        Layout.fillWidth: true
                        text: qsTr("Read back from the module. Values refresh "
                            + "whenever the module state changes.")
                    }
                }

                Card {
                    Layout.fillWidth: true
                    title: qsTr("Run control")
                    Text {
                        Layout.fillWidth: true
                        text: qsTr("Clock")
                        color: theme.text_secondary
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_small
                        font.weight: theme.weight_regular
                    }

                    SegmentedToggle {
                        Layout.fillWidth: true
                        options: [qsTr("Run"), qsTr("Hold")]
                        currentIndex: harness.running ? 0 : 1
                        onActivated: function (index) {
                            harness.setRunning(index === 0);
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        Layout.topMargin: theme.space_2
                        text: qsTr("Speed")
                        color: theme.text_secondary
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_small
                        font.weight: theme.weight_regular
                    }

                    // One segment per speed the shared clock accepts. Speed
                    // changes how often ticks happen, never dt.
                    SegmentedToggle {
                        objectName: "speedToggle"
                        Layout.fillWidth: true
                        options: harness.speeds.map(function (speed) {
                            return qsTr("%1x").arg(speed);
                        })
                        currentIndex: harness.speeds.indexOf(harness.speed)
                        onActivated: function (index) {
                            harness.setSpeed(harness.speeds[index]);
                        }
                    }

                    AppButton {
                        Layout.fillWidth: true
                        Layout.topMargin: theme.space_2
                        variant: "primary"
                        text: qsTr("Send inputs to train model")
                        onClicked: harness.sendInputs()
                    }

                    HelperText {
                        objectName: "inputError"
                        Layout.fillWidth: true
                        visible: harness.inputError !== ""
                        text: qsTr("Inputs not sent: ") + harness.inputError
                        color: theme.danger
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: theme.space_3

                        AppButton {
                            Layout.fillWidth: true
                            variant: "secondary"
                            text: qsTr("Advance one tick")
                            onClicked: harness.advanceTick()
                        }

                        AppButton {
                            Layout.fillWidth: true
                            variant: "secondary"
                            text: qsTr("Reset module")
                            onClicked: harness.resetModule()
                        }
                    }

                    KeyValueRow {
                        objectName: "track"
                        Layout.fillWidth: true
                        Layout.topMargin: theme.space_2
                        label: qsTr("Track")
                        value: harness.trackName
                    }

                    // The stand-in Train Controller lowers the entered
                    // power to hold the speed at or below this cap.
                    KeyValueRow {
                        objectName: "speedLimiter"
                        Layout.fillWidth: true
                        label: qsTr("Speed limiter")
                        value: qsTr("%1 mph cap").arg(
                                harness.speedCap.toFixed(1))
                            + (harness.limiting ? qsTr(" · limiting") : "")
                    }

                    // The stand-in Train Controller holds the train at a
                    // station for the 45 s dwell (D007) once a door opens.
                    KeyValueRow {
                        objectName: "dwell"
                        Layout.fillWidth: true
                        label: qsTr("Station dwell")
                        value: harness.dwellLeft > 0
                            ? qsTr("%1 s left").arg(
                                Math.ceil(harness.dwellLeft - 1e-9))
                            : "—"
                    }

                    KeyValueRow {
                        Layout.fillWidth: true
                        label: qsTr("Tick")
                        value: String(harness.tick)
                    }

                    KeyValueRow {
                        Layout.fillWidth: true
                        label: qsTr("dt")
                        value: Number(harness.dt).toFixed(3) + " s"
                    }

                    KeyValueRow {
                        Layout.fillWidth: true
                        label: qsTr("Elapsed")
                        value: harness.elapsed
                    }

                    // Checked every 30 clock ticks: ticks the shared clock
                    // spent that the Train Model did not take.
                    KeyValueRow {
                        objectName: "clockDrift"
                        Layout.fillWidth: true
                        label: qsTr("Clock drift")
                        value: (harness.driftTicks === 1 ? qsTr("1 tick")
                                : qsTr("%1 ticks").arg(harness.driftTicks))
                            + qsTr(" (%1 s)").arg(
                                (harness.driftTicks * harness.dt).toFixed(1))
                        rule: false
                    }

                    HelperText {
                        objectName: "driftWarning"
                        Layout.fillWidth: true
                        visible: harness.driftTicks > 0
                        text: qsTr("The Train Model is behind the shared "
                            + "clock. Reset the module to realign them.")
                        color: theme.warning
                    }
                }
            }
        }
    }
}
