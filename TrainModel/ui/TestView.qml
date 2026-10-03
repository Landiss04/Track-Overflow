// Test harness page. Every input the Train Model would receive from the
// Track Model or the Train Controller is supplied here instead, so the
// module can be run and graded on its own.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../ui"

ScrollView {
    id: root

    clip: true
    contentWidth: availableWidth

    RowLayout {
        width: root.availableWidth
        spacing: theme.space_5

        ColumnLayout {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignTop
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
                    + "a passenger brake latch. Brake failure still applies. "
                    + "Controls show live model state; pending edits are "
                    + "marked until sent. Boarding counts are consumed once.")
            }

            Card {
                Layout.fillWidth: true
                title: qsTr("Inputs")

                TableHeader { Layout.fillWidth: true }

                Repeater {
                    model: harness.inputDefinitions

                    delegate: SignalRow {
                        required property var modelData

                        Layout.fillWidth: true
                        objectName: "input-" + modelData.name
                        kind: modelData.kind
                        value: harness.displayInputValues[modelData.name]
                        unit: modelData.unit
                        editable: true
                        preserveActiveEdit: true
                        property bool pending: !!harness.pendingInputs[modelData.name]
                        name: modelData.name + (pending ? " (pending)" : "")
                        onEdited: function (newValue) {
                            harness.setDisplayInput(modelData.name, newValue);
                        }
                    }
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignTop
            Layout.margins: theme.space_5
            Layout.leftMargin: 0
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
                title: qsTr("Failure modes")

                StatusBadge {
                    label: harness.activeFailureCount > 0
                        ? harness.activeFailureCount + qsTr(" active")
                        : qsTr("Clear")
                    variant: harness.activeFailureCount > 0 ? "fault" : "ok"
                }

                Repeater {
                    model: harness.failures

                    delegate: RowLayout {
                        required property var modelData

                        Layout.fillWidth: true
                        spacing: theme.space_3

                        MonoText {
                            Layout.fillWidth: true
                            text: modelData.name
                        }

                        SegmentedToggle {
                            options: [qsTr("True"), qsTr("False")]
                            currentIndex: modelData.active ? 0 : 1
                            onActivated: function (index) {
                                harness.setFailure(
                                    modelData.name, index === 0);
                            }
                        }
                    }
                }

                HelperText {
                    Layout.fillWidth: true
                    text: qsTr("Test only: Murphy sets these from the Train "
                        + "Model window. Shown as the module reports them.")
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
                    Layout.fillWidth: true
                    Layout.topMargin: theme.space_2
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
