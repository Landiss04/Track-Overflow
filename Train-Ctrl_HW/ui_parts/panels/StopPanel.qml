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
        // What the brakes are actually doing, as the Train Model
        // reports it (Brake State), not what was asked of them.
        StatusBadge {
            label: root.s.fault_brake ? qsTr("Brakes failed")
                : root.s.fb_emergency_brake ? qsTr("Emergency")
                : root.s.fb_service_brake ? qsTr("Braking")
                : qsTr("Running")
            variant: root.s.fault_brake || root.s.fb_emergency_brake
                ? "fault"
                : root.s.fb_service_brake ? "warning" : "ok"
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
        // A brake failure disables both brakes, in either mode.
        enabled: !root.s.fault_brake
        applied: root.s.emergency_brake
        text: root.s.emergency_brake ? qsTr("Release emergency brake")
                                     : qsTr("Emergency brake")
        onClicked: controller.toggle_emergency_brake()
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
        enabled: root.s.can_drive && !root.s.fault_brake
        applied: root.s.service_request
        text: root.s.service_request ? qsTr("Release service brake")
                                     : qsTr("Service brake")
        onClicked: controller.toggle_service_brake()
    }

    HelperText {
        Layout.fillWidth: true
        Layout.preferredHeight: 34
        horizontalAlignment: Text.AlignHCenter
        text: root.s.brake_note
    }
}
