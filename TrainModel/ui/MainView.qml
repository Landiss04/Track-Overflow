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
                heading: qsTr("Automatic \u2014 track controller in command")
                body: qsTr("Commanded speed and authority arrive from the "
                    + "track controller. Lights, doors and the service brake "
                    + "are commanded by the train controller and are shown "
                    + "here as state only.")
            }

            Card {
                Layout.fillWidth: true
                title: qsTr("Speed & authority")
                badgeLabel: root.s.current_block
                badgeVariant: "info"

                RowLayout {
                    Layout.fillWidth: true
                    spacing: theme.space_3

                    TelemetryReadout {
                        Layout.fillWidth: true
                        label: qsTr("Actual speed")
                        value: root.fixed(root.s.actual_speed, 1)
                        unit: "m/s"
                    }

                    TelemetryReadout {
                        Layout.fillWidth: true
                        label: qsTr("Commanded")
                        value: root.fixed(root.s.commanded_speed, 1)
                        unit: "m/s"
                    }

                    TelemetryReadout {
                        Layout.fillWidth: true
                        label: qsTr("Speed limit")
                        value: root.fixed(root.s.speed_limit, 1)
                        unit: "m/s"
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
                    value: root.fixed(root.s.authority_distance, 1) + " m"
                }

                KeyValueRow {
                    Layout.fillWidth: true
                    label: qsTr("Acceleration")
                    value: root.fixed(root.s.acceleration, 2) + " m/s\u00B2"
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
                title: qsTr("Cabin & load")
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
                    value: root.fixed(root.s.length, 2) + " | "
                        + root.fixed(root.s.width, 2) + " | "
                        + root.fixed(root.s.height, 2) + " m"
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

            Card {
                Layout.fillWidth: true
                title: qsTr("Position")
                badgeLabel: root.s.line
                badgeVariant: "idle"

                KeyValueRow {
                    Layout.fillWidth: true
                    label: qsTr("Direction of travel")
                    value: root.s.direction + " \u00B7 " + root.s.previous_block
                        + " \u2192 " + root.s.current_block
                }

                KeyValueRow {
                    Layout.fillWidth: true
                    label: qsTr("Current block")
                    value: root.s.current_block
                }

                KeyValueRow {
                    Layout.fillWidth: true
                    label: qsTr("Offset into block")
                    value: root.fixed(root.s.position_offset, 1) + " m"
                }

                KeyValueRow {
                    Layout.fillWidth: true
                    label: qsTr("Next station \u00B7 arrival")
                    value: root.s.next_station + " ("
                        + root.s.platform_side + ") \u00B7 " + root.s.arrival
                    rule: false
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
                title: qsTr("Brakes & doors")
                badgeLabel: root.s.emergency_brake
                    ? qsTr("E-brake applied") : qsTr("E-brake released")
                badgeVariant: root.s.emergency_brake ? "fault" : "ok"

                KeyValueRow {
                    Layout.fillWidth: true
                    label: qsTr("Passenger emergency brake")
                    value: root.s.emergency_brake
                        ? qsTr("Applied") : qsTr("Released")
                }

                SafetyButton {
                    Layout.fillWidth: true
                    Layout.topMargin: theme.space_5
                    Layout.bottomMargin: theme.space_2
                    label: qsTr("Apply emergency brake")
                    onConfirmed: trainModel.applyEmergencyBrake()
                }

                HelperText {
                    Layout.fillWidth: true
                    text: qsTr("Stops the train at the full braking rate and "
                        + "reports the stop to the track controller and the "
                        + "CTC. Confirmation is required.")
                }

                AppButton {
                    Layout.topMargin: theme.space_2
                    variant: "secondary"
                    size: "small"
                    text: qsTr("Release brake")
                    enabled: root.s.emergency_brake
                    onClicked: trainModel.releaseEmergencyBrake()
                }

                FieldLabel {
                    Layout.fillWidth: true
                    Layout.topMargin: theme.space_4
                    text: qsTr("DOORS")
                }

                Repeater {
                    model: trainModel.doors

                    delegate: KeyValueRow {
                        required property var modelData

                        Layout.fillWidth: true
                        label: modelData.side
                        value: modelData.open ? qsTr("Open") : qsTr("Closed")
                    }
                }

                HelperText {
                    Layout.fillWidth: true
                    text: qsTr("Door commands come from the train controller. "
                        + "Doors unlock at 0 m/s with the service brake "
                        + "applied.")
                }
            }

            Card {
                Layout.fillWidth: true
                title: qsTr("Failure modes")
                badgeLabel: trainModel.activeFailureCount + qsTr(" failed")
                badgeVariant: trainModel.activeFailureCount > 0
                    ? "fault" : "ok"

                Repeater {
                    model: trainModel.failures

                    delegate: RowLayout {
                        required property var modelData

                        Layout.fillWidth: true
                        spacing: theme.space_3

                        FieldLabel {
                            Layout.fillWidth: true
                            text: modelData.label.toUpperCase()
                        }

                        StatusBadge {
                            label: modelData.active
                                ? qsTr("Failed") : qsTr("Normal")
                            variant: modelData.active ? "fault" : "ok"
                        }

                        AppButton {
                            variant: modelData.active ? "success" : "secondary"
                            size: "small"
                            text: modelData.active
                                ? qsTr("Clear") : qsTr("Induce")
                            onClicked: trainModel.setFailure(
                                modelData.name, !modelData.active)
                        }
                    }
                }

                HelperText {
                    Layout.fillWidth: true
                    text: qsTr("A failure stays set until it is cleared here. "
                        + "With signal pickup failed, no new commanded speed "
                        + "or authority reaches this train.")
                }
            }
        }
    }
}
