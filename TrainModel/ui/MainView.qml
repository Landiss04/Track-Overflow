import QtQuick
import QtQuick.Layouts
import "."
import "./components"

// Page 3a — Main page: the operational Train Model view. Two equal-weight
// columns; every displayed value binds to trainModel state, every visual
// property resolves through the theme tokens.
ColumnLayout {
    id: root

    TopBar {
        Layout.fillWidth: true
        title: "Train Model"
        trainSelector: trainModel.train_selector
        clock: trainModel.clock
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.leftMargin: theme.space_3
        Layout.rightMargin: theme.space_3
        spacing: theme.space_3

        // ---- Left column: what the train is doing ---------------------
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: theme.space_4

            Banner {
                Layout.fillWidth: true
                heading: trainModel.mode_label
                tooltip: "Speed and authority come from the track controller; " +
                        "the manual throttle is locked out and the doors will " +
                        "not release above 0 MPH."
            }

            Card {
                Layout.fillWidth: true
                title: "SPEED & AUTHORITY"
                badgeText: trainModel.speed_auth_badge
                badgeVariant: "ok"

                RowLayout {
                    Layout.fillWidth: true
                    spacing: theme.space_3

                    MetricTile {
                        Layout.fillWidth: true
                        label: "ACTUAL SPEED"
                        value: trainModel.actual_speed
                        unit: "MPH"
                    }
                    MetricTile {
                        Layout.fillWidth: true
                        label: "COMMANDED"
                        value: trainModel.commanded_display
                        unit: "MPH"
                    }
                    MetricTile {
                        Layout.fillWidth: true
                        label: "SPEED LIMIT"
                        value: trainModel.speed_limit
                        unit: "MPH"
                    }
                }

                KeyValueRow {
                    Layout.fillWidth: true
                    label: "Authority"
                    value: trainModel.authority
                }
                KeyValueRow {
                    Layout.fillWidth: true
                    label: "Distance to end of authority"
                    value: trainModel.distance_to_eoa
                }
                KeyValueRow {
                    Layout.fillWidth: true
                    label: "Acceleration"
                    value: trainModel.acceleration
                }
                KeyValueRow {
                    Layout.fillWidth: true
                    lastRow: true
                    label: "Grade"
                    value: trainModel.grade
                }
            }

            Card {
                Layout.fillWidth: true
                title: "CABIN & LOAD"
                badgeText: trainModel.cabin_badge
                badgeVariant: "idle"

                RowLayout {
                    Layout.fillWidth: true
                    spacing: theme.space_3

                    MetricTile {
                        Layout.fillWidth: true
                        label: "PASSENGERS"
                        value: trainModel.passengers
                    }
                    MetricTile {
                        Layout.fillWidth: true
                        label: "LOADED MASS"
                        value: trainModel.loaded_mass
                        unit: "T"
                    }
                    MetricTile {
                        Layout.fillWidth: true
                        label: "CABIN TEMP"
                        value: trainModel.cabin_temp
                        unit: "°F"
                    }
                }

                KeyValueRow {
                    Layout.fillWidth: true
                    label: "Crew"
                    value: trainModel.crew
                }
                KeyValueRow {
                    Layout.fillWidth: true
                    label: "Cars"
                    value: trainModel.cars
                }
                KeyValueRow {
                    Layout.fillWidth: true
                    label: "Train size (L|W|H)"
                    value: trainModel.train_size
                }
                KeyValueRow {
                    Layout.fillWidth: true
                    label: "Empty mass"
                    value: trainModel.empty_mass
                }

                // Power consumption row + progress bar (~78 % fill).
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: theme.space_2

                    KeyValueRow {
                        Layout.fillWidth: true
                        lastRow: true
                        label: "Power consumption"
                        value: trainModel.power_consumption
                    }
                    ProgressBar {
                        Layout.fillWidth: true
                        fraction: trainModel.power_fill
                    }
                }

                SectionLabel {
                    Layout.fillWidth: true
                    label: "Lights"
                }

                // Lights are controller-driven; the model displays state
                // only — read-only rows, no toggle, no click target.
                KeyValueRow {
                    Layout.fillWidth: true
                    label: "Interior"
                    value: trainModel.interior_light_state
                }
                KeyValueRow {
                    Layout.fillWidth: true
                    lastRow: true
                    label: "Exterior"
                    value: trainModel.exterior_light_state
                }
            }

            Card {
                Layout.fillWidth: true
                title: "POSITION"
                badgeText: trainModel.position_badge
                badgeVariant: "info"

                SectionLabel {
                    Layout.fillWidth: true
                    label: "Direction of travel"
                }
                ReadOnlyField {
                    Layout.fillWidth: true
                    value: trainModel.direction_of_travel
                }

                KeyValueRow {
                    Layout.fillWidth: true
                    label: "Current block"
                    value: trainModel.current_block
                }
                KeyValueRow {
                    Layout.fillWidth: true
                    label: "Distance into block"
                    value: trainModel.distance_into_block
                }
                KeyValueRow {
                    Layout.fillWidth: true
                    lastRow: true
                    label: "Next station · arrival"
                    value: trainModel.next_station
                }
            }
        }

        // ---- Right column: brakes, doors, failure modes ---------------
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: theme.space_4

            Card {
                Layout.fillWidth: true
                title: "BRAKES & DOORS"
                badgeText: trainModel.brakes_badge
                badgeVariant: "ok"

                SectionLabel {
                    Layout.fillWidth: true
                    label: "Brakes"
                }

                // Split ownership: the e-brake is a Train Model control and
                // stays interactive (Style Guide §7 safety-critical size).
                // The verb states the live state — no separate status row.
                PrimaryButton {
                    Layout.fillWidth: true
                    large: true
                    text: trainModel.passenger_ebrake_state === "APPLIED"
                          ? "RELEASE EMERGENCY BRAKE" : "APPLY EMERGENCY BRAKE"
                    tooltip: "Stops the train at full braking rate and reports " +
                            "the stop to the track controller and the CTC."
                    onClicked: trainModel.apply_emergency_brake()
                }

                // Divider (Figma "HorizontalBorder").
                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: theme.border
                }

                SectionLabel {
                    Layout.fillWidth: true
                    label: "Doors"
                }
                TableHeader {
                    Layout.fillWidth: true
                    columns: ["Car", "Side", "State"]
                    fractions: [0.4, 0.3, 0.3]
                }

                Repeater {
                    model: trainModel.door_states
                    delegate: TableRow {
                        Layout.fillWidth: true
                        cells: [modelData.car, modelData.side, modelData.state]
                        fractions: [0.4, 0.3, 0.3]
                        monoColumns: [true, false, false]
                        lastRow: index === trainModel.door_states.length - 1
                    }
                }

                // Manual door control — rendered disabled per the mockup
                // (see README "Design discrepancies", item 11).
                // Sub-label disabled with its buttons (Style Guide §6.1
                // disabled state: 40–45 % opacity, no pointer).
                SectionLabel {
                    Layout.fillWidth: true
                    label: "Manual door control"
                    opacity: theme.disabled_opacity
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: theme.space_3

                    SecondaryButton {
                        Layout.fillWidth: true
                        enabled_: false
                        text: "OPEN LEFT DOORS"
                        tooltip: "Doors unlock at 0 MPH with the service brake applied."
                    }
                    SecondaryButton {
                        Layout.fillWidth: true
                        enabled_: false
                        text: "CLOSE LEFT DOORS"
                        tooltip: "Doors unlock at 0 MPH with the service brake applied."
                    }
                    SecondaryButton {
                        Layout.fillWidth: true
                        enabled_: false
                        text: "OPEN RIGHT DOORS"
                        tooltip: "Doors unlock at 0 MPH with the service brake applied."
                    }
                    SecondaryButton {
                        Layout.fillWidth: true
                        enabled_: false
                        text: "CLOSE RIGHT DOORS"
                        tooltip: "Doors unlock at 0 MPH with the service brake applied."
                    }
                }
            }

            Card {
                Layout.fillWidth: true
                title: "FAILURE MODES"
                badgeText: trainModel.failure_badge
                badgeVariant: "fault"

                // The verb states the live state (INDUCE when normal, CLEAR
                // when failed) — no separate status line on the button.
                SecondaryButton {
                    Layout.fillWidth: true
                    text: trainModel.engine_failure_state.indexOf("FAILED") >= 0
                          ? "CLEAR ENGINE FAILURE" : "INDUCE ENGINE FAILURE"
                    tooltip: "A failure stays set until it is cleared here. With " +
                            "signal pickup failed, no new commanded speed or " +
                            "authority reaches this train."
                    onClicked: trainModel.toggle_engine_failure()
                }
                SecondaryButton {
                    Layout.fillWidth: true
                    text: trainModel.brake_failure_state.indexOf("FAILED") >= 0
                          ? "CLEAR BRAKE FAILURE" : "INDUCE BRAKE FAILURE"
                    tooltip: "A failure stays set until it is cleared here. With " +
                            "signal pickup failed, no new commanded speed or " +
                            "authority reaches this train."
                    onClicked: trainModel.toggle_brake_failure()
                }
                SecondaryButton {
                    Layout.fillWidth: true
                    text: trainModel.signal_pickup_state.indexOf("FAILED") >= 0
                          ? "CLEAR SIGNAL PICKUP FAILURE" : "INDUCE SIGNAL PICKUP FAILURE"
                    tooltip: "A failure stays set until it is cleared here. With " +
                            "signal pickup failed, no new commanded speed or " +
                            "authority reaches this train."
                    onClicked: trainModel.toggle_signal_pickup()
                }
            }
        }
    }
}
