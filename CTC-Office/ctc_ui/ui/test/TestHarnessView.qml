// Test harness view. Forces every CTC input and reads back every output
// so the module can be exercised on its own, following the Train Model
// test harness template. It fills the separate test UI process's window
// (test/TestMain.qml); the CTC Office window does not open it.
//
// Rows come from ctc_ui/test_harness.py, bound in TestMain.qml. A scalar
// row is { name, kind, value, unit, hint } where kind is
// "bool" | "int" | "float" | "string", matching SignalRow. A list row has
// kind "list", { fields, entries, noun } and is edited in a ListEditor
// table. hint says what the row is.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"
import "../../../../ui"

Rectangle {
    id: root

    // Rows from the neighboring modules (Track Controller, Track Model).
    property var inputs: []
    // Rows standing in for the CTC UI's own dispatcher actions.
    property var dispatcherInputs: []
    property var outputs: []
    // True once this process is linked to a CTC Office.
    property bool connected: false
    // Result of the last Send or Reset; shown in the footer.
    property string status: ""
    property bool statusIsError: false
    // The running CTC Office's simulation clock, over the clock link.
    property bool clockConnected: false
    property string clockTime: "--:--:--"
    property bool clockPaused: true
    property int clockSpeed: 1

    // Value column width of scalar rows.
    readonly property int valueWidth: 300
    // For list rows' layout dropdowns: harness.lineNames and
    // harness.layoutOptions.
    property var lineNames: []
    property var layoutOptions: ({})

    signal inputEdited(string name, var value)
    // A row with `choices` (ticket sales: Green or Red) picked one.
    signal inputChoiceEdited(string name, string choice)
    // List rows: add, remove, or change one field of one entry.
    signal entryAddRequested(string name)
    signal entryRemoveRequested(string name, int index)
    signal entryFieldEdited(string name, int index, string key, var value)
    signal sendInputsRequested()
    signal resetInputsRequested()
    signal clockPauseRequested()
    signal clockResumeRequested()
    signal clockSpeedRequested(int speed)

    color: theme.bg_surface
    clip: true

    function signalCount(count) {
        return count === 1 ? qsTr("1 signal") : qsTr("%1 signals").arg(count);
    }

    component EditableRows: ColumnLayout {
        id: rowsRoot

        property var rows: []

        Layout.fillWidth: true
        spacing: theme.space_2

        TableHeader {
            Layout.fillWidth: true
            valueWidth: root.valueWidth
        }

        Repeater {
            model: rowsRoot.rows

            delegate: ColumnLayout {
                id: row

                required property var modelData

                Layout.fillWidth: true
                spacing: 0

                // A list row's name; its table follows the hint below.
                RowLayout {
                    Layout.fillWidth: true
                    visible: row.modelData.kind === "list"
                    spacing: theme.space_3

                    MonoText {
                        Layout.fillWidth: true
                        text: row.modelData.name
                    }

                    MonoText {
                        text: row.modelData.unit
                        color: theme.text_muted
                    }
                }

                RowLayout {
                    id: rowLine

                    visible: row.modelData.kind !== "list"
                    readonly property bool hasChoices:
                        (row.modelData.choices || []).length > 0
                    readonly property int choiceWidth: 110

                    Layout.fillWidth: true
                    spacing: theme.space_3

                    SignalRow {
                        Layout.fillWidth: true
                        name: row.modelData.name
                        kind: row.modelData.kind
                        value: row.modelData.value
                        unit: row.modelData.unit
                        // A row with a dropdown gives up that much of its
                        // value column, so its name and type stay aligned
                        // with the other rows.
                        valueWidth: rowLine.hasChoices
                            ? root.valueWidth - rowLine.choiceWidth
                                - rowLine.spacing
                            : root.valueWidth
                        editable: true
                        onEdited: function (newValue) {
                            root.inputEdited(row.modelData.name, newValue);
                        }
                    }

                    // Only rows with `choices`: which line the value is
                    // for.
                    SelectField {
                        readonly property var choices:
                            row.modelData.choices || []
                        // Pinned: the select's own minimum is wider.
                        Layout.preferredWidth: rowLine.choiceWidth
                        Layout.minimumWidth: rowLine.choiceWidth
                        Layout.maximumWidth: rowLine.choiceWidth
                        visible: rowLine.hasChoices
                        label: qsTr("Line")
                        model: choices
                        currentIndex: choices.indexOf(row.modelData.choice)
                        onCommitted: function (value) {
                            root.inputChoiceEdited(row.modelData.name, value);
                        }
                    }
                }

                HelperText {
                    Layout.fillWidth: true
                    visible: (row.modelData.hint || "") !== ""
                    text: row.modelData.hint || ""
                    color: theme.text_muted
                }

                ListEditor {
                    Layout.fillWidth: true
                    Layout.topMargin: theme.space_2
                    Layout.bottomMargin: theme.space_2
                    visible: row.modelData.kind === "list"
                    fields: row.modelData.fields || []
                    entries: row.modelData.entries || []
                    noun: row.modelData.noun || qsTr("entry")
                    lineNames: root.lineNames
                    layoutOptions: root.layoutOptions
                    onAddRequested: root.entryAddRequested(
                        row.modelData.name)
                    onRemoveRequested: function (index) {
                        root.entryRemoveRequested(row.modelData.name, index);
                    }
                    onFieldEdited: function (index, key, value) {
                        root.entryFieldEdited(row.modelData.name, index, key,
                                              value);
                    }
                }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Title bar, with the CTC Office's simulation clock on the right.
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.max(
                theme.control_h_lg + theme.space_2,
                clockControls.implicitHeight + 2 * theme.space_2)
            Layout.leftMargin: theme.space_4
            Layout.rightMargin: theme.space_4
            spacing: theme.space_3

            Text {
                text: qsTr("CTC Office — Test harness")
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

            Item { Layout.fillWidth: true }

            HelperText {
                visible: !root.clockConnected
                text: qsTr("CTC Office not running. Start it with "
                    + "python -m ctc_ui to control its clock.")
                color: theme.text_muted
            }

            ClockControls {
                id: clockControls

                time: root.clockTime
                paused: root.clockPaused
                speed: root.clockSpeed
                controlsEnabled: root.clockConnected
                onPauseRequested: root.clockPauseRequested()
                onResumeRequested: root.clockResumeRequested()
                onSpeedRequested: function (speed) {
                    root.clockSpeedRequested(speed);
                }
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

                Callout {
                    Layout.fillWidth: true
                    Layout.topMargin: theme.space_4
                    Layout.leftMargin: theme.space_4
                    Layout.rightMargin: theme.space_4
                    heading: qsTr("Force inputs, read outputs")
                    body: qsTr("Inputs stand in for the Track Controller and "
                        + "the Track Model; dispatcher actions stand in for "
                        + "the CTC UI. Send applies them; the CTC window's "
                        + "clock steps the CTC with the inputs while it "
                        + "runs. Dispatcher rows follow the CTC window until "
                        + "you edit them. Outputs come from the module.")
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: theme.space_4
                    Layout.rightMargin: theme.space_4
                    Layout.bottomMargin: theme.space_4
                    spacing: theme.space_4

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        Layout.alignment: Qt.AlignTop
                        spacing: theme.space_4

                        Panel {
                            Layout.fillWidth: true
                            title: qsTr("Inputs")
                            headerItems: [
                                HelperText {
                                    text: root.signalCount(root.inputs.length)
                                    color: theme.text_muted
                                }
                            ]

                            EditableRows { rows: root.inputs }
                        }

                        Panel {
                            Layout.fillWidth: true
                            title: qsTr("Dispatcher actions")
                            headerItems: [
                                HelperText {
                                    text: qsTr("Stand-in for the CTC UI")
                                    color: theme.text_muted
                                }
                            ]

                            EditableRows { rows: root.dispatcherInputs }
                        }
                    }

                    Panel {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        Layout.alignment: Qt.AlignTop
                        title: qsTr("Outputs")

                        headerItems: [
                            HelperText {
                                text: root.signalCount(root.outputs.length)
                                color: theme.text_muted
                            }
                        ]

                        TableHeader { Layout.fillWidth: true }

                        Repeater {
                            model: root.outputs

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
                            text: qsTr("To the Track Controller and the "
                                + "central harness, updated live.")
                            color: theme.text_muted
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
                text: root.status !== "" ? root.status
                    : qsTr("Edit inputs, then Send to apply them.")
                color: root.statusIsError ? theme.danger
                    : theme.text_secondary
            }

            AppButton {
                variant: "secondary"
                text: qsTr("Reset inputs")
                enabled: root.connected
                onClicked: root.resetInputsRequested()
            }

            AppButton {
                variant: "primary"
                text: qsTr("Send inputs to CTC")
                enabled: root.connected
                onClicked: root.sendInputsRequested()
            }
        }
    }
}
