// The two brakes, the only controls in the console that override an
// automatic function. Guide 7 governs everything in this file: both
// are oversized, isolated from routine controls, and uppercase.
import QtQuick
import QtQuick.Layouts
import "../../../ui"
import "../components"

Panel {
    id: root

    readonly property var s: controller.snapshot

    title: qsTr("Stop the train")
    headerItems: [
        StatusBadge {
            label: root.s.emergency_brake ? qsTr("Emergency")
                : root.s.service_request ? qsTr("Braking") : qsTr("Running")
            variant: root.s.emergency_brake ? "fault"
                : root.s.service_request ? "warning" : "ok"
        }
    ]

    // Live for any signed-in operator, in either mode. It engages the
    // moment it is pressed; releasing is a second press, and the core
    // refuses that until the train is stopped.
    BrakeButton {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.preferredHeight: 170
        tone: "emergency"
        applied: root.s.emergency_brake
        text: root.s.emergency_brake ? qsTr("Release emergency brake")
                                     : qsTr("Emergency brake")
        onClicked: controller.toggleEmergencyBrake()
    }

    // Guide 7 separation, so neither brake is hit by reaching for the
    // other.
    Item {
        Layout.fillWidth: true
        Layout.preferredHeight: theme.space_5
    }

    BrakeButton {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.preferredHeight: 100
        tone: "service"
        enabled: root.s.can_drive
        applied: root.s.service_request
        text: root.s.service_request ? qsTr("Release service brake")
                                     : qsTr("Service brake")
        onClicked: controller.toggleServiceBrake()
    }

    HelperText {
        Layout.fillWidth: true
        Layout.preferredHeight: 34
        horizontalAlignment: Text.AlignHCenter
        text: root.s.brake_note
    }
}
