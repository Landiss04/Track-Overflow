// Doors, cabin temperature and lights: everything the driver touches
// at a station stop.
import QtQuick
import QtQuick.Layouts
import "../../../ui"
import "../components"

Panel {
    id: root

    readonly property var s: controller.snapshot
    readonly property bool anyDoorOpen: s.doors_left || s.doors_right

    title: qsTr("Doors & cabin")
    headerItems: [
        StatusBadge {
            label: !root.s.can_drive ? qsTr("Locked")
                : root.anyDoorOpen ? qsTr("Open") : qsTr("Closed")
            variant: !root.s.can_drive ? "idle"
                : root.anyDoorOpen ? "info" : "ok"
        }
    ]

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_2

        ToggleTile {
            Layout.fillWidth: true
            enabled: root.s.can_drive
            on: root.s.doors_left
            tone: "info"
            text: root.s.doors_left ? qsTr("Close left") : qsTr("Open left")
            onClicked: controller.setDoor("left", !root.s.doors_left)
        }

        ToggleTile {
            Layout.fillWidth: true
            enabled: root.s.can_drive
            on: root.s.doors_right
            tone: "info"
            text: root.s.doors_right ? qsTr("Close right") : qsTr("Open right")
            onClicked: controller.setDoor("right", !root.s.doors_right)
        }
    }

    TempDial {
        Layout.fillWidth: true
        Layout.fillHeight: true
        target: root.s.target_temp_f
        actual: root.s.cabin_temp_f
        interactive: root.s.can_drive
        onTargetRequested: function (degrees) {
            controller.setTargetTemp(degrees);
        }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_2

        ToggleTile {
            Layout.fillWidth: true
            enabled: root.s.can_drive
            on: root.s.lights
            text: root.s.lights ? qsTr("Lights on") : qsTr("Lights off")
            onClicked: controller.setLights(!root.s.lights)
        }

        ToggleTile {
            Layout.fillWidth: true
            enabled: root.s.can_drive
            on: root.s.headlights
            text: root.s.headlights ? qsTr("Headlights on")
                                    : qsTr("Headlights off")
            onClicked: controller.setHeadlights(!root.s.headlights)
        }
    }
}
