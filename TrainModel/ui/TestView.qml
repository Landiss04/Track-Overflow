import QtQuick
import QtQuick.Layouts
import "."
import "./components"

// Page 3b — Test UI: the standalone harness. Inputs are edited here and
// routed through harness.set_input(); outputs, failure modes, and run
// control bind to harness state. Copy is verbatim from the mockup.
ColumnLayout {
    id: root

    TopBar {
        Layout.fillWidth: true
        hamburger: true
        title: "TRAIN MODEL"
        subtitle: "Page 3b · Test UI"
        trainSelector: trainModel.train_selector
        clock: trainModel.clock
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.leftMargin: theme.space_3
        Layout.rightMargin: theme.space_3
        spacing: theme.space_3

        // ---- Left column: inputs --------------------------------------
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: theme.space_4

            Banner {
                Layout.fillWidth: true
                heading: "TEST HARNESS — MODULE DRIVEN FROM THIS PAGE"
                tooltip: "Every input below is supplied by this page instead " +
                        "of by the track model and train controller, so the " +
                        "train model can be run and graded on its own."
            }

            Card {
                Layout.fillWidth: true
                title: "INPUTS · SET HERE"
                badgeText: "15"
                badgeVariant: "idle"

                TableHeader {
                    Layout.fillWidth: true
                    columns: ["Signal", "Type", "Value"]
                    fractions: [0.4, 0.2, 0.4]
                }

                Repeater {
                    model: harness.input_descriptors

                    delegate: Item {
                        Layout.fillWidth: true
                        implicitHeight: theme.input_row_height

                        readonly property string name: modelData.name
                        readonly property string type: modelData.type
                        readonly property string unit: modelData.unit

                        // Signal name — mono, IDs and names in the mono face.
                        Text {
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                            text: name
                            elide: Text.ElideRight
                            font.family: theme.mono_family
                            font.pixelSize: theme.font_small
                            color: theme.text_primary
                        }

                        // Type column.
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            x: (0.4 * parent.width) + theme.space_3
                            text: type
                            font.family: theme.mono_family
                            font.pixelSize: theme.font_small
                            color: theme.text_muted
                        }

                        // Value control — bools toggle, numbers validate,
                        // strings take the wide field (Style Guide §6.2).
                        SegmentedToggle {
                            visible: type === "bool"
                            x: (0.6 * parent.width)
                            anchors.verticalCenter: parent.verticalCenter
                            selected: harness[name] ? "TRUE" : "FALSE"
                            onChanged: function(option) {
                                harness.set_input(name, option === "TRUE")
                            }
                        }

                        RowLayout {
                            visible: type !== "bool"
                            x: (0.6 * parent.width)
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: theme.space_2

                            NumericField {
                                visible: type === "float" || type === "int"
                                Layout.preferredWidth: theme.field_narrow_width
                                allowDecimals: type === "float"
                                sourceText: harness.input_text(name)
                                onCommit: function(value) {
                                    harness.set_input(name, value)
                                }
                            }

                            TextField {
                                visible: type === "string"
                                Layout.preferredWidth: theme.field_wide_width
                                sourceText: harness[name]
                                onCommit: function(value) {
                                    harness.set_input(name, value)
                                }
                            }

                            Text {
                                visible: unit.length > 0
                                text: unit
                                font.family: theme.mono_family
                                font.pixelSize: theme.font_small
                                color: theme.text_muted
                            }
                        }

                        // Bottom rule (Style Guide §6.6).
                        Rectangle {
                            visible: index < harness.input_descriptors.length - 1
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 1
                            color: theme.border
                        }
                    }
                }
            }
        }

        // ---- Right column: outputs, failures, run control -------------
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: theme.space_4

            Card {
                Layout.fillWidth: true
                title: "OUTPUTS · READ FROM MODULE"
                badgeText: "11"
                badgeVariant: "idle"
                tooltip: "Values refresh on every tick. Distance travelled " +
                        "is per tick, not cumulative."

                TableHeader {
                    Layout.fillWidth: true
                    columns: ["Signal", "Type", "Value"]
                    fractions: [0.4, 0.2, 0.4]
                }

                Repeater {
                    model: harness.outputs

                    delegate: Item {
                        Layout.fillWidth: true
                        implicitHeight: theme.table_row_height

                        Text {
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.signal
                            elide: Text.ElideRight
                            font.family: theme.mono_family
                            font.pixelSize: theme.font_small
                            color: theme.text_primary
                        }

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            x: (0.4 * parent.width) + theme.space_3
                            text: modelData.type
                            font.family: theme.mono_family
                            font.pixelSize: theme.font_small
                            color: theme.text_muted
                        }

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            x: (0.6 * parent.width)
                            text: modelData.value
                            elide: Text.ElideRight
                            font.family: theme.mono_family
                            font.pixelSize: theme.font_small
                            color: theme.text_primary
                        }

                        Rectangle {
                            visible: index < harness.outputs.length - 1
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 1
                            color: theme.border
                        }
                    }
                }

            }

            Card {
                Layout.fillWidth: true
                title: "FAILURE MODES · SET HERE"
                badgeText: "3"
                badgeVariant: "idle"
                tooltip: "Set here because these are module state, not " +
                        "inputs from another module."

                TableHeader {
                    Layout.fillWidth: true
                    columns: ["Internal state", "Type", "Value"]
                    fractions: [0.4, 0.2, 0.4]
                }

                Repeater {
                    model: [
                        {name: "engine_failure"},
                        {name: "brake_failure"},
                        {name: "signal_pickup_failure"}
                    ]

                    delegate: Item {
                        Layout.fillWidth: true
                        implicitHeight: theme.input_row_height

                        readonly property string name: modelData.name

                        Text {
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                            text: name
                            elide: Text.ElideRight
                            font.family: theme.mono_family
                            font.pixelSize: theme.font_small
                            color: theme.text_primary
                        }

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            x: (0.4 * parent.width) + theme.space_3
                            text: "bool"
                            font.family: theme.mono_family
                            font.pixelSize: theme.font_small
                            color: theme.text_muted
                        }

                        // Failure modes are module state, not inputs — set
                        // the property directly rather than via set_input.
                        SegmentedToggle {
                            anchors.verticalCenter: parent.verticalCenter
                            x: (0.6 * parent.width)
                            selected: harness[name] ? "TRUE" : "FALSE"
                            onChanged: function(option) {
                                harness[name] = (option === "TRUE")
                            }
                        }

                        Rectangle {
                            visible: index < 2
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 1
                            color: theme.border
                        }
                    }
                }

            }

            Card {
                Layout.fillWidth: true
                title: "RUN CONTROL"
                badgeText: harness.run_state
                badgeVariant: "idle"

                SectionLabel {
                    Layout.fillWidth: true
                    label: "Clock"
                }

                SegmentedToggle {
                    Layout.fillWidth: true
                    options: ["RUN", "HOLD"]
                    selected: harness.run_state
                    onChanged: function(option) {
                        harness.set_run_state(option)
                    }
                }

                PrimaryButton {
                    Layout.fillWidth: true
                    text: "SEND INPUTS TO TRAIN MODEL"
                    onClicked: harness.send_inputs()
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: theme.space_3

                    SecondaryButton {
                        Layout.fillWidth: true
                        text: "ADVANCE ONE TICK"
                        onClicked: harness.advance_tick()
                    }
                    SecondaryButton {
                        Layout.fillWidth: true
                        text: "RESET MODULE"
                        onClicked: harness.reset_module()
                    }
                }

                KeyValueRow {
                    Layout.fillWidth: true
                    label: "Tick"
                    value: String(harness.tick).replace(/(\d)(?=(\d{3})+$)/g, "$1 ")
                }
                KeyValueRow {
                    Layout.fillWidth: true
                    label: "dt"
                    value: harness.dt
                }
                KeyValueRow {
                    Layout.fillWidth: true
                    lastRow: true
                    label: "Elapsed"
                    value: harness.elapsed
                }
            }
        }
    }
}
