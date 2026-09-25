// Overview page. Everything here is read-only except the passenger emergency
// brake and the failure injectors, which the Train Model owns.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "components"

ScrollView {
    id: root

    readonly property var s: trainModel.snapshot

    function fixed(value, digits) {
        return Number(value).toFixed(digits);
    }

    function mph(val) { return Number(val) * 2.23694; }
    function ft(val)  { return Number(val) * 3.28084; }

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

            Card {
                Layout.fillWidth: true
                title: qsTr("Speed & Authority")
                badgeLabel: root.s.current_block
                badgeVariant: "info"

                RowLayout {
                    Layout.fillWidth: true
                    spacing: theme.space_3

                    TelemetryReadout {
                        Layout.fillWidth: true
                        label: qsTr("Actual speed")
                        value: root.fixed(root.mph(root.s.actual_speed), 1)
                        unit: "mph"
                    }

                    TelemetryReadout {
                        Layout.fillWidth: true
                        label: qsTr("Commanded")
                        value: root.fixed(root.mph(root.s.commanded_speed), 1)
                        unit: "mph"
                    }

                    TelemetryReadout {
                        Layout.fillWidth: true
                        label: qsTr("Speed limit")
                        value: root.fixed(root.mph(root.s.speed_limit), 1)
                        unit: "mph"
                    }
                }

                KeyValueRow {
                    Layout.fillWidth: true
                    label: qsTr("Authority")
                    value: root.s.authority_block
                }

                KeyValueRow {
                    Layout.fillWidth: true
                    label: qsTr("Distance to end of authority")
                    value: root.fixed(root.ft(root.s.authority_distance), 1) + " ft"
                }

                KeyValueRow {
                    Layout.fillWidth: true
                    label: qsTr("Acceleration")
                    value: root.fixed(root.ft(root.s.acceleration), 2) + " ft/s\u00B2"
                }

                KeyValueRow {
                    Layout.fillWidth: true
                    label: qsTr("Grade")
                    value: root.fixed(root.s.grade, 1) + " deg"
                    rule: false
                }
            }

            Card {
                Layout.fillWidth: true
                title: qsTr("Cabin & Load")
                badgeLabel: root.s.cars + qsTr(" cars")
                badgeVariant: "idle"

                RowLayout {
                    Layout.fillWidth: true
                    spacing: theme.space_3

                    TelemetryReadout {
                        Layout.fillWidth: true
                        label: qsTr("Passengers")
                        value: root.s.passengers + " / " + root.s.capacity
                    }

                    TelemetryReadout {
                        Layout.fillWidth: true
                        label: qsTr("Loaded mass")
                        value: root.fixed(root.s.loaded_mass, 1)
                        unit: "t"
                    }

                    TelemetryReadout {
                        Layout.fillWidth: true
                        label: qsTr("Cabin temp")
                        value: String(root.s.cabin_temp)
                        unit: "F"
                    }
                }

                KeyValueRow {
                    Layout.fillWidth: true
                    label: qsTr("Crew")
                    value: String(root.s.crew)
                }

                KeyValueRow {
                    Layout.fillWidth: true
                    label: qsTr("Train size (l | w | h)")
                    value: root.fixed(root.ft(root.s.length), 1) + " | "
                        + root.fixed(root.ft(root.s.width), 1) + " | "
                        + root.fixed(root.ft(root.s.height), 1) + " ft"
                }

                KeyValueRow {
                    Layout.fillWidth: true
                    label: qsTr("Empty mass")
                    value: root.fixed(root.s.empty_mass, 1) + " t"
                }

                KeyValueRow {
                    Layout.fillWidth: true
                    label: qsTr("Power consumption")
                    value: root.fixed(root.s.power_consumption, 0) + " / "
                        + root.fixed(root.s.power_limit, 0) + " kW"
                    rule: false
                }

                UsageBar {
                    Layout.fillWidth: true
                    value: root.s.power_consumption
                    ceiling: root.s.power_limit
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: theme.space_2
                    spacing: theme.space_3

                    FieldLabel {
                        Layout.fillWidth: true
                        text: qsTr("LIGHTS")
                    }

                    StatusBadge {
                        label: root.s.cabin_light
                            ? qsTr("Cabin on") : qsTr("Cabin off")
                        variant: root.s.cabin_light ? "ok" : "idle"
                    }

                    StatusBadge {
                        label: root.s.headlight
                            ? qsTr("Headlight on") : qsTr("Headlight off")
                        variant: root.s.headlight ? "ok" : "idle"
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
                title: qsTr("Brakes & Doors")
                badgeLabel: root.s.emergency_brake
                    ? qsTr("E-brake applied") : qsTr("E-brake released")
                badgeVariant: root.s.emergency_brake ? "fault" : "ok"

                SafetyButton {
                    Layout.fillWidth: true
                    Layout.preferredHeight: theme.safety_emphasis_height
                    Layout.topMargin: theme.space_5
                    label: qsTr("Apply emergency brake")
                    applied: root.s.emergency_brake
                    tooltip: qsTr("Stops the train at the full braking rate and "
                        + "reports the stop to the track controller and the "
                        + "CTC. Confirmation is required.")
                    onConfirmed: {
                        if (root.s.emergency_brake)
                            trainModel.releaseEmergencyBrake()
                        else
                            trainModel.applyEmergencyBrake()
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: theme.space_4
                    spacing: theme.space_3

                    FieldLabel {
                        Layout.fillWidth: true
                        text: qsTr("LEFT DOORS")
                    }

                    StatusBadge {
                        label: root.s.left_door
                            ? qsTr("Open") : qsTr("Closed")
                        variant: root.s.left_door ? "ok" : "idle"
                    }

                    Item { Layout.fillWidth: true }

                    FieldLabel {
                        Layout.fillWidth: true
                        text: qsTr("RIGHT DOORS")
                    }

                    StatusBadge {
                        label: root.s.right_door
                            ? qsTr("Open") : qsTr("Closed")
                        variant: root.s.right_door ? "ok" : "idle"
                    }
                }

            }

            Card {
                Layout.fillWidth: true
                title: qsTr("Position")
                badgeLabel: root.s.line
                badgeVariant: "idle"

                KeyValueRow {
                    Layout.fillWidth: true
                    label: qsTr("Direction of travel")
                    value: root.s.direction + " · " + root.s.previous_block
                        + " → " + root.s.current_block
                }

                KeyValueRow {
                    Layout.fillWidth: true
                    label: qsTr("Current block")
                    value: root.s.current_block
                }

                KeyValueRow {
                    Layout.fillWidth: true
                    label: qsTr("Offset into block")
                    value: root.fixed(root.ft(root.s.position_offset), 1) + " ft"
                }

                KeyValueRow {
                    Layout.fillWidth: true
                    label: qsTr("Next station · arrival")
                    value: root.s.next_station + " ("
                        + root.s.platform_side + ") · " + root.s.arrival
                    rule: false
                }
            }

            Card {
                Layout.fillWidth: true
                title: qsTr("Failure Modes")
                badgeLabel: trainModel.activeFailureCount + qsTr(" failed")
                badgeVariant: trainModel.activeFailureCount > 0
                    ? "fault" : "ok"

                Repeater {
                    model: trainModel.failures

                    delegate: AppButton {
                        required property var modelData

                        Layout.fillWidth: true
                        variant: modelData.active ? "danger" : "success"
                        text: (modelData.active ? qsTr("Clear ") : qsTr("Induce "))
                            + modelData.label + qsTr(" failure")
                        tooltip: qsTr("A failure stays set until it is cleared here. "
                            + "With signal pickup failed, no new commanded speed "
                            + "or authority reaches this train.")
                        onClicked: trainModel.setFailure(
                            modelData.name, !modelData.active)
                    }
                }
            }
        }
    }
}
