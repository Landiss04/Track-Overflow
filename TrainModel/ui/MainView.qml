// Overview page. Everything here is read-only except the passenger emergency
// brake and the failure injectors, which the Train Model owns.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../ui"

ScrollView {
    id: root

    readonly property var s: trainModel.snapshot

    function fixed(value, digits) {
        const text = Number(value).toFixed(digits);
        // A small negative value rounds to "-0.00"; zero carries no sign.
        return Number(text) === 0 ? (0).toFixed(digits) : text;
    }

    function mph(val) { return Number(val) * 2.236936; }
    function ft(val)  { return Number(val) * 3.28084; }
    function tons(val) { return Number(val) * 0.001102311; }
    function kw(val)  { return Number(val) * 0.001; }
    function degF(val) { return Number(val) * 9 / 5 + 32; }

    clip: true
    contentWidth: availableWidth

    RowLayout {
        width: root.availableWidth
        spacing: theme.space_5

        ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.alignment: Qt.AlignTop
            Layout.margins: theme.space_5
            Layout.rightMargin: 0
            spacing: theme.space_5

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.space_3

                Text {
                    Layout.fillWidth: true
                    text: qsTr("Lights")
                    color: theme.text_primary
                    font.family: theme.ui_family
                    font.pixelSize: theme.size_h3
                    font.weight: theme.weight_bold
                }

                StatusBadge {
                    label: root.s.interior_light
                        ? qsTr("Interior on") : qsTr("Interior off")
                    variant: root.s.interior_light ? "ok" : "idle"
                }

                StatusBadge {
                    label: root.s.exterior_light
                        ? qsTr("Exterior on") : qsTr("Exterior off")
                    variant: root.s.exterior_light ? "ok" : "idle"
                }
            }

            Card {
                Layout.fillWidth: true
                title: qsTr("Speed & Authority")

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
                    value: root.s.authority
                        + (root.s.authority === 1 ? qsTr(" block") : qsTr(" blocks"))
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
                id: cabinAndLoadCard
                Layout.fillWidth: true
                // The two columns share a top origin, so this keeps the
                // lower cards on one baseline as either card changes height.
                Layout.preferredHeight: failureModesCard.y
                    + failureModesCard.height - cabinAndLoadCard.y
                title: qsTr("Cabin & Load")

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
                        value: root.fixed(root.tons(root.s.loaded_mass), 1)
                        unit: "ton"
                    }

                    TelemetryReadout {
                        Layout.fillWidth: true
                        label: qsTr("Cabin temp")
                        value: root.fixed(root.degF(root.s.cabin_temp), 0)
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
                    value: root.fixed(root.tons(root.s.empty_mass), 1) + " ton"
                }

                KeyValueRow {
                    Layout.fillWidth: true
                    label: qsTr("Power command")
                    value: root.fixed(root.kw(root.s.power_command), 0) + " / "
                        + root.fixed(root.kw(root.s.power_limit), 0) + " kW"
                    rule: false
                }

                UsageBar {
                    Layout.fillWidth: true
                    value: root.s.power_command
                    ceiling: root.s.power_limit
                }

            }

        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.alignment: Qt.AlignTop
            Layout.margins: theme.space_5
            Layout.leftMargin: 0
            spacing: theme.space_5

            Card {
                Layout.fillWidth: true
                title: qsTr("Brakes & Doors")
                statusLabel: root.s.emergency_brake
                    ? qsTr("Emergency brake applied")
                    : qsTr("Emergency brake released")
                statusVariant: root.s.emergency_brake ? "fault" : "ok"

                SafetyButton {
                    Layout.fillWidth: true
                    Layout.preferredHeight: theme.safety_emphasis_height
                    Layout.topMargin: theme.space_5
                    objectName: "passengerEmergencyBrake"
                    label: qsTr("Apply emergency brake")
                    // Never offers a release: whether passengers may release
                    // it is undecided. Disabled while the emergency brake is
                    // engaged from any source (a Train Controller command or
                    // a pull) and while a pull is latched.
                    enabled: !root.s.emergency_brake
                        && !root.s.passenger_ebrake_pulled
                    // tooltip: qsTr("Stops the train at the full braking rate and "
                        // + "reports the stop to the track controller and the "
                        // + "CTC. Confirmation is required.")
                    onConfirmed: trainModel.applyEmergencyBrake()
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: theme.space_3
                    spacing: theme.space_3

                    Text {
                        Layout.fillWidth: true
                        text: qsTr("Left doors")
                        color: theme.text_secondary
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_small
                        font.weight: theme.weight_regular
                    }

                    StatusBadge {
                        label: root.s.left_door
                            ? qsTr("Open") : qsTr("Closed")
                        variant: root.s.left_door ? "ok" : "idle"
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        Layout.fillWidth: true
                        text: qsTr("Right doors")
                        color: theme.text_secondary
                        font.family: theme.ui_family
                        font.pixelSize: theme.size_small
                        font.weight: theme.weight_regular
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

                // The station in the current block. The next station is
                // the last beacon's, kept until the train reaches it.
                KeyValueRow {
                    objectName: "currentStation"
                    Layout.fillWidth: true
                    label: qsTr("Station")
                    value: root.s.station
                }

                KeyValueRow {
                    objectName: "nextStation"
                    Layout.fillWidth: true
                    label: qsTr("Next station · arrival")
                    value: root.s.next_station + " ("
                        + root.s.platform_side + ") · " + root.s.arrival
                    rule: false
                }
            }

            Card {
                id: failureModesCard
                Layout.fillWidth: true
                title: qsTr("Failure Modes")
                statusLabel: trainModel.activeFailureCount > 0
                    ? trainModel.activeFailureCount + qsTr(" active")
                    : qsTr("Clear")
                statusVariant: trainModel.activeFailureCount > 0 ? "fault" : "ok"

                Repeater {
                    model: trainModel.failures

                    delegate: AppButton {
                        required property var modelData

                        Layout.fillWidth: true
                        // An active failure is a fault, so its button shows
                        // red (Kevin 2026-10-06), where style guide 6.1 gives
                        // a clear-fault action the green success fill.
                        variant: modelData.active ? "danger" : "secondary"
                        text: (modelData.active ? qsTr("Clear ") : qsTr("Induce "))
                            + modelData.label + qsTr(" failure")
                        // tooltip: qsTr("A failure stays set until it is cleared here. "
                            // + "With signal pickup failed, no new commanded speed "
                            // + "or authority reaches this train.")
                        onClicked: trainModel.setFailure(
                            modelData.name, !modelData.active)
                    }
                }
            }
        }
    }
}
