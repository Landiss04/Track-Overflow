// Page 4: the driver's cab. Three columns: what is ahead, what the driver
// controls, and passenger comfort. Built from the shared ui/ components;
// SignalAspectRow and TrackAhead are local because nothing shared fits.
// Engineer gain tuning is not part of this view (EngineerGainsPopup).
import QtQuick
import QtQuick.Layouts
import "components"
import "../../ui"

RowLayout {
    id: root

    readonly property var snapshot: controller.snapshot
    readonly property bool manual: snapshot.mode === "Manual"
    readonly property var offOn: ["Off", "On"]

    function formatNumber(value) {
        return Number(value).toLocaleString(Qt.locale("en_US"), "f", 0);
    }

    function sideText(side) {
        return side === "BOTH" ? "Both sides"
            : side === "LEFT" ? "Left" : side === "RIGHT" ? "Right" : "";
    }

    function doorHelp() {
        if (snapshot.dwelling)
            return "Station stop: doors close automatically "
                + "5 s before departure.";
        if (!manual && !(snapshot.left_door || snapshot.right_door))
            return "Automatic: doors open by themselves at each station.";
        if (snapshot.left_door || snapshot.right_door)
            return "Doors are open. The train will not move until they close.";
        if (!snapshot.at_station)
            return "Doors open only when stopped at a platform.";
        if (!snapshot.is_stopped)
            return "Stop the train fully to open the doors.";
        return "Platform on the " + sideText(snapshot.platform_side).toLowerCase() + ".";
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
        bodyPadding: theme.space_3
        headerItems: [
            MonoText {
                text: "Block " + root.snapshot.current_block
                    + " · Section " + root.snapshot.current_section
            }
        ]

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

            // Authority is a block ID, not a distance: shown unconverted
            // and with no unit (truth conventions/units.md).
            TelemetryReadout {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                label: "Authority"
                value: root.snapshot.authority_block
            }
        }

        FieldLabel {
            text: root.snapshot.next_block !== ""
                ? "SIGNAL AHEAD · ENTERING BLOCK " + root.snapshot.next_block
                : "SIGNAL AHEAD"
        }

        // Read-only: the aspect is a Track Model output, never set here.
        SignalAspectRow {
            Layout.fillWidth: true
            aspect: root.snapshot.signal_aspect
        }

        HelperText {
            Layout.fillWidth: true
            visible: root.snapshot.signal_aspect_source === "placeholder"
            text: "Placeholder — the Track Model will supply this signal."
        }

        FieldLabel {
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

        Panel {
            Layout.fillWidth: true
            title: "Speed"
            bodyPadding: theme.space_3
            headerItems: [
                StatusBadge {
                    variant: root.manual ? "idle" : "info"
                    label: root.manual ? "Driver control" : "CTC control"
                }
            ]

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.space_3

                TelemetryReadout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    label: "Target speed"
                    value: root.snapshot.target_speed_mph
                    unit: "mph"
                }

                TelemetryReadout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    label: "Set by"
                    value: root.snapshot.target_set_by
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.space_3

                AppButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 56
                    size: "large"
                    text: "Slower"
                    enabled: root.manual && root.snapshot.target_speed_mph > 0
                    onClicked: controller.slower()
                }

                AppButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 56
                    size: "large"
                    text: "Faster"
                    enabled: root.manual && root.snapshot.target_speed_mph
                        < root.snapshot.speed_limit_mph
                    onClicked: controller.faster()
                }
            }

            AppButton {
                Layout.fillWidth: true
                text: root.manual
                    ? "Use CTC target · " + root.snapshot.ctc_speed_mph + " mph"
                    : "CTC sets the speed in Automatic mode"
                enabled: root.manual
                onClicked: controller.useCtcTarget()
            }
        }

        Panel {
            Layout.fillWidth: true
            title: "Brakes"
            bodyPadding: theme.space_3
            headerItems: [
                StatusBadge {
                    visible: root.snapshot.service_brake
                    variant: "fault"
                    label: "Service brake on"
                }
            ]

            // The Train Controller brakes act immediately, with no
            // confirmation step (style guide 7).
            FormField {
                Layout.fillWidth: true
                label: "Service brake"

                SegmentedToggle {
                    Layout.fillWidth: true
                    options: root.offOn
                    currentIndex: root.snapshot.service_brake ? 1 : 0
                    onActivated: function (index) {
                        controller.setServiceBrake(index === 1);
                    }
                }
            }

            // At least --space-5 from the routine controls (style guide 7).
            SafetyButton {
                Layout.fillWidth: true
                Layout.preferredHeight: 72
                Layout.topMargin: theme.space_5 - theme.space_3
                confirmationRequired: false
                label: "Emergency brake"
                releaseLabel: "Release emergency brake"
                applied: root.snapshot.emergency_brake
                enabled: !applied || root.snapshot.can_release_emergency_brake
                onConfirmed: {
                    if (root.snapshot.emergency_brake)
                        controller.releaseEmergencyBrake();
                    else
                        controller.pullEmergencyBrake();
                }
            }

            HelperText {
                Layout.fillWidth: true
                text: !root.snapshot.emergency_brake
                    ? "Full stop. You can release it once the train has stopped."
                    : root.snapshot.can_release_emergency_brake
                    ? "Train stopped. Release the brake when it is safe."
                    : "Stopping. Release is available once the train is fully stopped."
            }
        }

        Panel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            title: "Doors"
            bodyPadding: theme.space_3
            headerItems: [
                StatusBadge {
                    variant: root.doorStatus === "Shut" ? "idle" : "warning"
                    label: root.doorStatus
                }
            ]

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.space_3

                AppButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 56
                    size: "large"
                    text: root.snapshot.left_door ? "Close left" : "Open left"
                    enabled: (root.snapshot.left_door && !root.snapshot.dwelling)
                        || root.snapshot.can_open_left
                    onClicked: controller.toggleLeftDoor()
                }

                AppButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 56
                    size: "large"
                    text: root.snapshot.right_door ? "Close right" : "Open right"
                    enabled: (root.snapshot.right_door && !root.snapshot.dwelling)
                        || root.snapshot.can_open_right
                    onClicked: controller.toggleRightDoor()
                }
            }

            HelperText {
                Layout.fillWidth: true
                text: root.doorHelp()
            }

            Item { Layout.fillHeight: true }
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
            bodyPadding: theme.space_3
            headerItems: [
                StatusBadge {
                    visible: root.snapshot.dwelling
                    variant: "info"
                    label: "Dwell " + root.snapshot.dwell_left_s + " s"
                }
            ]

            KeyValueRow {
                Layout.fillWidth: true
                label: "Station"
                value: root.snapshot.next_station
            }

            KeyValueRow {
                Layout.fillWidth: true
                label: "Block"
                value: root.snapshot.station_block
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
                value: root.sideText(root.snapshot.platform_side)
                rule: false
            }

            AppButton {
                Layout.fillWidth: true
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
            bodyPadding: theme.space_3

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.space_3

                AppButton {
                    Layout.preferredWidth: 124
                    Layout.fillHeight: true
                    size: "large"
                    text: "Cooler"
                    onClicked: controller.cooler()
                }

                TelemetryReadout {
                    Layout.fillWidth: true
                    label: "Target"
                    value: root.snapshot.temp_setpoint_f
                    unit: "°F"
                }

                AppButton {
                    Layout.preferredWidth: 124
                    Layout.fillHeight: true
                    size: "large"
                    text: "Warmer"
                    onClicked: controller.warmer()
                }
            }

            KeyValueRow {
                Layout.fillWidth: true
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
            bodyPadding: theme.space_3

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.space_4

                FormField {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    label: "Cabin"

                    SegmentedToggle {
                        Layout.fillWidth: true
                        options: root.offOn
                        currentIndex: root.snapshot.cabin_light ? 1 : 0
                        onActivated: function (index) {
                            controller.setCabinLight(index === 1);
                        }
                    }
                }

                FormField {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    label: "Headlights"

                    SegmentedToggle {
                        Layout.fillWidth: true
                        options: root.offOn
                        currentIndex: root.snapshot.headlight ? 1 : 0
                        onActivated: function (index) {
                            controller.setHeadlight(index === 1);
                        }
                    }
                }
            }

            Item { Layout.fillHeight: true }
        }
    }
}
