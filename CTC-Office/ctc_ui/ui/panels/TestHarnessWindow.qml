// Test harness window. Forces every CTC input and reads back every output
// so the module can be exercised on its own, following the Train Model
// test harness template. No IO is declared yet, so both tables are empty;
// bind `inputs` and `outputs` once the CTC interface is defined.
//
// Each row is { name, kind, value, unit } where kind is
// "bool" | "int" | "float" | "string", matching SignalRow.
//
// Like OccupancyWindow, this is a plain item on the design canvas rather
// than a Popup so it stays inside the canvas scale transform.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"
import "../../../../ui"

Rectangle {
    id: root

    property var inputs: []
    property var outputs: []
    // True once a module backend is attached to the harness.
    property bool connected: false
    // Dummy preview: swaps in example rows so the populated layout can be
    // seen before any IO is declared. Remove once real signals exist.
    property bool previewing: false

    readonly property var shownInputs: previewing ? previewInputs : inputs
    readonly property var shownOutputs: previewing ? previewOutputs : outputs

    readonly property var previewInputs: [
        { name: "sample_bool", kind: "bool", value: true,
          unit: "" },
        { name: "sample_float", kind: "float", value: 12.5,
          unit: "m/s" },
        { name: "sample_int", kind: "int", value: 3, unit: "" },
        { name: "sample_string", kind: "string", value: "BLOCK A",
          unit: "" }
    ]
    readonly property var previewOutputs: [
        { name: "sample_float", kind: "float", value: 17.9,
          unit: "m/s" },
        { name: "sample_bool", kind: "bool", value: false,
          unit: "" },
        { name: "sample_unset", kind: "float", value: "",
          unit: "m" }
    ]

    signal closeRequested()
    signal inputEdited(string name, var value)
    signal sendInputsRequested()
    signal resetInputsRequested()

    color: theme.bg_surface
    border.color: theme.border
    border.width: 1
    radius: theme.radius_lg
    clip: true
    focus: visible

    Keys.onEscapePressed: root.closeRequested()

    function signalCount(count) {
        return count === 1 ? qsTr("1 signal") : qsTr("%1 signals").arg(count);
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 1
        spacing: 0

        // Title bar.
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: theme.control_h_lg + theme.space_2
            Layout.leftMargin: theme.space_4
            Layout.rightMargin: theme.space_2
            spacing: theme.space_3

            Text {
                text: qsTr("Test harness")
                color: theme.text_primary
                font.family: theme.ui_family
                font.pixelSize: theme.size_h3
                font.weight: theme.weight_bold
            }

            StatusBadge {
                label: root.connected ? qsTr("Connected")
                    : qsTr("Not connected")
                variant: root.connected ? "ok" : "idle"
            }

            StatusBadge {
                label: qsTr("Preview data")
                variant: "warning"
                visible: root.previewing
            }

            Item { Layout.fillWidth: true }

            AppButton {
                variant: "secondary"
                size: "small"
                text: root.previewing ? qsTr("Hide preview")
                    : qsTr("Show preview")
                onClicked: root.previewing = !root.previewing
            }

            AppButton {
                variant: "ghost"
                size: "small"
                text: "×"
                Accessible.name: qsTr("Close test harness")
                onClicked: root.closeRequested()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 1
            color: theme.border
        }

        ScrollView {
            id: scroller

            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth

            ColumnLayout {
                width: scroller.availableWidth
                spacing: theme.space_4

                ModeCallout {
                    Layout.fillWidth: true
                    Layout.topMargin: theme.space_4
                    Layout.leftMargin: theme.space_4
                    Layout.rightMargin: theme.space_4
                    heading: qsTr("Force inputs, read outputs")
                    body: qsTr("Inputs set here replace what the CTC would "
                        + "receive from the track controllers and MBO. "
                        + "Outputs are read back from the module after the "
                        + "inputs are sent.")
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: theme.space_4
                    Layout.rightMargin: theme.space_4
                    Layout.bottomMargin: theme.space_4
                    spacing: theme.space_4

                    Panel {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        Layout.alignment: Qt.AlignTop
                        title: qsTr("Inputs")

                        headerItems: [
                            HelperText {
                                text: root.signalCount(
                                    root.shownInputs.length)
                                color: theme.text_muted
                            }
                        ]

                        TableHeader { Layout.fillWidth: true }

                        Repeater {
                            model: root.shownInputs

                            delegate: SignalRow {
                                required property var modelData

                                Layout.fillWidth: true
                                name: modelData.name
                                kind: modelData.kind
                                value: modelData.value
                                unit: modelData.unit
                                editable: true
                                onEdited: function (newValue) {
                                    root.inputEdited(modelData.name,
                                        newValue);
                                }
                            }
                        }

                        HelperText {
                            Layout.fillWidth: true
                            Layout.topMargin: theme.space_2
                            visible: root.shownInputs.length === 0
                            horizontalAlignment: Text.AlignHCenter
                            text: qsTr("No inputs declared yet.")
                        }
                    }

                    Panel {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        Layout.alignment: Qt.AlignTop
                        title: qsTr("Outputs")

                        headerItems: [
                            HelperText {
                                text: root.signalCount(
                                    root.shownOutputs.length)
                                color: theme.text_muted
                            }
                        ]

                        TableHeader { Layout.fillWidth: true }

                        Repeater {
                            model: root.shownOutputs

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
                            Layout.topMargin: theme.space_2
                            visible: root.shownOutputs.length === 0
                            horizontalAlignment: Text.AlignHCenter
                            text: qsTr("No outputs declared yet.")
                        }
                    }
                }
            }
        }

        // Footer: run controls.
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 1
            color: theme.border
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.margins: theme.space_3
            Layout.leftMargin: theme.space_4
            Layout.rightMargin: theme.space_4
            spacing: theme.space_3

            HelperText {
                Layout.fillWidth: true
                text: root.shownInputs.length === 0
                    ? qsTr("Controls enable once inputs are declared.")
                    : qsTr("Sending writes every input to the module at "
                        + "once.")
            }

            AppButton {
                variant: "secondary"
                text: qsTr("Reset inputs")
                enabled: root.shownInputs.length > 0
                onClicked: root.resetInputsRequested()
            }

            AppButton {
                variant: "primary"
                text: qsTr("Send inputs to CTC")
                enabled: root.shownInputs.length > 0
                onClicked: root.sendInputsRequested()
            }
        }
    }
}
