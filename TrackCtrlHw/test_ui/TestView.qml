// Track Controller test page. Every input the wayside controller would
// receive from the CTC Office, the Track Model and the programmer is
// supplied here, and every output it sends back to the CTC Office and the
// Track Model is read back here. The signal set is the one on the module
// interface diagram and nothing else.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtQuick.Layouts
import "../../ui"

Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        ModuleHeader {
            Layout.fillWidth: true
            moduleName: qsTr("Track Controller \u2014 Test UI")
            instance: qsTr("WAYSIDE 1")
            line: qsTr("Green Line")
            clock: harness.elapsed
        }

        ScrollView {
            id: scroller

            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth

            RowLayout {
                width: scroller.availableWidth
                spacing: theme.space_5

                // ---- inputs, driven from this page ----------------------
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.alignment: Qt.AlignTop
                    Layout.margins: theme.space_5
                    Layout.rightMargin: 0
                    spacing: theme.space_5

                    Callout {
                        Layout.fillWidth: true
                        heading: qsTr("Test harness \u2014 module driven "
                            + "from this page")
                        body: qsTr("Values are the interface units the "
                            + "signals carry, not display units. Sending "
                            + "the inputs resolves the declared "
                            + "pass-through outputs; the rest wait on the "
                            + "PLC program.")
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("Addressing")

                        SelectField {
                            Layout.fillWidth: true
                            label: qsTr("Block")
                            model: harness.blocks
                            currentIndex: harness.blocks.indexOf(
                                harness.selectedBlock)
                            onCommitted: function (value) {
                                harness.setSelectedBlock(value);
                            }
                        }

                        HelperText {
                            Layout.fillWidth: true
                            text: qsTr("Every signal on this page is read "
                                + "and written for the selected block. A "
                                + "signal the block has no equipment for is "
                                + "greyed out.")
                        }
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("Inputs \u2014 from CTC Office")

                        TableHeader { Layout.fillWidth: true }

                        Repeater {
                            model: harness.ctcInputs

                            delegate: SignalRow {
                                required property var modelData

                                Layout.fillWidth: true
                                opacity: modelData.applies ? 1.0 : 0.42
                                name: modelData.name
                                kind: modelData.kind
                                value: modelData.value
                                unit: modelData.unit
                                options: modelData.options !== undefined
                                    ? modelData.options : []
                                editable: modelData.applies
                                onEdited: function (newValue) {
                                    harness.setInput("ctc", modelData.name,
                                        newValue);
                                }
                            }
                        }
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("Inputs \u2014 from Track Model")

                        TableHeader { Layout.fillWidth: true }

                        Repeater {
                            model: harness.trackModelInputs

                            delegate: SignalRow {
                                required property var modelData

                                Layout.fillWidth: true
                                opacity: modelData.applies ? 1.0 : 0.42
                                name: modelData.name
                                kind: modelData.kind
                                value: modelData.value
                                unit: modelData.unit
                                options: modelData.options !== undefined
                                    ? modelData.options : []
                                editable: modelData.applies
                                onEdited: function (newValue) {
                                    harness.setInput("track_model",
                                        modelData.name, newValue);
                                }
                            }
                        }
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("Input \u2014 from programmer")

                        KeyValueRow {
                            Layout.fillWidth: true
                            label: qsTr("PLC program")
                            value: harness.programName === ""
                                ? "\u2014" : harness.programName
                        }

                        AppButton {
                            Layout.fillWidth: true
                            variant: "secondary"
                            text: qsTr("Upload .plc program")
                            onClicked: programDialog.open()
                        }
                    }
                }

                // ---- outputs, read back from the module ----------------
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.alignment: Qt.AlignTop
                    Layout.margins: theme.space_5
                    Layout.leftMargin: 0
                    spacing: theme.space_5

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("Outputs \u2014 to CTC Office")

                        TableHeader { Layout.fillWidth: true }

                        Repeater {
                            model: harness.ctcOutputs

                            delegate: SignalRow {
                                required property var modelData

                                Layout.fillWidth: true
                                opacity: modelData.applies ? 1.0 : 0.42
                                name: modelData.name
                                kind: modelData.kind
                                value: modelData.value
                                unit: modelData.unit
                            }
                        }
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("Outputs \u2014 to Track Model")

                        TableHeader { Layout.fillWidth: true }

                        Repeater {
                            model: harness.trackModelOutputs

                            delegate: SignalRow {
                                required property var modelData

                                Layout.fillWidth: true
                                opacity: modelData.applies ? 1.0 : 0.42
                                name: modelData.name
                                kind: modelData.kind
                                value: modelData.value
                                unit: modelData.unit
                            }
                        }

                        HelperText {
                            Layout.fillWidth: true
                            text: qsTr("Read back from the module. An em "
                                + "dash means the signal waits on the PLC "
                                + "program.")
                        }
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("Run control")

                        FormField {
                            Layout.fillWidth: true
                            label: qsTr("Clock")

                            SegmentedToggle {
                                Layout.fillWidth: true
                                options: [qsTr("Run"), qsTr("Hold")]
                                currentIndex: harness.running ? 0 : 1
                                onActivated: function (index) {
                                    harness.setRunning(index === 0);
                                }
                            }
                        }

                        AppButton {
                            Layout.fillWidth: true
                            Layout.topMargin: theme.space_2
                            variant: "primary"
                            text: qsTr("Send inputs to track controller")
                            onClicked: harness.sendInputs()
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: theme.space_3

                            ValueField {
                                Layout.preferredWidth: 120
                                label: qsTr("Ticks")
                                kind: "int"
                                text: String(harness.tickStep)
                                onCommitted: function (value) {
                                    harness.setTickStep(value);
                                }
                            }

                            AppButton {
                                Layout.fillWidth: true
                                Layout.alignment: Qt.AlignBottom
                                variant: "secondary"
                                text: qsTr("Advance")
                                onClicked: harness.advanceTicks()
                            }

                            AppButton {
                                Layout.fillWidth: true
                                Layout.alignment: Qt.AlignBottom
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
    }

    FileDialog {
        id: programDialog

        title: qsTr("Select a PLC program")
        nameFilters: [qsTr("PLC program (*.plc)"), qsTr("All files (*)")]
        onAccepted: harness.loadProgram(String(selectedFile))
    }
}
