// Track Model test page. Stands in for the Track Controller, the Train
// Model and the clock, and drives the Track Model only through its
// interface. Every output the Track Model sends to the Track Controller,
// the Train Model and the Train Controller is read back here.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../ui"

Item {
    id: root

    // One editable SignalRow per row; edits go to harness.setInput(group).
    component InputRows: Repeater {
        id: rows
        property string group: ""
        delegate: SignalRow {
            required property var modelData
            Layout.fillWidth: true
            name: modelData.name
            kind: modelData.kind
            value: modelData.value
            unit: modelData.unit
            options: modelData.options
            editable: true
            // The label is shortened; edits go back by the full id.
            onEdited: function (newValue) {
                harness.setInput(rows.group, modelData.id, newValue);
            }
        }
    }

    // Read-only SignalRows.
    component OutputRows: Repeater {
        delegate: SignalRow {
            required property var modelData
            Layout.fillWidth: true
            name: modelData.name
            kind: modelData.kind
            value: modelData.value
            unit: modelData.unit
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        ModuleHeader {
            Layout.fillWidth: true
            moduleName: qsTr("Track Model — Test UI")
            mode: harness.connected
                ? (harness.running ? qsTr("RUNNING") : qsTr("HELD"))
                : qsTr("NOT CONNECTED")
            clock: harness.elapsed
        }

        ScrollView {
            id: scroller
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth

            // Side margins live on the row, not the columns: a column's
            // margins count toward its share of the width, so uneven
            // margins would give the columns unequal widths.
            RowLayout {
                x: theme.space_5
                width: scroller.availableWidth - 2 * theme.space_5
                spacing: theme.space_5

                // ---- inputs from the Track Controller ------------------
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.alignment: Qt.AlignTop
                    Layout.topMargin: theme.space_5
                    Layout.bottomMargin: theme.space_5
                    spacing: theme.space_5

                    Callout {
                        Layout.fillWidth: true
                        visible: !harness.connected
                        variant: "warning"
                        heading: qsTr("Waiting for the Track Model")
                        body: qsTr("Start TrackModel/main.py. This page "
                            + "connects on its own and learns every "
                            + "block, switch, signal and crossing from "
                            + "the Track Model's outputs.")
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("Block filter")

                        FormField {
                            Layout.fillWidth: true
                            label: qsTr("Line")

                            SegmentedToggle {
                                Layout.fillWidth: true
                                options: harness.lines
                                currentIndex: harness.lines.indexOf(
                                    harness.line)
                                onActivated: function (index) {
                                    harness.setLine(harness.lines[index]);
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: theme.space_3

                            SelectField {
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                label: qsTr("Section")
                                model: harness.sections
                                currentIndex: harness.sections.indexOf(
                                    harness.section)
                                onCommitted: function (value) {
                                    harness.setSection(value);
                                }
                            }
                            ValueField {
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                label: qsTr("Blocks, e.g. 5-20")
                                kind: "string"
                                modelValue: harness.rangeText
                                onCommitted: function (value) {
                                    harness.setRange(String(value));
                                }
                            }
                            AppButton {
                                Layout.alignment: Qt.AlignBottom
                                variant: "secondary"
                                text: qsTr("Clear")
                                onClicked: harness.clearFilter()
                            }
                        }

                        HelperText {
                            Layout.fillWidth: true
                            text: harness.filterSummary + qsTr(
                                ". The block pickers, and the switch, "
                                + "signal and gate lists, show this "
                                + "line.")
                        }
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("From Track Controller — block")

                        SelectField {
                            Layout.fillWidth: true
                            label: qsTr("Block")
                            model: harness.filteredBlocks
                            currentIndex: harness.filteredBlocks.indexOf(
                                harness.selectedBlock)
                            onCommitted: function (value) {
                                harness.selectBlock(value);
                            }
                        }
                        TableHeader { Layout.fillWidth: true }
                        InputRows { model: harness.blockRows; group: "block" }
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("From Track Controller — switches")
                        TableHeader { Layout.fillWidth: true }
                        InputRows {
                            model: harness.switchRows
                            group: "switch"
                        }
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("From Track Controller — signals")
                        TableHeader { Layout.fillWidth: true }
                        InputRows {
                            model: harness.signalRows
                            group: "signal"
                        }
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("From Track Controller — gates, heaters")
                        TableHeader { Layout.fillWidth: true }
                        InputRows {
                            model: harness.crossingRows
                            group: "crossing"
                        }
                        InputRows {
                            model: harness.heaterRows
                            group: "heater"
                        }
                    }
                }

                // ---- inputs from the Train Model, environment, test ----
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.alignment: Qt.AlignTop
                    Layout.topMargin: theme.space_5
                    Layout.bottomMargin: theme.space_5
                    spacing: theme.space_5

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("From Train Model — trains")

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: theme.space_3

                            ValueField {
                                id: newTrainId
                                Layout.preferredWidth: 110
                                label: qsTr("New train ID")
                                kind: "string"
                                text: "T1"
                            }
                            SelectField {
                                id: newTrainBlock
                                Layout.fillWidth: true
                                label: qsTr("Start block")
                                model: harness.filteredBlocks
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: theme.space_3

                            AppButton {
                                Layout.fillWidth: true
                                variant: "primary"
                                text: qsTr("Add train")
                                enabled: harness.filteredBlocks.length > 0
                                onClicked: harness.addTrain(
                                    newTrainId.text,
                                    harness.filteredBlocks[Math.max(
                                        0, newTrainBlock.currentIndex)])
                            }
                            AppButton {
                                Layout.fillWidth: true
                                variant: "secondary"
                                text: qsTr("Remove selected")
                                enabled: harness.selectedTrain !== ""
                                onClicked: harness.removeTrain()
                            }
                        }

                        SelectField {
                            Layout.fillWidth: true
                            visible: harness.trains.length > 0
                            label: qsTr("Selected train")
                            model: harness.trains
                            currentIndex: harness.trains.indexOf(
                                harness.selectedTrain)
                            onCommitted: function (value) {
                                harness.selectTrain(value);
                            }
                        }

                        TableHeader {
                            Layout.fillWidth: true
                            visible: harness.trains.length > 0
                        }
                        InputRows { model: harness.trainRows; group: "train" }

                        RowLayout {
                            Layout.fillWidth: true

                            CheckBox {
                                checked: harness.actAsTrainModel
                                onToggled: harness.setActAsTrainModel(checked)
                            }
                            HelperText {
                                Layout.fillWidth: true
                                text: qsTr("Act as the Train Model: add "
                                    + "speed × dt to each offset every "
                                    + "tick, and move to the block the "
                                    + "feed names with offset 0.")
                            }
                        }
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("Environment")
                        TableHeader { Layout.fillWidth: true }
                        InputRows {
                            model: harness.environmentRows
                            group: "env"
                        }
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("Test only — never used at "
                            + "integration")

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: theme.space_3

                            SelectField {
                                id: failureMode
                                Layout.fillWidth: true
                                label: qsTr("Failure on selected block")
                                model: harness.failureOptions
                            }
                            AppButton {
                                Layout.alignment: Qt.AlignBottom
                                variant: "danger"
                                text: qsTr("Set failure")
                                onClicked: harness.setBlockFailure(
                                    harness.selectedBlock,
                                    harness.failureOptions[
                                        failureMode.currentIndex])
                            }
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            columnSpacing: theme.space_3

                            ValueField {
                                id: editLength
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                label: qsTr("Length (m)")
                                kind: "float"
                            }
                            ValueField {
                                id: editGrade
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                label: qsTr("Grade (deg)")
                                kind: "float"
                            }
                            ValueField {
                                id: editLimit
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                label: qsTr("Speed limit (m/s)")
                                kind: "float"
                            }
                            ValueField {
                                id: editElevation
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                label: qsTr("Elevation (m)")
                                kind: "float"
                            }
                        }

                        AppButton {
                            Layout.fillWidth: true
                            variant: "secondary"
                            text: qsTr("Edit selected block (blank = "
                                + "unchanged)")
                            onClicked: harness.editBlock(
                                harness.selectedBlock, editLength.text,
                                editGrade.text, editLimit.text,
                                editElevation.text)
                        }

                        AppButton {
                            Layout.fillWidth: true
                            variant: "secondary"
                            text: qsTr("Reset module")
                            onClicked: harness.resetModule()
                        }
                    }
                }

                // ---- run control and outputs ---------------------------
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.alignment: Qt.AlignTop
                    Layout.topMargin: theme.space_5
                    Layout.bottomMargin: theme.space_5
                    spacing: theme.space_5

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("Run control")

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
                                label: qsTr("Rate")
                                SegmentedToggle {
                                    Layout.fillWidth: true
                                    options: [qsTr("1×"), qsTr("10×")]
                                    currentIndex: harness.fast ? 1 : 0
                                    onActivated: function (index) {
                                        harness.setFast(index === 1);
                                    }
                                }
                            }
                        }

                        AppButton {
                            Layout.fillWidth: true
                            variant: "primary"
                            text: qsTr("Step one tick")
                            enabled: harness.connected
                            onClicked: harness.stepOnce()
                        }

                        KeyValueRow {
                            Layout.fillWidth: true
                            label: qsTr("Tick")
                            value: String(harness.tick)
                        }
                        KeyValueRow {
                            Layout.fillWidth: true
                            label: qsTr("dt (fixed)")
                            value: Number(harness.dt).toFixed(3) + " s"
                            rule: false
                        }
                    }

                    Callout {
                        Layout.fillWidth: true
                        visible: harness.lastError !== ""
                        variant: "warning"
                        heading: qsTr("Rejected by the Track Model")
                        body: harness.lastError
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("Outputs — to Track Controller")
                        TableHeader { Layout.fillWidth: true }
                        OutputRows { model: harness.controllerSummaryRows }
                        OutputRows { model: harness.deviceStateRows }
                        HelperText {
                            Layout.fillWidth: true
                            text: qsTr("%1 line. sw = switch, sig = signal "
                                + "light, gate = crossing gate (true = "
                                + "closed).").arg(harness.line)
                        }
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: harness.selectedTrain === ""
                            ? qsTr("Outputs — to Train Model")
                            : qsTr("Outputs — to Train Model, %1").arg(
                                harness.selectedTrain)
                        TableHeader { Layout.fillWidth: true }
                        OutputRows { model: harness.feedRows }
                        HelperText {
                            Layout.fillWidth: true
                            visible: harness.feedRows.length > 0
                            text: qsTr("block to station: Track Info. "
                                + "cmd speed, authority: Track Signal.")
                        }
                    }

                    Panel {
                        Layout.fillWidth: true
                        title: qsTr("Outputs — to Train Controller")
                        TableHeader { Layout.fillWidth: true }
                        OutputRows { model: harness.trainControllerRows }
                        HelperText {
                            Layout.fillWidth: true
                            text: qsTr("A train sees a light once, on the "
                                + "tick it enters that block.")
                        }
                    }
                }
            }
        }
    }
}
