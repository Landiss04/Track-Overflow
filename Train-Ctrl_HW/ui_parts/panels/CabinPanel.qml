// Doors, cabin temperature and lights: everything the driver touches
// at a station stop.
import QtQuick
import QtQuick.Layouts
import "../../../ui"
import "../components"

Panel {
    id: root

    readonly property var s: controller.snapshot
    // What the train reports, which is what the driver should be
    // looking at. The commands are the outputs beside them.
    readonly property bool anyDoorOpen: s.fb_doors_left || s.fb_doors_right

    title: qsTr("Doors & cabin")
    headerItems: [
        StatusBadge {
            label: !root.s.can_drive ? qsTr("Locked")
                : root.anyDoorOpen ? qsTr("Open") : qsTr("Closed")
            variant: !root.s.can_drive ? "idle"
                : root.anyDoorOpen ? "info" : "ok"
        }
    ]

<<<<<<< HEAD
    // Only the platform side opens, and only at a stand; an open door
    // can always be closed, so a door left open when the platform side
    // changes is not stuck. A moving train says why it will not open.
=======
    // Either side opens at a stand, only the platform side at a
    // station (REQUIREMENTS.md M6); an open door can always be closed.
    // A tile that cannot act now is greyed.
>>>>>>> origin/Train_Ctrl_integration
    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_2

        ToggleTile {
            Layout.fillWidth: true
<<<<<<< HEAD
            enabled: root.s.can_drive && (root.s.fb_doors_left
                || (root.s.platform_left && root.s.at_stand))
            on: root.s.fb_doors_left
            tone: "info"
            text: root.s.fb_doors_left ? qsTr("Close left")
                : root.s.at_stand ? qsTr("Open left")
                : qsTr("Left: stop first")
=======
            enabled: root.s.can_drive
                && (root.s.fb_doors_left || root.s.may_open_left)
            on: root.s.fb_doors_left
            tone: "info"
            text: root.s.fb_doors_left ? qsTr("Close left")
                                       : qsTr("Open left")
>>>>>>> origin/Train_Ctrl_integration
            onClicked: controller.set_door("left", !root.s.fb_doors_left)
        }

        ToggleTile {
            Layout.fillWidth: true
<<<<<<< HEAD
            enabled: root.s.can_drive && (root.s.fb_doors_right
                || (root.s.platform_right && root.s.at_stand))
            on: root.s.fb_doors_right
            tone: "info"
            text: root.s.fb_doors_right ? qsTr("Close right")
                : root.s.at_stand ? qsTr("Open right")
                : qsTr("Right: stop first")
=======
            enabled: root.s.can_drive
                && (root.s.fb_doors_right || root.s.may_open_right)
            on: root.s.fb_doors_right
            tone: "info"
            text: root.s.fb_doors_right ? qsTr("Close right")
                                        : qsTr("Open right")
>>>>>>> origin/Train_Ctrl_integration
            onClicked: controller.set_door("right", !root.s.fb_doors_right)
        }
    }

    TempDial {
        Layout.fillWidth: true
        Layout.fillHeight: true
        target: root.s.target_temp_f
        actual: root.s.cabin_temp_f
        interactive: root.s.can_drive
        onTargetRequested: function (degrees) {
            controller.set_target_temp_f(degrees);
        }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: theme.space_2

        ToggleTile {
            Layout.fillWidth: true
            enabled: root.s.can_drive
            on: root.s.fb_interior_lights
            text: root.s.fb_interior_lights ? qsTr("Interior on")
                                            : qsTr("Interior off")
            onClicked: controller.set_interior_lights(
                !root.s.fb_interior_lights)
        }

        ToggleTile {
            Layout.fillWidth: true
            enabled: root.s.can_drive
            on: root.s.fb_exterior_lights
            text: root.s.fb_exterior_lights ? qsTr("Exterior on")
                                            : qsTr("Exterior off")
            onClicked: controller.set_exterior_lights(
                !root.s.fb_exterior_lights)
        }
    }
}
