// Test harness view. Forces every CTC input and reads back every output
// so the module can be exercised on its own, following the Train Model
// test harness template. It fills the separate test UI process's window
// (test/TestMain.qml); the CTC Office window does not open it.
//
// Rows come from ctc_ui/test_harness.py, bound in TestMain.qml. Each row
// is { name, kind, value, unit, hint } where kind is
// "bool" | "int" | "float" | "string", matching SignalRow, and hint
// describes how a text row is written.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
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

    // Value column width; wide enough for list-valued text rows.
    readonly property int valueWidth: 300

    signal inputEdited(string name, var value)
    signal sendInputsRequested()
    signal resetInputsRequested()

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

                SignalRow {
                    Layout.fillWidth: true
                    name: row.modelData.name
                    kind: row.modelData.kind
                    value: row.modelData.value
                    unit: row.modelData.unit
                    valueWidth: root.valueWidth
                    editable: true
                    onEdited: function (newValue) {
                        root.inputEdited(row.modelData.name, newValue);
                    }
                }

                HelperText {
                    Layout.fillWidth: true
                    visible: (row.modelData.hint || "") !== ""
                    text: row.modelData.hint || ""
                    color: theme.text_muted
                }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Title bar.
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: theme.control_h_lg + theme.space_2
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
                        + "the CTC UI. Send applies them and advances the "
                        + "CTC one tick. Outputs are read back from the "
                        + "module.")
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
                            text: qsTr("To the Track Controller, read back "
                                + "after each Send.")
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
                    : qsTr("Edit inputs, then Send to apply them and "
                        + "advance one tick.")
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
