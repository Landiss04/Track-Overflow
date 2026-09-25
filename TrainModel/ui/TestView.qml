// Test harness page. Every input the Train Model would receive from the
// Track Model or the Train Controller is supplied here instead, so the
// module can be run and graded on its own.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "components"

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
                body: qsTr("Sending the inputs writes the declared "
                    + "pass-through signals into the module. The remaining "
                    + "outputs wait on the simulation.")
            }

            Card {
                Layout.fillWidth: true
                title: qsTr("Inputs")

                TableHeader { Layout.fillWidth: true }

                Repeater {
                    model: harness.inputs

                    delegate: SignalRow {
                        required property var modelData

                        Layout.fillWidth: true
                        name: modelData.name
                        kind: modelData.kind
                        value: modelData.value
                        unit: modelData.unit
                        editable: true
                        onEdited: function (newValue) {
                            harness.setInput(modelData.name, newValue);
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

                Repeater {
                    model: harness.outputs

                    delegate: SignalRow {
                        required property var modelData

                        Layout.fillWidth: true
                        name: modelData.name
                        kind: modelData.kind
                        value: modelData.value
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
                    label: trainModel.activeFailureCount > 0
                        ? trainModel.activeFailureCount + qsTr(" active")
                        : qsTr("Clear")
                    variant: trainModel.activeFailureCount > 0 ? "fault" : "ok"
                }

                Repeater {
                    model: trainModel.failures

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
                                trainModel.setFailure(
                                    modelData.name, index === 0);
                            }
                        }
                    }
                }

                HelperText {
                    Layout.fillWidth: true
                    text: qsTr("Set here because these are module state, not "
                        + "inputs from another module.")
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

                AppButton {
                    Layout.fillWidth: true
                    Layout.topMargin: theme.space_2
                    variant: "primary"
                    text: qsTr("Send inputs to train model")
                    onClicked: harness.sendInputs()
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
                    rule: false
                }
            }
        }
    }
}
