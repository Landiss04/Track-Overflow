// Page 4: the driver's cab. Three columns — what is ahead, what the driver
// controls, and passenger comfort. Engineer gain tuning is not part of this
// view; it lives in EngineerGainsPopup.
import QtQuick
import QtQuick.Layouts
import "components"

RowLayout {
    id: root

    readonly property var snapshot: controller.snapshot
    readonly property bool manual: snapshot.mode === "Manual"

    function formatNumber(value) {
        return Number(value).toLocaleString(Qt.locale("en_US"), "f", 0);
    }

    function doorSubtitle(side, open) {
        if (open)
            return "Doors are open";
        if (snapshot.platform_side !== side)
            return "No platform";
        return snapshot.is_stopped ? "Platform side" : "Stop the train first";
    }

    readonly property string doorStatus: snapshot.left_door && snapshot.right_door
        ? "Both open" : snapshot.left_door ? "Left open"
        : snapshot.right_door ? "Right open" : "Shut"

    spacing: theme.space_3

    // ---------------------------------------------------------------
    // Left: speed and track ahead
    // ---------------------------------------------------------------
    Panel {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.preferredWidth: 558
        title: "Speed and track ahead"
        trailing: root.snapshot.current_block + " · "
            + root.formatNumber(root.snapshot.authority_ft) + " ft authority"
        trailingMono: true

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.space_3

            TelemetryReadout {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                label: "Current speed"
                value: root.snapshot.current_speed_mph
                unit: "mph"
            }

            TelemetryReadout {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                label: "Speed limit"
                value: root.snapshot.speed_limit_mph
                unit: "mph"
            }

            TelemetryReadout {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                label: "To stop point"
                value: root.formatNumber(root.snapshot.authority_ft)
                unit: "ft"
            }
        }

        FieldLabel {
            Layout.topMargin: theme.space_1
            text: root.snapshot.next_block !== ""
                ? "SIGNAL AHEAD · ENTERING " + root.snapshot.next_block
                : "SIGNAL AHEAD"
        }

        SignalAspectRow {
            Layout.fillWidth: true
            aspect: root.snapshot.signal_aspect
        }

        FieldLabel {
            Layout.topMargin: theme.space_2
            text: "TRACK AHEAD — YOUR TRAIN AT THE BOTTOM"
        }

        TrackAhead {
            Layout.fillWidth: true
            Layout.fillHeight: true
            blocks: root.snapshot.blocks
        }
    }

    // ---------------------------------------------------------------
    // Middle: speed, brakes, doors
    // ---------------------------------------------------------------
    ColumnLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.preferredWidth: 415
        spacing: theme.space_3

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: theme.control_h_lg
            radius: theme.radius_lg
            color: root.manual ? theme.bg_sunken : theme.accent_subtle
            border.color: theme.border
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: theme.space_4
                anchors.rightMargin: theme.space_4
                spacing: theme.space_3

                Text {
                    text: root.snapshot.mode.toUpperCase()
                    color: root.manual ? theme.text_primary : theme.accent
                    font.family: theme.ui_family
                    font.pixelSize: theme.size_small
                    font.weight: theme.weight_bold
                    font.letterSpacing: theme.label_letter_spacing
                }

                HelperText {
                    Layout.fillWidth: true
                    text: root.manual ? "CTC speed control is off."
                        : "CTC speed control is on. Speed buttons are locked."
                }
            }
        }

        Panel {
            Layout.fillWidth: true
            title: "Speed"

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.space_2

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    spacing: theme.space_1

                    FieldLabel { text: "TARGET SPEED" }

                    ValueBox {
                        Layout.fillWidth: true
                        text: root.snapshot.target_speed_mph + " mph"
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    spacing: theme.space_1

                    FieldLabel { text: "SET BY" }

                    ValueBox {
                        Layout.fillWidth: true
                        text: root.snapshot.target_set_by
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.space_2

                BigButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 76
                    text: "SLOWER"
                    enabled: root.manual && root.snapshot.target_speed_mph > 0
                    onClicked: controller.slower()
                }

                BigButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 76
                    text: "FASTER"
                    enabled: root.manual && root.snapshot.target_speed_mph
                        < root.snapshot.speed_limit_mph
                    onClicked: controller.faster()
                }
            }

            AppButton {
                Layout.fillWidth: true
                text: "Use CTC target · " + root.snapshot.ctc_speed_mph + " mph"
                enabled: root.manual
                onClicked: controller.useCtcTarget()
            }
        }

        Panel {
            Layout.fillWidth: true
            title: "Brakes"

            FieldLabel { text: "SERVICE BRAKE" }

            OnOffToggle {
                Layout.fillWidth: true
                Layout.preferredHeight: 56
                checked: root.snapshot.service_brake
                dangerWhenOn: true
                onToggled: function (on) { controller.setServiceBrake(on); }
            }

            // Style guide 7: at least --space-5 between the emergency
            // control and routine controls.
            EmergencyBrakeButton {
                Layout.fillWidth: true
                Layout.preferredHeight: 116
                Layout.topMargin: theme.space_5 - theme.space_2
                engaged: root.snapshot.emergency_brake
                onClicked: controller.pullEmergencyBrake()
            }

            AppButton {
                Layout.fillWidth: true
                visible: root.snapshot.emergency_brake
                variant: "ghost"
                size: "small"
                text: "Simulate office release (test only)"
                onClicked: controller.simulateOfficeRelease()
            }
        }

        Panel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            title: "Doors"
            trailing: root.doorStatus

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: theme.space_2

                BigButton {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 1
                    text: root.snapshot.left_door ? "CLOSE LEFT" : "OPEN LEFT"
                    subtitle: root.doorSubtitle("LEFT", root.snapshot.left_door)
                    enabled: root.snapshot.left_door || root.snapshot.can_open_left
                    onClicked: controller.toggleLeftDoor()
                }

                BigButton {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 1
                    text: root.snapshot.right_door ? "CLOSE RIGHT" : "OPEN RIGHT"
                    subtitle: root.doorSubtitle("RIGHT", root.snapshot.right_door)
                    enabled: root.snapshot.right_door || root.snapshot.can_open_right
                    onClicked: controller.toggleRightDoor()
                }
            }
        }
    }

    // ---------------------------------------------------------------
    // Right: next station, cabin temperature, lights
    // ---------------------------------------------------------------
    ColumnLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.preferredWidth: 415
        spacing: theme.space_3

        Panel {
            Layout.fillWidth: true
            title: "Next station"

            KeyValueRow {
                Layout.fillWidth: true
                label: "Station"
                value: root.snapshot.next_station
            }

            KeyValueRow {
                Layout.fillWidth: true
                label: "Arrives"
                value: root.snapshot.station_arrival
            }

            KeyValueRow {
                Layout.fillWidth: true
                label: "Distance"
                value: root.snapshot.station_distance_ft >= 0
                    ? root.formatNumber(root.snapshot.station_distance_ft) + " ft" : ""
            }

            KeyValueRow {
                Layout.fillWidth: true
                label: "Doors open"
                value: root.snapshot.platform_side
                rule: false
            }

            AppButton {
                Layout.fillWidth: true
                Layout.topMargin: theme.space_1
                size: "large"
                text: "Announce again"
                onClicked: controller.announceAgain()
            }

            Callout {
                Layout.fillWidth: true
                visible: root.snapshot.announcement !== ""
                heading: "Announcing"
                body: root.snapshot.announcement
            }
        }

        // The two comfort panels share the rest of the column, with their
        // controls centred, so the column has no dead space at the bottom.
        Panel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            title: "Cabin temperature"

            Item { Layout.fillHeight: true }

            FieldLabel { text: "TARGET" }

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.space_2

                BigButton {
                    Layout.preferredWidth: 110
                    Layout.preferredHeight: 68
                    text: "COOLER"
                    onClicked: controller.cooler()
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 68
                    color: theme.bg_sunken
                    border.color: theme.border
                    border.width: 1
                    radius: theme.radius_md

                    MonoText {
                        anchors.centerIn: parent
                        text: root.snapshot.temp_setpoint_f + " °F"
                        font.pixelSize: theme.size_telemetry
                        font.weight: theme.weight_bold
                    }
                }

                BigButton {
                    Layout.preferredWidth: 110
                    Layout.preferredHeight: 68
                    text: "WARMER"
                    onClicked: controller.warmer()
                }
            }

            KeyValueRow {
                Layout.fillWidth: true
                Layout.topMargin: theme.space_2
                label: "In the cabin now"
                value: root.snapshot.cabin_temp_f + " °F"
                rule: false
            }

            Item { Layout.fillHeight: true }
        }

        Panel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            title: "Lights"

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.space_3

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    spacing: theme.space_1

                    FieldLabel { text: "CABIN" }

                    OnOffToggle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 64
                        checked: root.snapshot.cabin_light
                        onToggled: function (on) { controller.setCabinLight(on); }
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    spacing: theme.space_1

                    FieldLabel { text: "HEADLIGHTS" }

                    OnOffToggle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 64
                        checked: root.snapshot.headlight
                        onToggled: function (on) { controller.setHeadlight(on); }
                    }
                }
            }

            Item { Layout.fillHeight: true }
        }
    }
}
