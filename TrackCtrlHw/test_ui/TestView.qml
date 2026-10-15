// Track Controller test page. It stands in for the CTC Office, the Track
// Model and the clock, and drives the Track Controller over the test link:
// every clock tick sends the inputs below and reads back the outputs. The
// signal set is the module interface diagram's and nothing else; the PLC
// program and the database are loaded in the Track Controller window.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../ui"

Item {
    id: root

    readonly property bool ready: harness.connected && harness.selectedBlock !== ""

    // One input or output row; greyed and empty where the block lacks the
    // equipment the signal needs.
    component SignalTableRow: SignalRow {
        required property var row
        required property bool inputs

        Layout.fillWidth: true
        opacity: row.applies ? 1.0 : 0.42
        name: row.name
        kind: row.kind
        value: row.value
        unit: row.unit
        options: row.options
        editable: inputs && row.applies
        onEdited: function (newValue) {
            harness.setInput(row.group, row.name, newValue);
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        ModuleHeader {
            Layout.fillWidth: true
            moduleName: qsTr("Track Controller \u2014 Test UI")
            instance: harness.selectedWayside === "" ? ""
                : qsTr("WAYSIDE %1").arg(harness.selectedWayside)
            mode: harness.maintenance ? qsTr("Maintenance") : ""
            line: harness.line === "" ? "" : qsTr("%1 Line").arg(harness.line)
            clock: harness.clockText
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
                    spacing: theme.space_4

                    Callout {
                        Layout.fillWidth: true
                        variant: harness.connected ? "info" : "warning"
                        heading: harness.connected
                            ? qsTr("Driving the Track Controller")
                            : qsTr("Not connected")
                        body: harness.connected
                            ? (harness.selectedBlock === ""
                                ? qsTr("Load a wayside database in the Track "
                                    + "Controller window; its blocks appear here.")
                                : qsTr("Every tick sends these inputs. Values "
                                    + "are in the interface's units (m/s, "
                                    + "blocks), not display units."))
                            : (harness.refusal !== "" ? harness.refusal
                                : qsTr("Start the Track Controller window. "
                                    + "This page connects to it by itself."))
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("Addressing")
                        enabled: harness.connected

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: theme.space_4

                            SelectField {
                                Layout.fillWidth: false
                                Layout.preferredWidth: 120
                                label: qsTr("Wayside")
                                model: harness.waysides
                                currentIndex: harness.waysides.indexOf(
                                    harness.selectedWayside)
                                onCommitted: function (value) {
                                    harness.selectWayside(value);
                                }
                            }

                            SelectField {
                                Layout.fillWidth: true
                                label: qsTr("Block")
                                model: harness.blocks
                                currentIndex: harness.blocks.indexOf(
                                    harness.selectedBlock)
                                onCommitted: function (value) {
                                    harness.selectBlock(value);
                                }
                            }
                        }

                        HelperText {
                            Layout.fillWidth: true
                            text: qsTr("All four tables show the selected "
                                + "block. A signal the block has no "
                                + "equipment for is greyed out.")
                        }
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("Inputs \u2014 from CTC Office")
                        enabled: root.ready

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: theme.space_3

                            MonoText {
                                Layout.fillWidth: true
                                text: "maintenance_mode"
                            }

                            MonoText {
                                Layout.preferredWidth: 64
                                text: "bool"
                                color: theme.text_muted
                            }

                            SegmentedToggle {
                                Layout.preferredWidth: 180
                                options: [qsTr("True"), qsTr("False")]
                                currentIndex: harness.maintenance ? 0 : 1
                                onActivated: function (index) {
                                    harness.setMaintenance(index === 0);
                                }
                            }

                            Item { Layout.preferredWidth: 52 }
                        }

                        HelperText {
                            Layout.fillWidth: true
                            text: qsTr("System-wide, not per block. "
                                + "switch_command is sent only while it is "
                                + "true.")
                        }

                        TableHeader { Layout.fillWidth: true }

                        Repeater {
                            model: harness.ctcInputs
                            delegate: SignalTableRow { inputs: true }
                        }
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("Inputs \u2014 from Track Model")
                        enabled: root.ready

                        TableHeader { Layout.fillWidth: true }

                        Repeater {
                            model: harness.trackModelInputs
                            delegate: SignalTableRow { inputs: true }
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
                    spacing: theme.space_4

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("Outputs \u2014 to CTC Office")

                        headerItems: Text {
                            text: harness.reportText
                            textFormat: Text.PlainText
                            color: theme.text_muted
                            font.family: theme.ui_family
                            font.pixelSize: theme.size_small
                        }

                        TableHeader { Layout.fillWidth: true }

                        Repeater {
                            model: harness.ctcOutputs
                            delegate: SignalTableRow { inputs: false }
                        }
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("Outputs \u2014 to Track Model")

                        TableHeader { Layout.fillWidth: true }

                        Repeater {
                            model: harness.trackModelOutputs
                            delegate: SignalTableRow { inputs: false }
                        }

                        HelperText {
                            Layout.fillWidth: true
                            text: qsTr("Read back from the module after "
                                + "each tick. An em dash means nothing is "
                                + "sent: no suggestion for this block, or "
                                + "no tick yet.")
                        }
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("Run control")
                        enabled: harness.connected

                        Callout {
                            Layout.fillWidth: true
                            visible: harness.errorText !== ""
                            variant: "warning"
                            heading: qsTr("Step rejected")
                            body: harness.errorText
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: theme.space_4

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

                            FormField {
                                Layout.fillWidth: true
                                label: qsTr("Speed")

                                SegmentedToggle {
                                    Layout.fillWidth: true
                                    options: ["1x", "10x"]
                                    currentIndex: harness.speed === 10 ? 1 : 0
                                    onActivated: function (index) {
                                        harness.setSpeed(index === 1 ? 10 : 1);
                                    }
                                }
                            }
                        }

                        AppButton {
                            Layout.fillWidth: true
                            Layout.topMargin: theme.space_2
                            variant: "primary"
                            text: harness.pendingEdits > 0
                                ? qsTr("Send inputs (%1 unsent)").arg(harness.pendingEdits)
                                : qsTr("Send inputs")
                            tooltip: qsTr("Send now: advances the clock one tick")
                            onClicked: harness.sendInputs()
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: theme.space_3

                            PositiveIntField {
                                Layout.fillWidth: false
                                Layout.preferredWidth: 120
                                label: qsTr("Ticks")
                                modelValue: harness.tickStep
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
                            label: qsTr("Inputs last sent")
                            value: harness.lastSent
                            rule: false
                        }
                    }
                }
            }
        }
    }
}
